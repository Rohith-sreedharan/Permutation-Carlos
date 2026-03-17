from services.billing_state_service import BillingStateService


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return dict(doc)
        return None

    def update_one(self, query, update, upsert=False):
        doc = self.find_one(query)
        if doc is not None:
            doc.update(update.get("$set", {}))
            return
        if upsert:
            new_doc = dict(query)
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("change_id", "ok")})


def test_upsert_state_writes_state_and_change_log_per_changed_field():
    billing_state = FakeCollection(
        docs=[
            {
                "user_id": "user_1",
                "plan_id": "telegram_syndicate",
                "platform_access": False,
            }
        ]
    )
    change_log = FakeCollection()
    service = BillingStateService(
        billing_state_collection=billing_state,
        change_log_collection=change_log,
    )

    next_state = service.upsert_state(
        user_id="user_1",
        updates={
            "plan_id": "beatvegas_platform",
            "platform_access": True,
            "telegram_access": True,
        },
        trace_id="trace_123",
    )

    assert next_state["user_id"] == "user_1"
    assert next_state["plan_id"] == "beatvegas_platform"
    assert next_state["platform_access"] is True
    assert next_state["telegram_access"] is True
    assert "updated_at_utc" in next_state
    assert len(change_log.docs) == 3
    changed_fields = {doc["field_changed"] for doc in change_log.docs}
    assert changed_fields == {"plan_id", "platform_access", "telegram_access"}
    assert all(doc["trace_id"] == "trace_123" for doc in change_log.docs)


def test_upsert_state_does_not_log_unchanged_fields():
    billing_state = FakeCollection(
        docs=[
            {
                "user_id": "user_2",
                "plan_id": "beatvegas_platform",
                "platform_access": True,
            }
        ]
    )
    change_log = FakeCollection()
    service = BillingStateService(
        billing_state_collection=billing_state,
        change_log_collection=change_log,
    )

    next_state = service.upsert_state(
        user_id="user_2",
        updates={
            "plan_id": "beatvegas_platform",
            "platform_access": True,
        },
        trace_id="trace_same",
    )

    assert next_state["user_id"] == "user_2"
    assert len(change_log.docs) == 0
