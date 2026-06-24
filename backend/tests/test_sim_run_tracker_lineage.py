import services.sim_run_tracker as sim_run_module
from services.sim_run_tracker import SimRunTracker


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("prediction_id", "ok")})

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                return type("UpdateResult", (), {"modified_count": 1})
        return type("UpdateResult", (), {"modified_count": 0})


class FakeObservability:
    def __init__(self):
        self.lifecycle_calls = []

    def log_prediction_lifecycle(self, **kwargs):
        self.lifecycle_calls.append(kwargs)


def make_tracker() -> SimRunTracker:
    tracker = SimRunTracker()
    setattr(tracker, "sim_runs_collection", FakeCollection())
    setattr(tracker, "sim_run_inputs_collection", FakeCollection())
    setattr(tracker, "predictions_collection", FakeCollection())
    return tracker


def test_create_prediction_persists_decision_trace_and_snapshot(monkeypatch):
    fake_obs = FakeObservability()
    monkeypatch.setattr(sim_run_module, "observability_service", fake_obs)

    tracker = make_tracker()

    prediction_id = tracker.create_prediction(
        sim_run_id="sim_1",
        event_id="event_1",
        market_key="SPREAD:FULL_GAME",
        selection="HOME",
        market_snapshot_id_used="snap_1",
        model_line=-3.5,
        p_win=None,
        p_cover=0.61,
        p_over=None,
        ev_units=0.08,
        edge_points=2.1,
        uncertainty=0.11,
        distribution_summary={"mean": -3.5},
        rcl_gate_pass=True,
        recommendation_state="OFFICIAL_EDGE",
        tier="A",
        confidence_index=0.75,
        variance_bucket="MEDIUM",
        decision_id="decision_1",
        trace_id="trace_1",
        snapshot_hash="snapshot_hash_1",
    )

    assert prediction_id
    predictions = getattr(tracker, "predictions_collection")
    assert len(predictions.docs) == 1
    doc = predictions.docs[0]
    assert doc["decision_id"] == "decision_1"
    assert doc["trace_id"] == "trace_1"
    assert doc["snapshot_hash"] == "snapshot_hash_1"

    assert len(fake_obs.lifecycle_calls) == 1
    lifecycle = fake_obs.lifecycle_calls[0]
    assert lifecycle["stage"] == "PREDICTION_CREATED"
    assert lifecycle["decision_id"] == "decision_1"
    assert lifecycle["trace_id"] == "trace_1"
    assert lifecycle["snapshot_hash"] == "snapshot_hash_1"
