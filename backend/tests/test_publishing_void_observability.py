"""
Test: Publishing-stage void observability with immediate lineage logging
========================================================================
Validates that void_published_prediction() logs VOIDED lifecycle event
immediately with lineage preservation, independent of grading.

Critical principle: Void events must be observable at the point they occur
(in publishing service), not deferred to later grading stage.
"""
from datetime import datetime, timezone

import services.publishing_service as publishing_module

from services.publishing_service import PublishingService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("id", "ok")})

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    doc.update(update["$set"])
                return type("UpdateResult", (), {"modified_count": 1})
        return type("UpdateResult", (), {"modified_count": 0})


class FakeObservability:
    def __init__(self):
        self.lifecycle_calls = []

    def log_prediction_lifecycle(self, **kwargs):
        self.lifecycle_calls.append(kwargs)


def test_void_published_prediction_logs_voided_lifecycle_immediately(monkeypatch):
    """
    Validates immediate VOIDED lifecycle logging when void_published_prediction() called.
    
    Scenario:
    1. Publish a prediction with lineage (trace_id, snapshot_hash, decision_id)
    2. Void it via publishing service
    3. Verify VOIDED lifecycle event logged immediately with full lineage preserved
    4. Verify void logged even if grading never processes it
    
    Critical path: Publishing void → Observability VOIDED event → No dependency on grading
    """
    fake_obs = FakeObservability()
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    publishing = PublishingService()
    published_records = FakeCollection(
        docs=[
            {
                "publish_id": "pub_void_immedi_1",
                "prediction_id": "pred_immedi_1",
                "event_id": "event_immedi_1",
                "trace_id": "trace_immedi_1",
                "snapshot_hash": "snapshot_immedi_1",
                "locked_market_snapshot_id": "snap_immedi_1",
                "is_official": True,
                "published_at_utc": datetime.now(timezone.utc),
            }
        ]
    )
    predictions = FakeCollection(
        docs=[
            {
                "prediction_id": "pred_immedi_1",
                "decision_id": "decision_immedi_1",
                "trace_id": "trace_immedi_1",
                "snapshot_hash": "snapshot_immedi_1",
                "market_key": "SPREAD:FULL_GAME",
            }
        ]
    )
    setattr(publishing, "published_collection", published_records)
    setattr(publishing, "predictions_collection", predictions)

    # Void the published prediction
    voided = publishing.void_published_prediction(
        publish_id="pub_void_immedi_1",
        reason="GAME_CANCELLED"
    )
    assert voided is True

    # Verify VOIDED lifecycle event logged immediately
    voided_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "VOIDED"]
    assert len(voided_lifecycle) == 1
    assert voided_lifecycle[0]["publish_id"] == "pub_void_immedi_1"
    assert voided_lifecycle[0]["decision_id"] == "decision_immedi_1"
    assert voided_lifecycle[0]["trace_id"] == "trace_immedi_1"
    assert voided_lifecycle[0]["snapshot_hash"] == "snapshot_immedi_1"
    assert voided_lifecycle[0]["metadata"]["void_reason"] == "GAME_CANCELLED"


def test_void_with_published_lineage_fallback(monkeypatch):
    """
    Validates lineage fallback when published record has all lineage fields.
    
    Scenario: Published record has trace_id/snapshot_hash; prediction missing lineage
    Expected: Uses published record lineage, no fallback needed
    """
    fake_obs = FakeObservability()
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    publishing = PublishingService()
    published_records = FakeCollection(
        docs=[
            {
                "publish_id": "pub_void_full_lineage_1",
                "prediction_id": "pred_full_1",
                "event_id": "event_full_1",
                "trace_id": "trace_publish_full_1",
                "snapshot_hash": "snapshot_full_1",
                "locked_market_snapshot_id": "snap_full_1",
                "is_official": True,
                "published_at_utc": datetime.now(timezone.utc),
            }
        ]
    )
    predictions = FakeCollection(
        docs=[
            {
                "prediction_id": "pred_full_1",
                "decision_id": None,  # Missing decision_id in prediction
                "trace_id": None,  # Missing trace_id in prediction
                "snapshot_hash": None,  # Missing snapshot_hash in prediction
                "market_key": "TOTAL:FULL_GAME",
            }
        ]
    )
    setattr(publishing, "published_collection", published_records)
    setattr(publishing, "predictions_collection", predictions)

    # Void the published prediction
    voided = publishing.void_published_prediction(
        publish_id="pub_void_full_lineage_1",
        reason="ODDS_MISMATCH"
    )
    assert voided is True

    # Verify lineage from published record used (no fallback needed)
    voided_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "VOIDED"]
    assert len(voided_lifecycle) == 1
    assert voided_lifecycle[0]["trace_id"] == "trace_publish_full_1"
    assert voided_lifecycle[0]["snapshot_hash"] == "snapshot_full_1"
    assert voided_lifecycle[0]["metadata"]["void_reason"] == "ODDS_MISMATCH"


def test_void_with_prediction_lineage_fallback(monkeypatch):
    """
    Validates lineage fallback when published record lacks trace_id/snapshot_hash.
    
    Scenario: Published record missing trace_id/snapshot_hash; prediction has them
    Expected: Falls back to prediction lineage (consistent with grading pattern)
    """
    fake_obs = FakeObservability()
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    publishing = PublishingService()
    published_records = FakeCollection(
        docs=[
            {
                "publish_id": "pub_void_fallback_1",
                "prediction_id": "pred_fallback_1",
                "event_id": "event_fallback_1",
                "trace_id": None,  # Missing trace_id in published
                "snapshot_hash": None,  # Missing snapshot_hash in published
                "locked_market_snapshot_id": "snap_fallback_1",
                "is_official": True,
                "published_at_utc": datetime.now(timezone.utc),
            }
        ]
    )
    predictions = FakeCollection(
        docs=[
            {
                "prediction_id": "pred_fallback_1",
                "decision_id": "decision_fallback_1",
                "trace_id": "trace_fallback_1",  # Fallback source
                "snapshot_hash": "snapshot_fallback_1",  # Fallback source
                "market_key": "SPREAD:FULL_GAME",
                "market_snapshot_id_used": "snap_fallback_1",
            }
        ]
    )
    setattr(publishing, "published_collection", published_records)
    setattr(publishing, "predictions_collection", predictions)

    # Void the published prediction
    voided = publishing.void_published_prediction(
        publish_id="pub_void_fallback_1",
        reason="DATA_ERROR"
    )
    assert voided is True

    # Verify fallback to prediction lineage
    voided_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "VOIDED"]
    assert len(voided_lifecycle) == 1
    assert voided_lifecycle[0]["trace_id"] == "trace_fallback_1"  # From prediction
    assert voided_lifecycle[0]["snapshot_hash"] == "snapshot_fallback_1"  # From prediction
    assert voided_lifecycle[0]["decision_id"] == "decision_fallback_1"  # From prediction
    assert voided_lifecycle[0]["metadata"]["void_reason"] == "DATA_ERROR"


def test_void_nonexistent_prediction_returns_false(monkeypatch):
    """
    Validates graceful handling when void called on non-existent published record.
    """
    fake_obs = FakeObservability()
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    publishing = PublishingService()
    setattr(publishing, "published_collection", FakeCollection())
    setattr(publishing, "predictions_collection", FakeCollection())

    # Attempt to void non-existent prediction
    voided = publishing.void_published_prediction(
        publish_id="pub_nonexistent",
        reason="UNKNOWN"
    )
    assert voided is False
    assert len(fake_obs.lifecycle_calls) == 0  # No lifecycle event logged
