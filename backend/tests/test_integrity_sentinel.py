from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.integrity_sentinel import IntegritySentinel


class FakeUpdateResult:
    def __init__(self, modified_count=0, upserted_id=None):
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class FakeDeleteResult:
    def __init__(self, deleted_count=0):
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def _resolve_path(self, doc, dotted_key):
        current = doc
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _match_value(self, actual, expected):
        if isinstance(expected, dict):
            if "$exists" in expected:
                exists = actual is not None
                return exists == expected["$exists"]
            if "$gte" in expected and not (actual is not None and actual >= expected["$gte"]):
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            return True
        return actual == expected

    def _match(self, doc, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._match(doc, subquery) for subquery in value):
                    return False
                continue
            actual = self._resolve_path(doc, key)
            if not self._match_value(actual, value):
                return False
        return True

    def count_documents(self, query):
        return sum(1 for doc in self.docs if self._match(doc, query))

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc.get("id", "ok")})

    def find(self, query, projection=None):
        return [doc for doc in self.docs if self._match(doc, query)]

    def find_one(self, query, sort=None):
        docs = self.find(query)
        if sort:
            field, direction = sort[0]
            docs.sort(key=lambda doc: str(doc.get(field, "")), reverse=direction < 0)
        return docs[0] if docs else None

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if self._match(doc, query):
                doc.update(update.get("$set", {}))
                return FakeUpdateResult(modified_count=1)
        if upsert:
            doc = dict(query)
            doc.update(update.get("$set", {}))
            doc.update(update.get("$setOnInsert", {}))
            self.docs.append(doc)
            return FakeUpdateResult(modified_count=0, upserted_id="upserted")
        return FakeUpdateResult()

    def delete_many(self, query):
        kept = [doc for doc in self.docs if not self._match(doc, query)]
        deleted = len(self.docs) - len(kept)
        self.docs = kept
        return FakeDeleteResult(deleted_count=deleted)


class FakeDB:
    def __init__(self, collections):
        self._collections = collections

    def get_collection(self, name):
        return self._collections.setdefault(name, FakeCollection())

    def __getattr__(self, name):
        return self.get_collection(name)

    def __getitem__(self, name):
        return self.get_collection(name)


def test_integrity_metrics_use_canonical_observability_sources():
    recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    db = FakeDB(
        {
            "prediction_lifecycle_log": FakeCollection(
                docs=[
                    {"stage": "DECISION_COMPUTED", "timestamp": recent, "trace_id": "t1", "snapshot_hash": "s1"},
                    {"stage": "PUBLISHED", "timestamp": recent, "trace_id": "t2", "snapshot_hash": "s2"},
                    {"stage": "DISTRIBUTION_GOVERNANCE", "timestamp": recent, "trace_id": "", "snapshot_hash": "s3"},
                ]
            ),
            "decision_audit_log": FakeCollection(
                docs=[
                    {"timestamp": recent, "classification": "EDGE", "trace_id": "t1", "snapshot_hash": "s1"},
                    {"timestamp": recent, "classification": "NO_ACTION", "trace_id": "t2", "snapshot_hash": "s2"},
                ]
            ),
            "assertion_failure_log": FakeCollection(docs=[{"created_at_utc": recent, "code": "BROKEN"}]),
            "decision_records": FakeCollection(
                docs=[
                    {"created_at": recent, "payload": {"spread": {"selection_id": "sel_1"}, "total": None, "moneyline": None}},
                    {"created_at": recent, "payload": {"spread": {"selection_id": ""}, "total": None, "moneyline": None}},
                ]
            ),
            "odds_refresh_log": FakeCollection(docs=[{"refreshed_at": recent, "success": False}, {"refreshed_at": recent, "success": True}]),
            "telegram_post_log": FakeCollection(docs=[{"created_at": recent, "validation_failed": False}, {"created_at": recent, "validation_failed": True}]),
            "feature_flags": FakeCollection(),
            "sentinel_log": FakeCollection(),
            "ops_alerts": FakeCollection(),
            "rollback_log": FakeCollection(),
            "telegram_queue": FakeCollection(),
            "lkg_config": FakeCollection(),
        }
    )

    sentinel = IntegritySentinel(db)
    metrics = sentinel.check_all_metrics()

    assert round(metrics["integrity_violation_rate"].value, 4) == round(2 / 3, 4)
    assert round(metrics["missing_selection_id_rate"].value, 4) == 0.5
    assert round(metrics["missing_snapshot_hash_rate"].value, 4) == 0.0
    assert round(metrics["post_validation_fail_rate"].value, 4) == 0.5
    assert round(metrics["simulation_fetch_fail_rate"].value, 4) == 0.5
    assert metrics["edge_rate_collapse"].value >= 0.0


def test_check_cycle_triggers_disable_and_autorollback_when_enabled():
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    db = FakeDB(
        {
            "prediction_lifecycle_log": FakeCollection(docs=[{"stage": "DECISION_COMPUTED", "timestamp": recent, "trace_id": "", "snapshot_hash": ""}]),
            "decision_audit_log": FakeCollection(docs=[]),
            "assertion_failure_log": FakeCollection(docs=[{"created_at_utc": recent, "code": "ASSERT"}]),
            "decision_records": FakeCollection(docs=[]),
            "odds_refresh_log": FakeCollection(docs=[]),
            "telegram_post_log": FakeCollection(docs=[]),
            "feature_flags": FakeCollection(
                docs=[
                    {"flag_name": "FEATURE_AUTOROLLBACK_ON_INTEGRITY", "enabled": True},
                    {"flag_name": "FEATURE_TELEGRAM_AUTOPUBLISH", "enabled": True},
                ]
            ),
            "sentinel_log": FakeCollection(),
            "ops_alerts": FakeCollection(),
            "rollback_log": FakeCollection(),
            "telegram_queue": FakeCollection(docs=[{"created_at": datetime.now(timezone.utc)}]),
            "lkg_config": FakeCollection(
                docs=[
                    {
                        "config_id": "lkg_current",
                        "lkg_backend_image": "backend:test",
                        "lkg_frontend_build": "frontend:test",
                        "lkg_classifier_commit": "abc123",
                        "lkg_model_version": "model_v1",
                    }
                ]
            ),
        }
    )

    sentinel = IntegritySentinel(db)
    status = sentinel.run_check_cycle(enforce_actions=True)

    assert "integrity_violation_rate" in status["breaches"]
    assert any(action.startswith("DISABLED_TELEGRAM") for action in status["actions_taken"])
    assert any(action.startswith("AUTOROLLBACK_TRIGGERED") for action in status["actions_taken"])
    telegram_flag = next(doc for doc in db.feature_flags.docs if doc["flag_name"] == "FEATURE_TELEGRAM_AUTOPUBLISH")
    assert telegram_flag["enabled"] is False
    assert len(db.rollback_log.docs) == 1
    assert len(db.sentinel_log.docs) == 1


def test_latest_status_returns_most_recent_cycle():
    db = FakeDB({"sentinel_log": FakeCollection(docs=[{"timestamp": "2026-03-15T00:00:00"}, {"timestamp": "2026-03-15T00:00:01"}])})
    sentinel = IntegritySentinel(db)

    latest = sentinel.get_latest_status()

    assert latest is not None
    assert latest["timestamp"] == "2026-03-15T00:00:01"