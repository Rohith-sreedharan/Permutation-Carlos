from db.decision_record_store import DecisionRecordStore
from core.market_decision import GameDecisions


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self):
        self.docs = []

    def create_index(self, *args, **kwargs):
        return None

    def find_one(self, query, projection=None):
        for doc in self.docs:
            ok = True
            for k, v in query.items():
                if doc.get(k) != v:
                    ok = False
                    break
            if ok:
                if projection:
                    projected = {}
                    for key, include in projection.items():
                        if include and key in doc:
                            projected[key] = doc[key]
                    return projected
                return doc
        return None

    def insert_one(self, doc):
        # Emulate unique identity_key constraint.
        for existing in self.docs:
            if existing.get("identity_key") == doc.get("identity_key"):
                raise Exception("duplicate key")
        self.docs.append(doc)
        return FakeInsertResult(inserted_id=doc["record_id"])


def make_decisions() -> GameDecisions:
    return GameDecisions(
        spread=None,
        moneyline=None,
        total=None,
        decision_record_id=None,
        home_team_name="Home",
        away_team_name="Away",
        inputs_hash="abc123",
        decision_version="1.0.0",
        computed_at="2026-01-01T00:00:00+00:00",
    )


def test_compute_identity_key_is_stable():
    key1 = DecisionRecordStore.compute_identity_key("NBA", "game_1", "h1", "1.0.0")
    key2 = DecisionRecordStore.compute_identity_key("NBA", "game_1", "h1", "1.0.0")
    key3 = DecisionRecordStore.compute_identity_key("NBA", "game_2", "h1", "1.0.0")
    assert key1 == key2
    assert key1 != key3


def test_persist_game_decisions_is_idempotent_for_same_bundle():
    fake = FakeCollection()
    store = DecisionRecordStore(collection=fake)
    decisions = make_decisions()

    record_id_1 = store.persist_game_decisions(
        league="NBA",
        game_id="game_1",
        odds_event_id="odds_event_game_1",
        decisions=decisions,
    )
    record_id_2 = store.persist_game_decisions(
        league="NBA",
        game_id="game_1",
        odds_event_id="odds_event_game_1",
        decisions=decisions,
    )

    assert record_id_1 == record_id_2
    assert len(fake.docs) == 1


def test_get_record_payload_returns_persisted_bundle():
    fake = FakeCollection()
    store = DecisionRecordStore(collection=fake)
    decisions = make_decisions()

    record_id = store.persist_game_decisions(
        league="NBA",
        game_id="game_1",
        odds_event_id="odds_event_game_1",
        decisions=decisions,
    )

    payload = store.get_record_payload(record_id)
    assert payload is not None
    assert payload["inputs_hash"] == "abc123"
    assert payload["decision_version"] == "1.0.0"
