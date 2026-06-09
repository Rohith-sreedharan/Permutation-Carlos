"""
Phase 13 Migration 001 — promo_tokens Trial System Schema Additions
====================================================================
Adds four new fields to the promo_tokens collection (MongoDB) required
for the 3-day affiliate trial system.

New fields:
  trial_source              Enum: QR_PROMO | AFFILIATE_REFERRAL | SUBSCRIBER_REFERRAL
  trial_duration_hours      Integer — controls Stripe trial_period_days
  payment_method_fingerprint  String — Stripe PM fingerprint for cross-trial dedup
  device_fingerprint        String — browser fingerprint at token generation time

Run:
  cd backend && python -m db.migrations.phase13_001_promo_tokens_trial_fields

Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from db.mongo import db

logger = logging.getLogger(__name__)

MIGRATION_ID = "phase13_001_promo_tokens_trial_fields"
COLLECTION = "promo_tokens"

# Valid trial_source values
TRIAL_SOURCE_VALUES = ("QR_PROMO", "AFFILIATE_REFERRAL", "SUBSCRIBER_REFERRAL")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _already_applied() -> bool:
    """Check migration log for idempotency."""
    return db["migration_log"].find_one({"migration_id": MIGRATION_ID}) is not None


def run() -> Dict[str, Any]:
    """
    Apply schema additions to promo_tokens collection.
    Sets default values on all existing documents that lack the new fields.
    Builds indexes required for deduplication queries.
    """
    if _already_applied():
        logger.info("[Migration] %s already applied — skipping", MIGRATION_ID)
        return {"status": "already_applied", "migration_id": MIGRATION_ID}

    results: Dict[str, Any] = {
        "migration_id": MIGRATION_ID,
        "timestamp": _now_iso(),
        "steps": [],
    }

    # ── Step 1: Backfill existing documents with default values ──────────────
    # All existing tokens are QR_PROMO (the only trial type before Phase 13).
    backfill_result = db[COLLECTION].update_many(
        {"trial_source": {"$exists": False}},
        {
            "$set": {
                "trial_source": "QR_PROMO",
                "trial_duration_hours": 24,  # Default: QR = 24h
                "payment_method_fingerprint": None,
                "device_fingerprint": None,
            }
        },
    )
    results["steps"].append({
        "step": "backfill_existing_tokens",
        "matched": backfill_result.matched_count,
        "modified": backfill_result.modified_count,
    })
    logger.info(
        "[Migration] backfilled %d promo_tokens with trial_source=QR_PROMO",
        backfill_result.modified_count,
    )

    # ── Step 2: Create indexes for deduplication queries ─────────────────────
    # Dedup by email: promo_tokens where stripe_customer_id matches + redeemed=true
    # Dedup by card:  promo_tokens where payment_method_fingerprint matches + redeemed=true

    try:
        db[COLLECTION].create_index(
            [("payment_method_fingerprint", 1), ("redeemed", 1)],
            name="idx_promo_tokens_pm_fingerprint_redeemed",
            sparse=True,  # Skip docs where fingerprint is null
            background=True,
        )
        results["steps"].append({"step": "create_index_pm_fingerprint", "status": "ok"})
    except Exception as exc:
        results["steps"].append({"step": "create_index_pm_fingerprint", "status": "exists_or_error", "detail": str(exc)[:200]})

    try:
        db[COLLECTION].create_index(
            [("trial_source", 1), ("redeemed", 1)],
            name="idx_promo_tokens_trial_source_redeemed",
            background=True,
        )
        results["steps"].append({"step": "create_index_trial_source", "status": "ok"})
    except Exception as exc:
        results["steps"].append({"step": "create_index_trial_source", "status": "exists_or_error", "detail": str(exc)[:200]})

    try:
        db[COLLECTION].create_index(
            [("device_fingerprint", 1)],
            name="idx_promo_tokens_device_fingerprint",
            sparse=True,
            background=True,
        )
        results["steps"].append({"step": "create_index_device_fingerprint", "status": "ok"})
    except Exception as exc:
        results["steps"].append({"step": "create_index_device_fingerprint", "status": "exists_or_error", "detail": str(exc)[:200]})

    # ── Step 3: Create promo_scans collection index for DEVICE_MISMATCH ──────
    try:
        db["promo_scans"].create_index(
            [("token_id", 1), ("event_type", 1), ("created_at", -1)],
            name="idx_promo_scans_token_event",
            background=True,
        )
        results["steps"].append({"step": "create_promo_scans_index", "status": "ok"})
    except Exception as exc:
        results["steps"].append({"step": "create_promo_scans_index", "status": "exists_or_error", "detail": str(exc)[:200]})

    # ── Step 4: Create promo_scans index for CARD_AUTH_FAILED queries ────────
    # promo_tokens valid status values: pending | redeemed | expired |
    #   CARD_AUTH_FAILED (new — Phase 13 card authorization failure)
    try:
        db["promo_scans"].create_index(
            [("blocked_reason", 1), ("created_at", -1)],
            name="idx_promo_scans_blocked_reason_date",
            background=True,
        )
        db["promo_scans"].create_index(
            [("stripe_customer_id", 1), ("blocked_reason", 1)],
            name="idx_promo_scans_customer_block",
            background=True,
        )
        results["steps"].append({"step": "create_promo_scans_card_auth_indexes", "status": "ok"})
    except Exception as exc:
        results["steps"].append({"step": "create_promo_scans_card_auth_indexes", "status": "exists_or_error", "detail": str(exc)[:200]})

    # ── Step 5: Create affiliate_trial_subscriptions collection for trial tracking
    try:
        db["affiliate_trial_subscriptions"].create_index(
            [("stripe_customer_id", 1)],
            name="idx_aff_trial_customer",
            unique=True,
            background=True,
        )
        db["affiliate_trial_subscriptions"].create_index(
            [("affiliate_id", 1), ("trial_starts_at", -1)],
            name="idx_aff_trial_affiliate_date",
            background=True,
        )
        db["affiliate_trial_subscriptions"].create_index(
            [("trial_ends_at", 1), ("status", 1)],
            name="idx_aff_trial_ends_status",
            background=True,
        )
        results["steps"].append({"step": "create_affiliate_trial_subscriptions_indexes", "status": "ok"})
    except Exception as exc:
        results["steps"].append({"step": "create_affiliate_trial_subscriptions_indexes", "status": "exists_or_error", "detail": str(exc)[:200]})

    # ── Step 5: Mark migration as applied ─────────────────────────────────────
    db["migration_log"].insert_one({
        "migration_id": MIGRATION_ID,
        "applied_at": _now_iso(),
        "results": results,
    })
    results["status"] = "applied"
    logger.info("[Migration] %s applied successfully", MIGRATION_ID)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    import json
    print(json.dumps(result, indent=2, default=str))
