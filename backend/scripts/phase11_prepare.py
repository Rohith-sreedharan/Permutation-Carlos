"""
Phase 11 preparation script.

- Ensures indexes
- Ensures affiliate_attributions is immutable (time-series collection)
- Ensures invite-only mode seed config
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from db.mongo import db, ensure_indexes  # noqa: E402


def ensure_affiliate_attributions_immutable() -> str:
    names = db.list_collection_names()
    migrated_from_timeseries = False

    if "affiliate_attributions" in names:
        info = db.command({"listCollections": 1, "filter": {"name": "affiliate_attributions"}})
        first = info.get("cursor", {}).get("firstBatch", [])
        opts = first[0].get("options", {}) if first else {}
        if "timeseries" in opts:
            db["affiliate_attributions"].drop()
            migrated_from_timeseries = True
            names = db.list_collection_names()

    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "attribution_id",
                "affiliate_id",
                "click_id",
                "user_id",
                "locked_at_utc",
                "immutable_guard",
                "trace_id",
                "tenant_id",
            ],
            "properties": {
                "attribution_id": {"bsonType": "string"},
                "affiliate_id": {"bsonType": "string"},
                "click_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "locked_at_utc": {"bsonType": "string"},
                "immutable_guard": {"enum": ["LOCKED"]},
                "trace_id": {"bsonType": "string"},
                "tenant_id": {"bsonType": ["null", "string"]},
            },
        }
    }

    if "affiliate_attributions" not in names:
        db.create_collection("affiliate_attributions", validator=validator)
    else:
        db.command({"collMod": "affiliate_attributions", "validator": validator})

    db["affiliate_attributions"].create_index([("attribution_id", 1)], unique=True)
    db["affiliate_attributions"].create_index([("user_id", 1)], unique=True)
    db["affiliate_attributions"].create_index([("affiliate_id", 1), ("locked_at_utc", -1)])
    return "migrated_from_timeseries_validator_guard_applied" if migrated_from_timeseries else "validator_guard_applied"


def seed_affiliate_program_config() -> None:
    db["affiliate_program_config"].update_one(
        {"config_id": "phase11_program"},
        {
            "$set": {
                "config_id": "phase11_program",
                "access_mode": "INVITE_ONLY",
                "open_enrollment_enabled": False,
                "open_enrollment_eligible_after_days": 90,
            }
        },
        upsert=True,
    )


def ensure_workstream10_indexes() -> None:
    db["affiliate_interest_log"].create_index([("interest_id", 1)], unique=True)
    db["affiliate_interest_log"].create_index([("status", 1), ("submitted_at_utc", -1)])
    db["affiliate_accounts"].create_index([("status", 1), ("leaderboard_opt_out", 1)])
    db["users"].create_index([("tier", 1), ("created_at", 1), ("has_seen_affiliate_popup", 1)])


def main() -> None:
    db.client.admin.command("ping")
    ensure_indexes()
    immutable_state = ensure_affiliate_attributions_immutable()
    seed_affiliate_program_config()
    ensure_workstream10_indexes()

    print("=== PHASE 11 PREP ===")
    print(f"affiliate_attributions: {immutable_state}")
    print("affiliate_program_config: seeded")
    print("workstream10_indexes: ensured")


if __name__ == "__main__":
    main()
