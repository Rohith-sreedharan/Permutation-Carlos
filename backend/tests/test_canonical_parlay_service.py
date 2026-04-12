from services.canonical_parlay_service import CanonicalParlayService


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, _n):
        return self._docs


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, _query):
        return FakeCursor(self.docs)

    def find_one(self, query):
        for doc in self.docs:
            payload = doc.get("payload", {})
            for market in ("spread", "total", "moneyline"):
                decision = payload.get(market)
                if not decision:
                    continue
                target = query["$or"][0].get(f"payload.{market}.decision_id")
                if target and decision.get("decision_id") == target:
                    return doc
                for branch in query["$or"]:
                    key = f"payload.{market}.decision_id"
                    if branch.get(key) and decision.get("decision_id") == branch[key]:
                        return doc
        return None


def _doc(decision_id: str, snapshot_hash: str = "snap_1"):
    return {
        "event_id": "event_1",
        "league": "NBA",
        "payload": {
            "inputs_hash": snapshot_hash,
            "spread": {
                "decision_id": decision_id,
                "release_status": "OFFICIAL",
                "classification": "EDGE",
                "di_pass": True,
                "mv_pass": True,
                "market_type": "SPREAD",
                "pick": {"team_name": "HOME"},
                "market": {"line": -4.5, "odds": -110},
                "probabilities": {"model_prob": 0.57},
            },
        },
    }


def test_get_candidate_legs_returns_only_canonical_contract_rows():
    docs = [_doc("d1")]
    service = CanonicalParlayService(decision_records_collection=FakeCollection(docs))

    legs = service.get_candidate_legs(sports=["NBA"], limit=20)

    assert len(legs) == 1
    leg = legs[0]
    assert leg["decision_id"] == "d1"
    assert leg["snapshot_hash"] == "snap_1"
    assert leg["canonical_state"] == "EDGE"
    assert leg["true_probability"] == 0.57
    assert leg["american_odds"] == -110


def test_get_candidate_legs_rejects_missing_snapshot_hash():
    docs = [_doc("d2", snapshot_hash="")]
    service = CanonicalParlayService(decision_records_collection=FakeCollection(docs))

    legs = service.get_candidate_legs(limit=20)
    assert legs == []


def test_resolve_decision_ids_fails_fast_on_invalid_id():
    docs = [_doc("d3")]
    service = CanonicalParlayService(decision_records_collection=FakeCollection(docs))

    try:
        service.resolve_decision_ids(["missing_id"])
        assert False, "Expected KeyError"
    except KeyError as exc:
        assert "invalid decision_id" in str(exc)
