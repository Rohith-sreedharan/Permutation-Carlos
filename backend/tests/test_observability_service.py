from services.observability_service import ObservabilityService


class FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("id", "ok")})


def make_service() -> tuple[ObservabilityService, dict[str, FakeCollection]]:
    collections = {
        "lifecycle": FakeCollection(),
        "decision_audit": FakeCollection(),
        "settlement": FakeCollection(),
        "truth": FakeCollection(),
        "clv": FakeCollection(),
        "calibration": FakeCollection(),
        "drift": FakeCollection(),
    }
    service = ObservabilityService(
        lifecycle_collection=collections["lifecycle"],
        decision_audit_collection=collections["decision_audit"],
        settlement_collection=collections["settlement"],
        truth_dataset_collection=collections["truth"],
        clv_collection=collections["clv"],
        calibration_collection=collections["calibration"],
        drift_collection=collections["drift"],
    )
    return service, collections


def test_lifecycle_and_audit_include_trace_and_snapshot_hash():
    service, collections = make_service()

    lifecycle_id = service.log_prediction_lifecycle(
        stage="DECISION_COMPUTED",
        decision_id="d1",
        event_id="e1",
        trace_id="t1",
        snapshot_hash="s1",
        metadata={"market_type": "spread"},
    )

    audit_id = service.log_decision_audit(
        event_id="e1",
        decision_id="d1",
        market_type="spread",
        release_status="OFFICIAL",
        classification="EDGE",
        model_prob=0.61,
        edge_points=2.3,
        trace_id="t1",
        snapshot_hash="s1",
    )

    assert lifecycle_id
    assert audit_id
    assert len(collections["lifecycle"].docs) == 1
    assert len(collections["decision_audit"].docs) == 1
    assert collections["lifecycle"].docs[0]["trace_id"] == "t1"
    assert collections["lifecycle"].docs[0]["snapshot_hash"] == "s1"
    assert collections["decision_audit"].docs[0]["trace_id"] == "t1"
    assert collections["decision_audit"].docs[0]["snapshot_hash"] == "s1"


def test_settlement_truth_clv_and_drift_append_rows():
    service, collections = make_service()

    service.log_settlement_metrics(
        graded_id="g1",
        event_id="e1",
        prediction_id="p1",
        publish_id="pub1",
        result_code="WIN",
        bet_status="SETTLED",
        brier=0.04,
        logloss=0.22,
        ece_bucket_error=0.1,
        clv=1.5,
        p_predicted=0.8,
        actual_outcome=1,
        trace_id="t2",
        snapshot_hash="s2",
    )
    service.log_settlement_metrics(
        graded_id="g2",
        event_id="e2",
        prediction_id="p2",
        publish_id="pub2",
        result_code="LOSS",
        bet_status="SETTLED",
        brier=0.36,
        logloss=0.92,
        ece_bucket_error=0.6,
        clv=-0.8,
        p_predicted=0.6,
        actual_outcome=0,
        trace_id="t3",
        snapshot_hash="s3",
    )

    truth_id = service.log_truth_dataset_row(
        event_id="e1",
        prediction_id="p1",
        publish_id="pub1",
        graded_id="g1",
        feature_snapshot={"market_key": "SPREAD:FULL_GAME"},
        label={"result_code": "WIN", "actual_outcome": 1},
        trace_id="t2",
        snapshot_hash="s2",
    )

    clv_id = service.log_clv_capture(
        event_id="e1",
        prediction_id="p1",
        publish_id="pub1",
        graded_id="g1",
        entry_price=-110,
        closing_price=-105,
        clv=1.5,
        trace_id="t2",
        snapshot_hash="s2",
    )

    drift = service.run_drift_detection(
        baseline_metrics={"brier": 0.1, "logloss": 0.3, "ece": 0.12, "sample_count": 20.0},
        recent_rows=collections["settlement"].docs,
        threshold_delta=0.01,
        trace_id="t4",
        snapshot_hash="s4",
    )

    assert truth_id
    assert clv_id
    assert drift["drift_id"]
    assert len(collections["settlement"].docs) == 2
    assert len(collections["truth"].docs) == 1
    assert len(collections["clv"].docs) == 1
    assert len(collections["drift"].docs) == 1
    assert collections["drift"].docs[0]["trace_id"] == "t4"
    assert collections["drift"].docs[0]["snapshot_hash"] == "s4"
