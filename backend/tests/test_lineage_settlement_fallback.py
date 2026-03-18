from datetime import datetime, timedelta, timezone

import services.grading_service as grading_module
import services.calibration_service as calibration_module

from services.grading_service import GradingService
from services.calibration_service import CalibrationService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find_one(self, query):
        for doc in self.docs:
            ok = True
            for k, v in query.items():
                if doc.get(k) != v:
                    ok = False
                    break
            if ok:
                return doc
        return None

    def find(self, query):
        results = []
        for doc in self.docs:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$gte" in v and doc.get(k) < v["$gte"]:
                        ok = False
                        break
                    if "$lte" in v and doc.get(k) > v["$lte"]:
                        ok = False
                        break
                elif doc.get(k) != v:
                    ok = False
                    break
            if ok:
                results.append(doc)
        return results

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("graded_id", "ok")})


class FakeObservability:
    def __init__(self):
        self.settlement_calls = []
        self.lifecycle_calls = []

    def log_settlement_metrics(self, **kwargs):
        self.settlement_calls.append(kwargs)

    def log_prediction_lifecycle(self, **kwargs):
        self.lifecycle_calls.append(kwargs)

    def log_truth_dataset_row(self, **kwargs):
        return kwargs

    def log_clv_capture(self, **kwargs):
        return kwargs


def test_settlement_lineage_falls_back_to_prediction_when_publish_lineage_missing(monkeypatch):
    fake_obs = FakeObservability()
    monkeypatch.setattr(grading_module, "observability_service", fake_obs)
    monkeypatch.setattr(calibration_module, "observability_service", fake_obs)

    grading = GradingService()
    grading_records = FakeCollection()

    # Intentionally omit trace_id/snapshot_hash on publish doc to force fallback path.
    published = FakeCollection(
        docs=[
            {
                "publish_id": "pub_settle_1",
                "prediction_id": "pred_settle_1",
                "event_id": "event_settle_1",
                "is_official": True,
                "published_at_utc": datetime.now(timezone.utc),
                "ticket_terms": {"line": -3.5, "price": -110},
            }
        ]
    )
    predictions = FakeCollection(
        docs=[
            {
                "prediction_id": "pred_settle_1",
                "market_key": "SPREAD:FULL_GAME",
                "selection": "HOME",
                "p_cover": 0.61,
                "decision_id": "decision_settle_1",
                "trace_id": "trace_settle_1",
                "snapshot_hash": "snapshot_settle_1",
                "market_snapshot_id_used": "snapshot_settle_1",
                "recommendation_state": "OFFICIAL_EDGE",
            }
        ]
    )
    event_results = FakeCollection(
        docs=[
            {
                "event_id": "event_settle_1",
                "status": "FINAL",
                "home_score": 110,
                "away_score": 100,
                "total_score": 210,
                "margin": 10,
            }
        ]
    )
    odds_snapshots = FakeCollection(
        docs=[
            {
                "snapshot_id": "close_settle_1",
                "event_id": "event_settle_1",
                "market_key": "SPREAD:FULL_GAME",
                "selection": "HOME",
                "is_close_candidate": True,
                "price_american": -115,
            }
        ]
    )
    setattr(grading, "grading_collection", grading_records)
    setattr(grading, "published_collection", published)
    setattr(grading, "predictions_collection", predictions)
    setattr(grading, "event_results_collection", event_results)
    setattr(grading, "odds_snapshots_collection", odds_snapshots)

    graded_id = grading.grade_published_prediction("pub_settle_1")
    assert graded_id is not None

    # Settlement metrics must preserve lineage via prediction fallback.
    assert len(fake_obs.settlement_calls) == 1
    assert fake_obs.settlement_calls[0]["trace_id"] == "trace_settle_1"
    assert fake_obs.settlement_calls[0]["snapshot_hash"] == "snapshot_settle_1"

    settled_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "SETTLED"]
    assert len(settled_lifecycle) == 1
    assert settled_lifecycle[0]["decision_id"] == "decision_settle_1"
    assert settled_lifecycle[0]["trace_id"] == "trace_settle_1"
    assert settled_lifecycle[0]["snapshot_hash"] == "snapshot_settle_1"

    # Calibration training rows must carry the same lineage fields.
    calibration = CalibrationService()
    setattr(calibration, "calibration_versions_collection", FakeCollection())
    setattr(calibration, "calibration_segments_collection", FakeCollection())
    setattr(calibration, "grading_collection", grading_records)
    setattr(calibration, "published_collection", published)
    setattr(calibration, "predictions_collection", predictions)

    now = datetime.now(timezone.utc)
    samples = calibration._get_training_data(now - timedelta(days=3), now + timedelta(days=1))

    assert len(samples) == 1
    assert samples[0]["decision_id"] == "decision_settle_1"
    assert samples[0]["trace_id"] == "trace_settle_1"
    assert samples[0]["snapshot_hash"] == "snapshot_settle_1"
