import services.sim_run_tracker as sim_run_module
import services.publishing_service as publishing_module

from services.sim_run_tracker import SimRunTracker
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


class FakeObservability:
    def __init__(self):
        self.lifecycle_calls = []

    def log_prediction_lifecycle(self, **kwargs):
        self.lifecycle_calls.append(kwargs)


def test_default_lineage_values_flow_from_sim_prediction_to_publish(monkeypatch):
    fake_obs = FakeObservability()
    monkeypatch.setattr(sim_run_module, "observability_service", fake_obs)
    monkeypatch.setattr(publishing_module, "observability_service", fake_obs)

    sim_tracker = SimRunTracker()
    sim_tracker.sim_runs_collection = FakeCollection()
    sim_tracker.sim_run_inputs_collection = FakeCollection()
    predictions = FakeCollection()
    sim_tracker.predictions_collection = predictions

    prediction_id = sim_tracker.create_prediction(
        sim_run_id="sim_default",
        event_id="event_default",
        market_key="TOTAL:FULL_GAME",
        selection="OVER",
        market_snapshot_id_used="snapshot_default",
        model_line=220.5,
        p_win=None,
        p_cover=None,
        p_over=0.57,
        ev_units=0.05,
        edge_points=1.8,
        uncertainty=0.09,
        distribution_summary={"mean": 221.0},
        rcl_gate_pass=True,
        recommendation_state="MODEL_LEAN",
        tier="B",
        confidence_index=0.66,
        variance_bucket="MEDIUM",
    )

    prediction_doc = predictions.find_one({"prediction_id": prediction_id})
    assert prediction_doc is not None
    assert prediction_doc["trace_id"].startswith("trace_sim_")
    assert prediction_doc["snapshot_hash"] == "snapshot_default"

    publishing = PublishingService()
    publishing.published_collection = FakeCollection()
    publishing.predictions_collection = predictions

    publish_id = publishing.publish_prediction(
        prediction_id=prediction_id,
        channel="TELEGRAM",
        visibility="PREMIUM",
        decision_reason_codes=["LEAN_THRESHOLD_MET"],
        ticket_terms={"line": 220.5, "price": -110},
        is_official=True,
    )

    assert publish_id
    published_doc = publishing.published_collection.find_one({"publish_id": publish_id})
    assert published_doc["locked_market_snapshot_id"] == "snapshot_default"

    publish_lifecycle = [c for c in fake_obs.lifecycle_calls if c.get("stage") == "PUBLISHED"]
    assert len(publish_lifecycle) == 1
    assert publish_lifecycle[0]["trace_id"].startswith("trace_sim_")
    assert publish_lifecycle[0]["snapshot_hash"] == "snapshot_default"
