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
        return type("InsertResult", (), {"inserted_id": doc.get("publish_id", "ok")})


class FakeObservability:
    def __init__(self):
        self.lifecycle_calls = []

    def log_prediction_lifecycle(self, **kwargs):
        self.lifecycle_calls.append(kwargs)


def make_service() -> PublishingService:
    service = PublishingService()
    setattr(service, "published_collection", FakeCollection())
    setattr(service, "predictions_collection", FakeCollection())
    return service


def test_publish_prediction_preserves_lineage_and_locks_market_snapshot(monkeypatch):
    fake_obs = FakeObservability()
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    service = make_service()
    predictions = FakeCollection(
        docs=[
        {
            "prediction_id": "pred_1",
            "event_id": "event_1",
            "market_key": "SPREAD:FULL_GAME",
            "selection": "HOME",
            "market_snapshot_id_used": "snap_1",
            "decision_id": "decision_1",
            "trace_id": "trace_1",
            "snapshot_hash": "snapshot_hash_1",
        }
    ]
    )
    setattr(service, "predictions_collection", predictions)

    publish_id = service.publish_prediction(
        prediction_id="pred_1",
        channel="TELEGRAM",
        visibility="PREMIUM",
        decision_reason_codes=["EDGE_THRESHOLD_MET"],
        ticket_terms={"line": -3.5, "price": -110},
        is_official=True,
    )

    assert publish_id
    published_collection = getattr(service, "published_collection")
    assert len(published_collection.docs) == 1
    published = published_collection.docs[0]
    assert published["locked_market_snapshot_id"] == "snap_1"

    assert len(fake_obs.lifecycle_calls) == 1
    lifecycle = fake_obs.lifecycle_calls[0]
    assert lifecycle["stage"] == "PUBLISHED"
    assert lifecycle["decision_id"] == "decision_1"
    assert lifecycle["trace_id"] == "trace_1"
    assert lifecycle["snapshot_hash"] == "snapshot_hash_1"


def test_publish_prediction_is_idempotent_for_official_duplicate(monkeypatch):
    fake_obs = FakeObservability()
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    service = make_service()
    predictions = FakeCollection(
        docs=[
        {
            "prediction_id": "pred_2",
            "event_id": "event_2",
            "market_key": "TOTAL:FULL_GAME",
            "selection": "OVER",
            "market_snapshot_id_used": "snap_2",
        }
    ]
    )
    published = FakeCollection(
        docs=[
        {
            "publish_id": "pub_existing",
            "prediction_id": "pred_2",
            "channel": "TELEGRAM",
            "is_official": True,
        }
    ]
    )
    setattr(service, "predictions_collection", predictions)
    setattr(service, "published_collection", published)

    publish_id = service.publish_prediction(
        prediction_id="pred_2",
        channel="TELEGRAM",
        visibility="PREMIUM",
        decision_reason_codes=["EDGE"],
        ticket_terms={"line": 220.5, "price": -110},
        is_official=True,
    )

    assert publish_id == "pub_existing"
    published_collection = getattr(service, "published_collection")
    assert len(published_collection.docs) == 1
    assert len(fake_obs.lifecycle_calls) == 0
