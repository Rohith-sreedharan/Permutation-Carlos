from datetime import datetime, timedelta, timezone

import services.sim_run_tracker as sim_run_module
import services.publishing_service as publishing_module
import services.grading_service as grading_module
import services.calibration_service as calibration_module
import services.distribution_governance_service as distribution_module

from services.sim_run_tracker import SimRunTracker
from services.publishing_service import PublishingService
from services.grading_service import GradingService
from services.distribution_governance_service import DistributionGovernanceService
from services.calibration_service import CalibrationService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def create_index(self, *args, **kwargs):
        return None

    def _resolve_path(self, doc, dotted_key):
        current = doc
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _match(self, doc, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._match(doc, sub) for sub in value):
                    return False
                continue
            actual = self._resolve_path(doc, key)
            if isinstance(value, dict):
                if "$in" in value and actual not in value["$in"]:
                    return False
                if "$gte" in value and (actual is None or actual < value["$gte"]):
                    return False
                if "$lte" in value and (actual is None or actual > value["$lte"]):
                    return False
                if "$lt" in value and (actual is None or actual >= value["$lt"]):
                    return False
                continue
            if actual != value:
                return False
        return True

    def find_one(self, query, projection=None, sort=None):
        matches = [doc for doc in self.docs if self._match(doc, query)]
        if not matches:
            return None
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda d: d.get(key), reverse=direction < 0)
        doc = matches[0]
        if projection:
            projected = {}
            for field, include in projection.items():
                if include and field in doc:
                    projected[field] = doc[field]
            return projected
        return doc

    def find(self, query):
        return [doc for doc in self.docs if self._match(doc, query)]

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("id", "ok")})

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if self._match(doc, query):
                doc.update(update.get("$set", {}))
                return type("UpdateResult", (), {"modified_count": 1})
        if upsert:
            new_doc = dict(query)
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)
            return type("UpdateResult", (), {"modified_count": 1})
        return type("UpdateResult", (), {"modified_count": 0})

    def update_many(self, query, update):
        modified = 0
        for doc in self.docs:
            if self._match(doc, query):
                doc.update(update.get("$set", {}))
                modified += 1
        return type("UpdateResult", (), {"modified_count": modified})

    def count_documents(self, query):
        return sum(1 for doc in self.docs if self._match(doc, query))


class FakeObservability:
    def __init__(self):
        self.lifecycle_calls = []
        self.settlement_calls = []
        self.calibration_calls = []
        self.settlement_collection = FakeCollection()

    def log_prediction_lifecycle(self, **kwargs):
        self.lifecycle_calls.append(kwargs)

    def log_settlement_metrics(self, **kwargs):
        self.settlement_calls.append(kwargs)
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "p_predicted": kwargs.get("p_predicted"),
            "actual_outcome": kwargs.get("actual_outcome"),
            "brier": kwargs.get("brier") if kwargs.get("brier") is not None else 0.0,
            "logloss": kwargs.get("logloss") if kwargs.get("logloss") is not None else 0.0,
            "ece_bucket_error": kwargs.get("ece_bucket_error") if kwargs.get("ece_bucket_error") is not None else 0.0,
        }
        self.settlement_collection.insert_one(row)

    def log_truth_dataset_row(self, **kwargs):
        return kwargs

    def log_clv_capture(self, **kwargs):
        return kwargs

    def log_calibration_record(self, **kwargs):
        self.calibration_calls.append(kwargs)

    def compute_aggregate_metrics(self, rows):
        rows = list(rows)
        if not rows:
            return {"brier": 0.0, "logloss": 0.0, "ece": 0.0, "sample_count": 0.0}
        return {
            "brier": 0.1,
            "logloss": 0.2,
            "ece": 0.05,
            "sample_count": float(len(rows)),
        }

    def run_drift_detection(self, **kwargs):
        return {"drift_id": "drift_1", "drift_detected": False}


def test_lineage_continuity_simulation_to_calibration(monkeypatch):
    event_id = "nba_event_1"
    decision_id = "decision_1"
    trace_id = "trace_1"
    snapshot_hash = "snapshot_hash_1"

    fake_obs = FakeObservability()
    monkeypatch.setattr(sim_run_module, "observability_service", fake_obs)
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)
    monkeypatch.setattr(grading_module, "observability_service", fake_obs)
    monkeypatch.setattr(calibration_module, "observability_service", fake_obs)
    monkeypatch.setattr(distribution_module, "observability_service", fake_obs)

    # Simulation -> Prediction
    sim_tracker = SimRunTracker()
    sim_tracker.sim_runs_collection = FakeCollection()
    sim_tracker.sim_run_inputs_collection = FakeCollection()
    predictions = FakeCollection()
    sim_tracker.predictions_collection = predictions

    sim_run_id = "sim_1"
    prediction_id = sim_tracker.create_prediction(
        sim_run_id=sim_run_id,
        event_id=event_id,
        market_key="SPREAD:FULL_GAME",
        selection="HOME",
        market_snapshot_id_used=snapshot_hash,
        model_line=-3.0,
        p_win=None,
        p_cover=0.64,
        p_over=None,
        ev_units=0.11,
        edge_points=2.4,
        uncertainty=0.07,
        distribution_summary={"mean": -3.0},
        rcl_gate_pass=True,
        recommendation_state="OFFICIAL_EDGE",
        tier="A",
        confidence_index=0.8,
        variance_bucket="LOW",
        decision_id=decision_id,
        trace_id=trace_id,
        snapshot_hash=snapshot_hash,
    )

    # Decision -> Distribution
    decision_records = FakeCollection(
        docs=[
            {
                "league": "NBA",
                "game_id": event_id,
                "payload": {
                    "inputs_hash": snapshot_hash,
                    "home_team_name": "Home",
                    "away_team_name": "Away",
                    "spread": {
                        "decision_id": decision_id,
                        "market_type": "SPREAD",
                        "classification": "EDGE",
                        "release_status": "OFFICIAL",
                        "probabilities": {"model_prob": 0.64},
                        "edge": {"edge_points": 2.4},
                    },
                    "total": None,
                    "moneyline": None,
                },
            }
        ]
    )
    distribution = DistributionGovernanceService(
        distribution_collection=FakeCollection(),
        decision_record_collection=decision_records,
        lifecycle_collection=FakeCollection(),
        assertion_collection=FakeCollection(),
    )
    distribution_result = distribution.evaluate(decision_id=decision_id, trace_id=trace_id)
    assert distribution_result.decision_id == decision_id

    # Prediction -> Publish
    publishing = PublishingService()
    published = FakeCollection()
    publishing.published_collection = published
    publishing.predictions_collection = predictions

    publish_id = publishing.publish_prediction(
        prediction_id=prediction_id,
        channel="TELEGRAM",
        visibility="PREMIUM",
        decision_reason_codes=["EDGE_THRESHOLD_MET"],
        ticket_terms={"line": -3.0, "price": -110},
        is_official=True,
    )

    # Publish -> Settlement
    grading = GradingService()
    grading.grading_collection = FakeCollection()
    grading.published_collection = published
    grading.predictions_collection = predictions
    grading.event_results_collection = FakeCollection(
        docs=[
            {
                "event_id": event_id,
                "status": "FINAL",
                "home_score": 110,
                "away_score": 100,
                "total_score": 210,
                "margin": 10,
            }
        ]
    )
    grading.odds_snapshots_collection = FakeCollection(
        docs=[
            {
                "snapshot_id": "close_1",
                "event_id": event_id,
                "market_key": "SPREAD:FULL_GAME",
                "selection": "HOME",
                "is_close_candidate": True,
                "price_american": -115,
            }
        ]
    )

    graded_id = grading.grade_published_prediction(publish_id)
    assert graded_id is not None

    # Settlement -> Calibration training data continuity
    calibration = CalibrationService()
    calibration.calibration_versions_collection = FakeCollection()
    calibration.calibration_segments_collection = FakeCollection()
    calibration.grading_collection = grading.grading_collection
    calibration.published_collection = published
    calibration.predictions_collection = predictions

    now = datetime.now(timezone.utc)
    samples = calibration._get_training_data(now - timedelta(days=7), now + timedelta(days=1))

    assert len(samples) == 1
    sample = samples[0]
    assert sample["decision_id"] == decision_id
    assert sample["trace_id"] == trace_id
    assert sample["snapshot_hash"] == snapshot_hash

    # Verify lifecycle continuity markers from observability calls.
    published_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "PUBLISHED"][0]
    settled_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "SETTLED"][0]
    distribution_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "DISTRIBUTION_GOVERNANCE"][0]

    assert published_lifecycle["decision_id"] == decision_id
    assert published_lifecycle["trace_id"] == trace_id
    assert published_lifecycle["snapshot_hash"] == snapshot_hash

    assert distribution_lifecycle["decision_id"] == decision_id
    assert distribution_lifecycle["trace_id"] == trace_id
    assert distribution_lifecycle["snapshot_hash"] == snapshot_hash

    assert settled_lifecycle["decision_id"] == decision_id
    assert settled_lifecycle["trace_id"] == trace_id
    assert settled_lifecycle["snapshot_hash"] == snapshot_hash
