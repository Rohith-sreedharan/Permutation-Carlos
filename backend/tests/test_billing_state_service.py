from services.billing_state_service import BillingLedgerService


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.indexes = []

    def create_index(self, *args, **kwargs):
        self.indexes.append((args, kwargs))

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("id", "ok")})

    def aggregate(self, pipeline):
        user_id = pipeline[0]["$match"]["user_id"]
        balance = sum(float(doc.get("amount", 0.0)) for doc in self.docs if doc.get("user_id") == user_id)
        if not any(doc.get("user_id") == user_id for doc in self.docs):
            return []
        return [{"_id": None, "balance": balance}]


def test_append_ledger_entry_writes_required_contract_fields():
    ledger = FakeCollection()
    service = BillingLedgerService(ledger_collection=ledger)

    row = service.append_ledger_entry(
        user_id="user_1",
        event_type="usage",
        amount=-1.25,
        reference_id="run_123",
    )

    assert row["id"]
    assert row["user_id"] == "user_1"
    assert row["event_type"] == "USAGE"
    assert row["amount"] == -1.25
    assert row["reference_id"] == "run_123"
    assert "created_at" in row
    assert len(ledger.docs) == 1


def test_get_derived_balance_sums_ledger_without_mutable_state():
    ledger = FakeCollection()
    service = BillingLedgerService(ledger_collection=ledger)

    service.append_ledger_entry(user_id="user_2", event_type="CREDIT", amount=10.0, reference_id="credit_1")
    service.append_ledger_entry(user_id="user_2", event_type="USAGE", amount=-2.5, reference_id="run_1")
    service.append_ledger_entry(user_id="user_2", event_type="CHARGE", amount=-1.5, reference_id="run_2")

    assert service.get_derived_balance("user_2") == 6.0
    assert service.get_derived_balance("unknown_user") == 0.0


def test_append_ledger_entry_rejects_invalid_event_type():
    ledger = FakeCollection()
    service = BillingLedgerService(ledger_collection=ledger)

    try:
        service.append_ledger_entry(
            user_id="user_3",
            event_type="MUTATE",
            amount=1.0,
            reference_id="bad",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "event_type" in str(exc)
