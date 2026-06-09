"""
Phase 13 — Section 13.18: Subscriber Referral Program
======================================================
Subscribers earn rewards by sharing a personal referral QR code/link.
When a referred user subscribes, the referrer earns a reward and the
referred user receives a discounted trial.

Collections:
  subscriber_referral_links   — one per subscriber; referral_code + QR payload
  subscriber_referral_events  — fired on referred-user subscription
  subscriber_referral_rewards — pending/paid reward records
  payout_batch_items          — integrated with affiliate payout batch

Rules:
  - Each Platform subscriber has exactly one referral link (created on demand)
  - Reward: $10 account credit on referred user's first paid month
  - Auto-upgrade: referred user gets 30-day Platform trial (not just Telegram)
  - Payout batch picks up rewards in PENDING status
  - FTC: one reward per unique referred subscriber (card-fingerprint dedup)
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import qrcode  # type: ignore
import io
import base64

from db.mongo import db

logger = logging.getLogger(__name__)

_REWARD_AMOUNT_USD = float(os.getenv("P13_REFERRAL_REWARD_USD", "10.0"))       # default fallback
_REWARD_PLATFORM_USD = float(os.getenv("P13_REFERRAL_REWARD_PLATFORM_USD", "30.0"))   # Platform ($97/mo) referral
_REWARD_SYNDICATE_USD = float(os.getenv("P13_REFERRAL_REWARD_SYNDICATE_USD", "15.0"))  # Syndicate ($47/mo) referral
_TRIAL_DURATION_DAYS = int(os.getenv("P13_REFERRAL_TRIAL_DAYS", "30"))
_AUTO_UPGRADE_CONVERSION_THRESHOLD = int(os.getenv("P13_REFERRAL_UPGRADE_THRESHOLD", "5"))  # referrer tier upgrade at N conversions
_BASE_URL = os.getenv("FRONTEND_URL", os.getenv("VITE_BASE_URL", "https://beta.beatvegas.app"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Item 13.18.1 — Ensure DB collections exist (called during startup / on-demand)
# ─────────────────────────────────────────────────────────────────────────────

def ensure_referral_collections() -> None:
    """Create indexes for subscriber referral collections. Idempotent."""
    try:
        db["subscriber_referral_links"].create_index(
            [("user_id", 1)], unique=True, name="idx_srl_user_id", background=True
        )
        db["subscriber_referral_links"].create_index(
            [("referral_code", 1)], unique=True, name="idx_srl_code", background=True
        )
        db["subscriber_referral_events"].create_index(
            [("referral_code", 1), ("referred_user_id", 1)],
            unique=True,
            name="idx_sre_code_user",
            background=True,
        )
        db["subscriber_referral_events"].create_index(
            [("card_fingerprint", 1)], name="idx_sre_card_fp", background=True
        )
        db["subscriber_referral_rewards"].create_index(
            [("user_id", 1), ("status", 1)], name="idx_srr_user_status", background=True
        )
        db["subscriber_referral_rewards"].create_index(
            [("status", 1), ("created_at", -1)], name="idx_srr_status_date", background=True
        )
        db["payout_batch_items"].create_index(
            [("reward_id", 1)], unique=True, name="idx_pbi_reward_id", background=True
        )
        db["payout_batch_items"].create_index(
            [("status", 1), ("created_at", -1)], name="idx_pbi_status_date", background=True
        )
        logger.info("[Phase13.18] Subscriber referral indexes ensured")
    except Exception as exc:
        logger.warning("[Phase13.18] Index creation partial: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Item 13.18.3 — QR code generation
# ─────────────────────────────────────────────────────────────────────────────

def _generate_referral_code(user_id: str) -> str:
    """Deterministic referral code from user_id — stable across calls."""
    return hashlib.sha256(f"bvref:{user_id}".encode()).hexdigest()[:12].upper()


def get_or_create_referral_link(user_id: str) -> Dict[str, Any]:
    """
    Return existing referral link for the subscriber, or create one.
    Returns: referral_code, referral_url, qr_code_base64, created_at
    """
    existing = db["subscriber_referral_links"].find_one({"user_id": user_id})
    if existing:
        return {
            "referral_code": existing["referral_code"],
            "referral_url": existing["referral_url"],
            "qr_code_base64": existing.get("qr_code_base64", ""),
            "created_at": existing["created_at"],
        }

    referral_code = _generate_referral_code(user_id)
    referral_url = f"{_BASE_URL}/join/{referral_code}"

    # Generate QR code as base64 PNG
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(referral_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="white", back_color="#0c141f")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    now = _now_iso()
    doc = {
        "user_id": user_id,
        "referral_code": referral_code,
        "referral_url": referral_url,
        "qr_code_base64": qr_base64,
        "created_at": now,
        "updated_at": now,
    }
    db["subscriber_referral_links"].insert_one(doc)
    logger.info("[Phase13.18] Created referral link user=%s code=%s", user_id, referral_code)

    return {
        "referral_code": referral_code,
        "referral_url": referral_url,
        "qr_code_base64": qr_base64,
        "created_at": now,
    }


def get_referral_stats(user_id: str) -> Dict[str, Any]:
    """
    Return referral performance for dashboard panel.
    Items 13.18.2 (dashboard panel data).
    """
    total = db["subscriber_referral_events"].count_documents(
        {"referrer_user_id": user_id}
    )
    converted = db["subscriber_referral_events"].count_documents(
        {"referrer_user_id": user_id, "subscription_confirmed": True}
    )
    pending_rewards = db["subscriber_referral_rewards"].count_documents(
        {"user_id": user_id, "status": "PENDING"}
    )
    paid_rewards = db["subscriber_referral_rewards"].count_documents(
        {"user_id": user_id, "status": "PAID"}
    )
    total_earned_usd = (
        db["subscriber_referral_rewards"].aggregate([
            {"$match": {"user_id": user_id, "status": "PAID"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_usd"}}},
        ])
    )
    earned = next(total_earned_usd, {}).get("total", 0.0)

    return {
        "total_referred": total,
        "converted": converted,
        "pending_rewards": pending_rewards,
        "paid_rewards": paid_rewards,
        "total_earned_usd": round(earned, 2),
        "reward_per_conversion_usd": _REWARD_AMOUNT_USD,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Item 13.18.5 — Auto-upgrade trigger: when referred user subscribes,
# grant 30-day Platform trial and fire reward for referrer
# ─────────────────────────────────────────────────────────────────────────────

def process_referral_conversion(
    referral_code: str,
    referred_user_id: str,
    card_fingerprint: str,
    stripe_subscription_id: str,
    subscription_type: str = "platform",  # "platform" ($30) or "syndicate" ($15)
) -> Tuple[bool, str]:
    """
    Called when a referred user's subscription is confirmed (webhook).
    1. Validates referral code + dedup by card fingerprint
    2. Logs subscriber_referral_events entry
    3. Creates PENDING reward for referrer — $30 Platform, $15 Syndicate
    4. Queues payout_batch_items entry (Item 13.18.4)
    5. Grants auto-upgrade to referred user (Item 13.18.5)
    6. Checks referrer milestone: at 5 conversions → auto-upgrade referrer tier

    Returns (success: bool, reason: str)
    """
    link = db["subscriber_referral_links"].find_one({"referral_code": referral_code})
    if not link:
        return False, "INVALID_REFERRAL_CODE"

    referrer_user_id = link["user_id"]
    if referrer_user_id == referred_user_id:
        return False, "SELF_REFERRAL"

    # Card fingerprint dedup — prevent abuse from same card on multiple accounts
    existing_fp = db["subscriber_referral_events"].find_one(
        {"card_fingerprint": card_fingerprint, "subscription_confirmed": True}
    )
    if existing_fp:
        logger.warning(
            "[Phase13.18] Duplicate card fingerprint on referral: code=%s fp=%s",
            referral_code, card_fingerprint,
        )
        return False, "DUPLICATE_CARD_FINGERPRINT"

    # Check for existing event for this referred user
    existing_event = db["subscriber_referral_events"].find_one(
        {"referral_code": referral_code, "referred_user_id": referred_user_id}
    )
    if existing_event:
        return False, "ALREADY_PROCESSED"

    # Determine commission based on subscription type (Item 13.18.6: $30 Platform, $15 Syndicate)
    reward_amount = _REWARD_AMOUNT_USD  # fallback
    if subscription_type == "platform":
        reward_amount = _REWARD_PLATFORM_USD   # $30
    elif subscription_type == "syndicate":
        reward_amount = _REWARD_SYNDICATE_USD  # $15

    now = _now_iso()
    event_id = str(uuid.uuid4())
    reward_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    # Log referral event
    db["subscriber_referral_events"].insert_one({
        "event_id": event_id,
        "referral_code": referral_code,
        "referrer_user_id": referrer_user_id,
        "referred_user_id": referred_user_id,
        "card_fingerprint": card_fingerprint,
        "stripe_subscription_id": stripe_subscription_id,
        "subscription_confirmed": True,
        "created_at": now,
        "trace_id": trace_id,
    })

    # Create PENDING reward for referrer — amount depends on subscription tier
    db["subscriber_referral_rewards"].insert_one({
        "reward_id": reward_id,
        "user_id": referrer_user_id,
        "event_id": event_id,
        "referred_user_id": referred_user_id,
        "amount_usd": reward_amount,
        "subscription_type": subscription_type,
        "status": "PENDING",
        "created_at": now,
        "trace_id": trace_id,
    })

    # Integrate with payout batch (Item 13.18.4)
    db["payout_batch_items"].insert_one({
        "batch_item_id": str(uuid.uuid4()),
        "source": "SUBSCRIBER_REFERRAL",
        "reward_id": reward_id,
        "user_id": referrer_user_id,
        "amount_usd": reward_amount,
        "subscription_type": subscription_type,
        "status": "PENDING",
        "created_at": now,
        "trace_id": trace_id,
    })

    # Auto-upgrade: grant Platform trial to referred user (Item 13.18.5)
    _grant_referral_platform_trial(referred_user_id, referral_code, trace_id)

    # Item 13.18.7 — Referrer milestone: at N conversions, auto-upgrade referrer tier
    _check_referrer_milestone(referrer_user_id, trace_id)

    logger.info(
        "[Phase13.18] Referral conversion processed: referrer=%s referred=%s "
        "reward_id=%s amount=%.2f subscription_type=%s",
        referrer_user_id, referred_user_id, reward_id, reward_amount, subscription_type,
    )
    return True, "OK"


def _grant_referral_platform_trial(
    user_id: str, referral_code: str, trace_id: str
) -> None:
    """
    Auto-upgrade: set billing_state.platform_access=True for trial duration.
    The Stripe subscription webhook handles actual entitlement — this ensures
    the platform_access flag is set immediately without waiting for the webhook.
    """
    from datetime import timedelta
    trial_end = (
        datetime.now(timezone.utc) + timedelta(days=_TRIAL_DURATION_DAYS)
    ).isoformat()

    db["billing_state"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "platform_access": True,
                "telegram_access": True,
                "on_trial": True,
                "trial_source": "SUBSCRIBER_REFERRAL",
                "trial_referral_code": referral_code,
                "trial_ends_at": trial_end,
                "updated_at": _now_iso(),
            }
        },
        upsert=True,
    )
    logger.info("[Phase13.18] Auto-upgraded user=%s to Platform trial via referral", user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Item 13.18.7 — Referrer milestone: auto-upgrade referrer at N conversions
# ─────────────────────────────────────────────────────────────────────────────

def _check_referrer_milestone(referrer_user_id: str, trace_id: str) -> None:
    """
    Auto-upgrade trigger: when the referrer accumulates _AUTO_UPGRADE_CONVERSION_THRESHOLD
    confirmed conversions (default: 5), upgrade their Platform access for one free month.
    Fires once per milestone crossing — subsequent conversions beyond the threshold do not
    re-trigger the upgrade.
    """
    conversion_count = db["subscriber_referral_events"].count_documents(
        {"referrer_user_id": referrer_user_id, "subscription_confirmed": True}
    )

    if conversion_count != _AUTO_UPGRADE_CONVERSION_THRESHOLD:
        # Only fires exactly at the threshold — not on every conversion after
        return

    # Check if milestone upgrade was already granted to avoid re-triggering
    already_upgraded = db["subscriber_referral_rewards"].find_one(
        {"user_id": referrer_user_id, "reward_type": "MILESTONE_UPGRADE"}
    )
    if already_upgraded:
        logger.info(
            "[Phase13.18] Referrer milestone already processed for user=%s", referrer_user_id
        )
        return

    from datetime import timedelta
    trial_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    now = _now_iso()

    # Grant referrer a free Platform month
    db["billing_state"].update_one(
        {"user_id": referrer_user_id},
        {
            "$set": {
                "platform_access": True,
                "milestone_upgrade": True,
                "milestone_upgrade_source": "REFERRAL_5_CONVERSIONS",
                "milestone_upgrade_trace_id": trace_id,
                "milestone_upgrade_ends_at": trial_end,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    # Log milestone reward in subscriber_referral_rewards for audit trail
    db["subscriber_referral_rewards"].insert_one({
        "reward_id": str(uuid.uuid4()),
        "user_id": referrer_user_id,
        "reward_type": "MILESTONE_UPGRADE",
        "amount_usd": 0.0,          # non-cash reward (free Platform month)
        "description": f"Auto-upgrade: {_AUTO_UPGRADE_CONVERSION_THRESHOLD} referral conversions reached",
        "status": "PAID",           # immediate non-cash grant
        "created_at": now,
        "trace_id": trace_id,
    })

    logger.info(
        "[Phase13.18] Referrer milestone auto-upgrade fired: user=%s conversions=%d",
        referrer_user_id, conversion_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Item 13.18.6 — Payout batch processor: mark PENDING rewards as PAID
# Called by the payout batch job when processing subscriber referral rewards
# ─────────────────────────────────────────────────────────────────────────────

def process_referral_payout_batch() -> Dict[str, Any]:
    """
    Mark all eligible PENDING subscriber referral rewards as PAID.
    Eligibility: referred user's subscription is >= 30 days old (first paid period confirmed).
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    eligible = list(
        db["subscriber_referral_rewards"].find(
            {"status": "PENDING", "created_at": {"$lte": cutoff}}
        )
    )
    processed = 0
    for reward in eligible:
        db["subscriber_referral_rewards"].update_one(
            {"reward_id": reward["reward_id"]},
            {"$set": {"status": "PAID", "paid_at": _now_iso()}},
        )
        db["payout_batch_items"].update_one(
            {"reward_id": reward["reward_id"]},
            {"$set": {"status": "PAID", "processed_at": _now_iso()}},
        )
        processed += 1

    logger.info("[Phase13.18] Payout batch processed %d subscriber referral rewards", processed)
    return {"processed": processed, "eligible": len(eligible)}
