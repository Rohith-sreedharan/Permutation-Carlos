"""
Phase 10 shell preparation.

Applies the minimal beta shell infrastructure required for SimSports B2B readiness:
- tenant collection schema validator + indexes
- tenant_id backfill for required audit collections
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from config.phase10_tenant_shell import (  # noqa: E402
    ENTITLEMENT_TYPE_ENUM,
    PHASE10_AUDIT_COLLECTIONS,
    REQUIRED_TENANT_FIELDS,
    TENANT_STATUS_ENUM,
    TENANT_TYPE_ENUM,
)
from db.mongo import db, ensure_indexes  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_tenant_validator() -> None:
    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": REQUIRED_TENANT_FIELDS,
            "properties": {
                "tenant_id": {"bsonType": "string"},
                "tenant_type": {"enum": TENANT_TYPE_ENUM},
                "entitlement_type": {"enum": ENTITLEMENT_TYPE_ENUM},
                "status": {"enum": TENANT_STATUS_ENUM},
                "rate_limit_tier": {"bsonType": ["string", "null"]},
                "api_key_hash": {"bsonType": ["string", "null"]},
                "created_at_utc": {"bsonType": "string"},
                "updated_at_utc": {"bsonType": "string"},
                "custom_thresholds": {"bsonType": "object"},
                "trace_id": {"bsonType": "string"},
            },
        }
    }

    names = db.list_collection_names()
    if "tenants" not in names:
        db.create_collection("tenants", validator=validator)
    else:
        db.command({"collMod": "tenants", "validator": validator})


def seed_consumer_shell_tenant() -> None:
    doc = {
        "tenant_id": "consumer_default",
        "tenant_type": "CONSUMER",
        "entitlement_type": "B2C_PLATFORM",
        "status": "ACTIVE",
        "rate_limit_tier": "platform_default",
        "api_key_hash": None,
        "created_at_utc": now_iso(),
        "updated_at_utc": now_iso(),
        "custom_thresholds": {},
        "trace_id": str(uuid4()),
    }
    db["tenants"].update_one(
        {"tenant_id": "consumer_default"},
        {"$set": doc},
        upsert=True,
    )


def backfill_tenant_id_fields() -> dict:
    results = {}
    for collection in PHASE10_AUDIT_COLLECTIONS:
        result = db[collection].update_many(
            {"tenant_id": {"$exists": False}},
            {"$set": {"tenant_id": None}},
        )
        results[collection] = int(result.modified_count)
    return results


def ensure_phase10_indexes() -> None:
    db["tenants"].create_index([("tenant_id", 1)], unique=True)
    db["tenants"].create_index([("tenant_type", 1), ("status", 1)])
    db["tenants"].create_index([("entitlement_type", 1), ("status", 1)])

    for collection in PHASE10_AUDIT_COLLECTIONS:
        db[collection].create_index([("tenant_id", 1)])


def main() -> None:
    ensure_indexes()
    ensure_tenant_validator()
    ensure_phase10_indexes()
    seed_consumer_shell_tenant()
    updated = backfill_tenant_id_fields()

    print("=== PHASE 10 SHELL PREP ===")
    print("tenant_validator: APPLIED")
    print("tenant_seed: consumer_default upserted")
    print("tenant_id_backfill:", updated)


if __name__ == "__main__":
    main()
