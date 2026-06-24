from services.distribution_governance_service import DistributionGovernanceService


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, docs=None, fail_counts=False):
        self.docs = docs or []
        self.fail_counts = fail_counts

    def create_index(self, *args, **kwargs):
        return None

    def _match(self, doc, query):
        def resolve_path(obj, dotted_key):
            current = obj
            for part in dotted_key.split("."):
                if not isinstance(current, dict) or part not in current:
                    return None
                current = current[part]
            return current

        for key, value in query.items():
            if key == "$or":
                if not any(self._match(doc, subq) for subq in value):
                    return False
                continue
            if isinstance(value, dict) and "$in" in value:
                if resolve_path(doc, key) not in value["$in"]:
                    return False
                continue
            if resolve_path(doc, key) != value:
                return False
        return True

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                if projection:
                    projected = {}
                    for key, include in projection.items():
                        if include and key in doc:
                            projected[key] = doc[key]
                    return projected
                return doc
        return None

    def insert_one(self, doc):
        if any(existing.get("decision_id") == doc.get("decision_id") for existing in self.docs if "decision_id" in doc):
            raise Exception("duplicate key")
        self.docs.append(doc)
        return FakeInsertResult(inserted_id=doc.get("distribution_id") or doc.get("assertion_id") or "ok")

    def count_documents(self, query):
        if self.fail_counts:
            raise Exception("count query unavailable")
        return sum(1 for doc in self.docs if self._match(doc, query))


def make_decision_record(decision_id: str, release_status: str = "OFFICIAL", classification: str = "EDGE", model_prob: float = 0.62):
    return {
        "league": "NBA",
        "game_id": "game_123",
        "payload": {
            "inputs_hash": "hash_abc",
            "home_team_name": "Lakers",
            "away_team_name": "Celtics",
            "spread": {
                "decision_id": decision_id,
                "market_type": "SPREAD",
                "classification": classification,
                "release_status": release_status,
                "probabilities": {"model_prob": model_prob},
                "edge": {"edge_points": 2.1},
            },
            "total": None,
            "moneyline": None,
        },
    }


def test_distribution_rule_blocks_non_eligible_release_status():
    decision_records = FakeCollection(docs=[make_decision_record("d1", release_status="BLOCKED_BY_RISK")])
    distribution_log = FakeCollection(docs=[])
    lifecycle_log = FakeCollection(docs=[])
    assertion_log = FakeCollection(docs=[])

    service = DistributionGovernanceService(
        distribution_collection=distribution_log,
        decision_record_collection=decision_records,
        lifecycle_collection=lifecycle_log,
        assertion_collection=assertion_log,
    )

    result = service.evaluate(decision_id="d1", trace_id="t1")

    assert result.distribution_category == "WITHHELD_EDGE"
    assert result.rule_applied == "BLOCKED_RELEASE_STATUS"
    assert result.withheld_reason == "BLOCKED_RELEASE_STATUS"


def test_distribution_rule_routes_no_action_to_analysis_only():
    decision_records = FakeCollection(docs=[make_decision_record("d2", classification="NO_ACTION")])
    distribution_log = FakeCollection(docs=[])

    service = DistributionGovernanceService(
        distribution_collection=distribution_log,
        decision_record_collection=decision_records,
        lifecycle_collection=FakeCollection(docs=[]),
        assertion_collection=FakeCollection(docs=[]),
    )

    result = service.evaluate(decision_id="d2", trace_id="t2")

    assert result.distribution_category == "ANALYSIS_ONLY"
    assert result.rule_applied == "NO_ACTION_CLASSIFICATION"


def test_distribution_rule_fails_closed_when_count_query_fails():
    decision_records = FakeCollection(docs=[make_decision_record("d3")])
    distribution_log = FakeCollection(docs=[], fail_counts=True)
    assertion_log = FakeCollection(docs=[])

    service = DistributionGovernanceService(
        distribution_collection=distribution_log,
        decision_record_collection=decision_records,
        lifecycle_collection=FakeCollection(docs=[]),
        assertion_collection=assertion_log,
    )

    result = service.evaluate(decision_id="d3", trace_id="t3")

    assert result.distribution_category == "WITHHELD_EDGE"
    assert result.rule_applied == "DAILY_COUNT_QUERY_FAILED"
    assert len(assertion_log.docs) == 1
    assert assertion_log.docs[0]["code"] == "DAILY_COUNT_QUERY_FAILED"


def test_distribution_is_idempotent_per_decision_id():
    decision_records = FakeCollection(docs=[make_decision_record("d4")])
    distribution_log = FakeCollection(docs=[])

    service = DistributionGovernanceService(
        distribution_collection=distribution_log,
        decision_record_collection=decision_records,
        lifecycle_collection=FakeCollection(docs=[]),
        assertion_collection=FakeCollection(docs=[]),
    )

    first = service.evaluate(decision_id="d4", trace_id="t4")
    second = service.evaluate(decision_id="d4", trace_id="t4")

    assert first.decision_id == second.decision_id
    assert second.already_exists is True
    assert len(distribution_log.docs) == 1
