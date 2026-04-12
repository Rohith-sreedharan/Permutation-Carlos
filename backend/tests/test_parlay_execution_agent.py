import services.parlay_execution_agent as execution_module
from services.parlay_execution_agent import ParlayExecutionAgent, BillingWriteFailure


class FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("event_id") or doc.get("charge_id") or "ok"})


class FakeBillingLedger:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.rows = []

    def append_ledger_entry(self, user_id, event_type, amount, reference_id):
        if self.should_fail:
            raise RuntimeError("write failed")
        row = {
            "id": "ledger_1",
            "user_id": user_id,
            "event_type": event_type,
            "amount": amount,
            "reference_id": reference_id,
            "created_at": "2026-03-19T00:00:00+00:00",
        }
        self.rows.append(row)
        return row


def test_log_execution_event_writes_append_only_execution_row():
    execution_log = FakeCollection()
    overage_log = FakeCollection()
    agent = ParlayExecutionAgent(
        execution_log_collection=execution_log,
        overage_log_collection=overage_log,
    )

    event_id = agent.log_execution_event(
        run_id="run_1",
        user_id="user_1",
        trace_id="trace_1",
        decision_id="decision_1",
        event_type="PARLAY_EXECUTED",
        payload={"legs": 4},
    )

    assert event_id
    assert len(execution_log.docs) == 1
    doc = execution_log.docs[0]
    assert doc["event_id"] == event_id
    assert doc["run_id"] == "run_1"
    assert doc["user_id"] == "user_1"
    assert doc["trace_id"] == "trace_1"
    assert doc["decision_id"] == "decision_1"
    assert doc["event_type"] == "PARLAY_EXECUTED"
    assert doc["payload"] == {"legs": 4}
    assert "created_at_utc" in doc


def test_log_overage_charge_writes_append_only_charge_row():
    execution_log = FakeCollection()
    overage_log = FakeCollection()
    agent = ParlayExecutionAgent(
        execution_log_collection=execution_log,
        overage_log_collection=overage_log,
    )

    charge_id = agent.log_overage_charge(
        parlay_run_id="run_2",
        user_id="user_2",
        trace_id="trace_2",
        billing_period_start="2026-03-01",
        token_shortfall=25,
        charge_usd=0.5,
    )

    assert charge_id
    assert len(overage_log.docs) == 1
    doc = overage_log.docs[0]
    assert doc["charge_id"] == charge_id
    assert doc["parlay_run_id"] == "run_2"
    assert doc["user_id"] == "user_2"
    assert doc["trace_id"] == "trace_2"
    assert doc["billing_period_start"] == "2026-03-01"
    assert doc["token_shortfall"] == 25
    assert doc["charge_usd"] == 0.5
    assert "created_at_utc" in doc


def test_enforce_billing_write_before_execution_logs_success(monkeypatch):
    execution_log = FakeCollection()
    overage_log = FakeCollection()
    agent = ParlayExecutionAgent(
        execution_log_collection=execution_log,
        overage_log_collection=overage_log,
    )
    ops_alert = FakeCollection()
    audit_log = FakeCollection()
    setattr(agent, "_ops_alert", ops_alert)
    setattr(agent, "_audit_log", audit_log)

    monkeypatch.setattr(execution_module, "billing_ledger_service", FakeBillingLedger(should_fail=False))

    ledger_id = agent.enforce_billing_write_before_execution(
        run_id="run_ok",
        user_id="user_ok",
        trace_id="trace_ok",
        amount=-1.0,
    )

    assert ledger_id == "ledger_1"
    assert any(doc["event_type"] == "BILLING_WRITE_OK" for doc in execution_log.docs)


def test_enforce_billing_write_before_execution_aborts_on_failure(monkeypatch):
    execution_log = FakeCollection()
    overage_log = FakeCollection()
    agent = ParlayExecutionAgent(
        execution_log_collection=execution_log,
        overage_log_collection=overage_log,
    )
    ops_alert = FakeCollection()
    audit_log = FakeCollection()
    setattr(agent, "_ops_alert", ops_alert)
    setattr(agent, "_audit_log", audit_log)

    monkeypatch.setattr(execution_module, "billing_ledger_service", FakeBillingLedger(should_fail=True))

    try:
        agent.enforce_billing_write_before_execution(
            run_id="run_fail",
            user_id="user_fail",
            trace_id="trace_fail",
            amount=-1.0,
        )
        assert False, "Expected BillingWriteFailure"
    except BillingWriteFailure:
        pass

    assert any(doc["event_type"] == "BILLING_WRITE_FAIL" for doc in execution_log.docs)
    assert len(ops_alert.docs) == 1
    assert ops_alert.docs[0]["type"] == "BILLING_WRITE_FAIL"
    assert len(audit_log.docs) == 1
    assert audit_log.docs[0]["reason_code"] == "BILLING_WRITE_FAIL"
