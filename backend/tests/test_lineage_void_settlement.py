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


def test_void_settlement_preserves_lineage_and_is_excluded_from_calibration_training(monkeypatch):
    fake_obs = FakeObservability()
    monkeypatch.setattr(grading_module, "observability_service", fake_obs)
    monkeypatch.setattr(calibration_module, "observability_service", fake_obs)

    grading = GradingService()
    grading.grading_collection = FakeCollection()
    published = FakeCollection(
        docs=[
            {
                "publish_id": "pub_void_1",
                "prediction_id": "pred_void_1",
                "event_id": "event_void_1",
                "is_official": True,
                "trace_id": "trace_void_1",
                "snapshot_hash": "snapshot_void_1",
                "published_at_utc": datetime.now(timezone.utc),
            }
        ]
    )
    predictions = FakeCollection(
        docs=[
            {
                "prediction_id": "pred_void_1",
                "market_key": "SPREAD:FULL_GAME",
                "selection": "HOME",
                "p_cover": 0.59,
                "decision_id": "decision_void_1",
                "trace_id": "trace_void_1",
                "snapshot_hash": "snapshot_void_1",
            }
        ]
    )
    grading.published_collection = published
    grading.predictions_collection = predictions
    grading.event_results_collection = FakeCollection(
        docs=[
            {
                "event_id": "event_void_1",
                "status": "CANCELLED",
            }
        ]
    )
    grading.odds_snapshots_collection = FakeCollection()

    graded_id = grading.grade_published_prediction("pub_void_1")
    assert graded_id is not None

    assert len(fake_obs.settlement_calls) == 1
    assert fake_obs.settlement_calls[0]["result_code"] == "VOID"
    assert fake_obs.settlement_calls[0]["trace_id"] == "trace_void_1"
    assert fake_obs.settlement_calls[0]["snapshot_hash"] == "snapshot_void_1"

    voided_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "VOIDED"]
    assert len(voided_lifecycle) == 1
    assert voided_lifecycle[0]["decision_id"] == "decision_void_1"
    assert voided_lifecycle[0]["trace_id"] == "trace_void_1"
    assert voided_lifecycle[0]["snapshot_hash"] == "snapshot_void_1"

    calibration = CalibrationService()
    calibration.calibration_versions_collection = FakeCollection()
    calibration.calibration_segments_collection = FakeCollection()
    calibration.grading_collection = grading.grading_collection
    calibration.published_collection = published
    calibration.predictions_collection = predictions

    now = datetime.now(timezone.utc)
    samples = calibration._get_training_data(now - timedelta(days=3), now + timedelta(days=1))

    # VOID outcomes must not enter calibration training labels.
    assert samples == []
