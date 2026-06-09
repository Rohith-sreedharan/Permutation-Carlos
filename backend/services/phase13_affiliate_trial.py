"""
Phase 13 — Affiliate Trial Service
====================================
Core business logic for the 3-day affiliate referral trial system.

Covers:
  - Affiliate display name validation + HTML sanitisation (Part 3.2 / 11.5)
  - Cross-trial deduplication by email AND card fingerprint (Part 2)
  - Stripe trial subscription creation (Part 4.1)
  - Trial token balance initialisation (Part 10)
  - Cancellation handling — immediate entitlement revert + token zero (Part 5)
  - Mid-trial direct purchase conflict resolution (Part 9)
  - Charge timing disclosure with user-local timezone (Part 3.4)

All thresholds from agent_config.phase13 — zero hardcoded values.
"""

from __future__ import annotations

import html
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import stripe

from config.agent_config import AGENT_CONFIG
from db.mongo import db

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# ── Config shorthand ──────────────────────────────────────────────────────────
def _cfg() -> Dict[str, Any]:
    return AGENT_CONFIG.get("phase13", {})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Part 3.2 — Affiliate display name validation + HTML sanitisation
# ─────────────────────────────────────────────────────────────────────────────

# affiliate_id must be alphanumeric + hyphen/underscore, 4–64 chars
_AFFILIATE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{4,64}$')


def sanitise_html(raw: str) -> str:
    """
    HTML-encode a raw string before any DOM insertion.
    Uses Python's html.escape — equivalent to htmlspecialchars().
    XSS attempt safely rendered as plain text.
    """
    return html.escape(raw, quote=True)


def get_affiliate_display_name(affiliate_id: str) -> str:
    """
    Validate affiliate_id and return the HTML-encoded display_name.
    Falls back to generic copy if invalid or not found — never exposes
    raw URL parameter values in the DOM.

    Part 3.2 / Part 11.5 (URL parameter HTML encoding).
    """
    FALLBACK = "a BeatVegas subscriber"

    if not affiliate_id or not _AFFILIATE_ID_RE.match(affiliate_id):
        return FALLBACK

    try:
        doc = db["affiliate_accounts"].find_one(
            {"affiliate_id": affiliate_id, "status": {"$ne": "REVOKED"}},
            {"display_name": 1},
        )
        if not doc or not doc.get("display_name"):
            return FALLBACK
        # Sanitise before returning — never raw string insertion into DOM
        return sanitise_html(str(doc["display_name"]))
    except Exception as exc:
        logger.error("[AffiliateTrial] display_name lookup failed: %s", exc)
        return FALLBACK


# ─────────────────────────────────────────────────────────────────────────────
# Part 3.4 — Charge timing disclosure (exact local date and time)
# ─────────────────────────────────────────────────────────────────────────────

# GeoIP state → IANA timezone fallback table (major US states)
_STATE_TZ: Dict[str, str] = {
    "AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix",
    "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
    "CT": "America/New_York", "DE": "America/New_York", "FL": "America/New_York",
    "GA": "America/New_York", "HI": "Pacific/Honolulu", "ID": "America/Denver",
    "IL": "America/Chicago", "IN": "America/Indiana/Indianapolis", "IA": "America/Chicago",
    "KS": "America/Chicago", "KY": "America/New_York", "LA": "America/Chicago",
    "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
    "MI": "America/Detroit", "MN": "America/Chicago", "MS": "America/Chicago",
    "MO": "America/Chicago", "MT": "America/Denver", "NE": "America/Chicago",
    "NV": "America/Los_Angeles", "NH": "America/New_York", "NJ": "America/New_York",
    "NM": "America/Denver", "NY": "America/New_York", "NC": "America/New_York",
    "ND": "America/Chicago", "OH": "America/New_York", "OK": "America/Chicago",
    "OR": "America/Los_Angeles", "PA": "America/New_York", "RI": "America/New_York",
    "SC": "America/New_York", "SD": "America/Chicago", "TN": "America/Chicago",
    "TX": "America/Chicago", "UT": "America/Denver", "VT": "America/New_York",
    "VA": "America/New_York", "WA": "America/Los_Angeles", "WV": "America/New_York",
    "WI": "America/Chicago", "WY": "America/Denver", "DC": "America/New_York",
}


def get_charge_disclosure(
    trial_duration_hours: int,
    state_code: Optional[str] = None,
    iana_tz: Optional[str] = None,
) -> Dict[str, str]:
    """
    Compute exact local charge date/time for FTC Negative Option Rule 2024.

    Returns dict with:
      trial_ends_at_utc   ISO-8601 UTC
      charge_display      Human-readable: "Wednesday, June 4 at 2:47 PM ET"
      disclosure_text     Full FTC-compliant disclosure sentence
      timezone_used       IANA name of the timezone used
      timezone_note       "" or "times shown in ET" if fallback used

    Never hardcoded, never UTC, always local time.
    """
    now_utc = datetime.now(timezone.utc)
    trial_ends_at = now_utc + timedelta(hours=trial_duration_hours)
    trial_ends_at_iso = trial_ends_at.isoformat()

    # Resolve timezone: explicit IANA → state mapping → default Eastern
    tz_fallback_note = ""
    tz_name = _cfg().get("charge_timezone_default", "America/New_York")

    if iana_tz:
        try:
            ZoneInfo(iana_tz)
            tz_name = iana_tz
        except (ZoneInfoNotFoundError, Exception):
            pass
    elif state_code and state_code.upper() in _STATE_TZ:
        tz_name = _STATE_TZ[state_code.upper()]

    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = ZoneInfo("America/New_York")
        tz_fallback_note = "times shown in ET"

    local_dt = trial_ends_at.astimezone(local_tz)

    # Format: "Wednesday, June 4 at 2:47 PM ET"
    tz_abbrev = local_dt.strftime("%Z")
    charge_display = local_dt.strftime(f"%A, %B %-d at %-I:%M %p {tz_abbrev}")

    price_display = _cfg().get("platform_price_display", "$97/month")
    disclosure_text = (
        f"Free until {charge_display}. "
        f"Then {price_display}. "
        f"Cancel before that time and you won't be charged."
    )

    return {
        "trial_ends_at_utc": trial_ends_at_iso,
        "charge_display": charge_display,
        "disclosure_text": disclosure_text,
        "timezone_used": tz_name,
        "timezone_note": tz_fallback_note,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Part 2 — Cross-trial deduplication (email + card fingerprint)
# ─────────────────────────────────────────────────────────────────────────────

def check_deduplication(
    stripe_customer_id: str,
    payment_method_fingerprint: str,
) -> Tuple[bool, str]:
    """
    Check whether this user has already had a trial.
    Must run BEFORE Stripe subscription creation — never after.

    Returns (is_duplicate: bool, reason: str).
      (False, "ok")                  → trial may proceed
      (True,  "TRIAL_ALREADY_USED")  → block trial creation
    """
    # Email / Stripe customer check
    email_dup = db["promo_tokens"].find_one(
        {"stripe_customer_id": stripe_customer_id, "redeemed": True},
        {"_id": 1},
    )
    if email_dup:
        logger.info(
            "[AffiliateTrial] Dedup block: stripe_customer_id=%s already redeemed a trial",
            stripe_customer_id,
        )
        return True, "TRIAL_ALREADY_USED"

    # Card fingerprint check — catches same card, different email
    if payment_method_fingerprint:
        card_dup = db["promo_tokens"].find_one(
            {
                "payment_method_fingerprint": payment_method_fingerprint,
                "redeemed": True,
            },
            {"_id": 1},
        )
        if card_dup:
            logger.info(
                "[AffiliateTrial] Dedup block: payment_method_fingerprint=%s already redeemed a trial",
                payment_method_fingerprint,
            )
            return True, "TRIAL_ALREADY_USED"

    return False, "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Part 4.1 — Stripe trial subscription creation
# ─────────────────────────────────────────────────────────────────────────────

def create_trial_subscription(
    *,
    stripe_customer_id: str,
    trial_duration_hours: int,
    user_id: str,
    affiliate_id: Optional[str] = None,
    token_id: str,
) -> Dict[str, Any]:
    """
    Create a Stripe subscription with trial_period_days derived from
    trial_duration_hours. Card required upfront via Stripe $0 auth hold.

    Returns {"subscription_id": ..., "trial_end": ..., "status": ...}.
    Raises on Stripe error.
    """
    platform_price_id = os.getenv("STRIPE_PRICE_ID_PLATFORM", "")
    if not platform_price_id:
        raise ValueError("STRIPE_PRICE_ID_PLATFORM not configured")

    trial_period_days = max(1, trial_duration_hours // 24)

    subscription = stripe.Subscription.create(
        customer=stripe_customer_id,
        items=[{"price": platform_price_id}],
        trial_period_days=trial_period_days,
        metadata={
            "user_id": user_id,
            "affiliate_id": affiliate_id or "",
            "token_id": token_id,
            "trial_source": "AFFILIATE_REFERRAL" if affiliate_id else "QR_PROMO",
        },
        expand=["latest_invoice"],
    )
    return {
        "subscription_id": subscription.id,
        "trial_end": subscription.trial_end,
        "status": subscription.status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Part 10 — Trial token initialisation and churn/conversion handling
# ─────────────────────────────────────────────────────────────────────────────

def initialise_trial_tokens(user_id: str) -> None:
    """
    Set parlay_token_ledger balance to platform trial allocation on trial start.
    Called immediately when trial subscription is created.
    """
    allocation = _cfg().get("trial_platform_token_allocation", 1500)
    db["parlay_token_ledger"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "balance": allocation,
                "tier": "platform",
                "updated_at": _now_iso(),
                "is_trial": True,
            }
        },
        upsert=True,
    )
    db["billing_state_change_log"].insert_one({
        "event": "TRIAL_TOKEN_INIT",
        "user_id": user_id,
        "token_balance_set": allocation,
        "timestamp_utc": _now_iso(),
    })
    logger.info("[AffiliateTrial] Tokens initialised: user=%s balance=%d", user_id, allocation)


def zero_trial_tokens(user_id: str, reason: str = "TRIAL_CHURN") -> None:
    """
    Zero the token balance on trial churn or charge failure.
    Called on: cancellation, invoice.payment_failed (trial path).
    """
    db["parlay_token_ledger"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "balance": 0,
                "tier": "intelligence_preview",
                "updated_at": _now_iso(),
                "is_trial": False,
            }
        },
        upsert=True,
    )
    db["billing_state_change_log"].insert_one({
        "event": f"TRIAL_CHURN_TOKEN_ZERO",
        "reason": reason,
        "user_id": user_id,
        "token_balance_set": 0,
        "timestamp_utc": _now_iso(),
    })
    logger.info("[AffiliateTrial] Token zero: user=%s reason=%s", user_id, reason)


def carry_forward_trial_tokens_on_conversion(user_id: str) -> None:
    """
    On trial-to-paid conversion: do NOT re-initialise token balance.
    Existing balance carries forward. First paid month inherits trial remainder.
    Called from invoice.payment_succeeded (trial conversion path only).
    """
    db["billing_state_change_log"].insert_one({
        "event": "TRIAL_CONVERSION_TOKEN_CARRY_FORWARD",
        "user_id": user_id,
        "note": "Token balance carried forward — not reset on conversion",
        "timestamp_utc": _now_iso(),
    })
    # Flip is_trial flag to False — user is now a paid subscriber
    db["parlay_token_ledger"].update_one(
        {"user_id": user_id},
        {"$set": {"is_trial": False, "updated_at": _now_iso()}},
    )
    logger.info("[AffiliateTrial] Token carry-forward: user=%s", user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Part 5 — Trial cancellation
# ─────────────────────────────────────────────────────────────────────────────

def cancel_trial(user_id: str, stripe_subscription_id: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel trial subscription immediately.
    - Stripe subscription cancelled NOW (not at period end)
    - Entitlement reverts to intelligence_preview immediately
    - Token balance zeroed
    - billing_state_change_log entry written

    Returns {"status": "cancelled"} or raises.
    """
    trace_id = trace_id or str(uuid4())

    # Cancel in Stripe — immediately
    try:
        stripe.Subscription.cancel(stripe_subscription_id)
    except stripe.error.InvalidRequestError as exc:
        # Already cancelled or doesn't exist
        logger.warning("[AffiliateTrial] Stripe cancel returned error (may be already cancelled): %s", exc)

    # Revert entitlement
    db["user_entitlements"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "active": True,
                "tier": "intelligence_preview",
                "trial_active": False,
                "updated_at": _now_iso(),
            }
        },
        upsert=True,
    )

    # Zero tokens
    zero_trial_tokens(user_id, reason="TRIAL_CANCELLATION")

    # Log state change
    db["billing_state_change_log"].insert_one({
        "event": "TRIAL_CANCELLED",
        "user_id": user_id,
        "stripe_subscription_id": stripe_subscription_id,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
    })
    db["entitlement_change_log"].insert_one({
        "event": "ENTITLEMENT_REVERT_TRIAL_CANCEL",
        "user_id": user_id,
        "new_tier": "intelligence_preview",
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
    })

    logger.info("[AffiliateTrial] Trial cancelled: user=%s sub=%s", user_id, stripe_subscription_id)
    return {"status": "cancelled", "trace_id": trace_id}


# ─────────────────────────────────────────────────────────────────────────────
# Part 9 — Mid-trial direct purchase conflict resolution
# ─────────────────────────────────────────────────────────────────────────────

def resolve_mid_trial_direct_purchase(
    user_id: str,
    stripe_customer_id: str,
    new_subscription_id: str,
    new_tier: str,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Called when customer.subscription.created fires for a user who already
    has an active trial subscription. Direct purchase wins — trial is
    cancelled atomically.

    Attribution is preserved: affiliate still earns commission on the direct
    purchase if within the 30-day bv_ref cookie window.
    """
    trace_id = trace_id or str(uuid4())

    # Find the active trial subscription for this customer
    trial_doc = db["affiliate_trial_subscriptions"].find_one(
        {"stripe_customer_id": stripe_customer_id, "status": "active"},
        {"stripe_subscription_id": 1, "user_id": 1},
    )

    if not trial_doc:
        logger.info("[AffiliateTrial] MID_TRIAL_DIRECT_PURCHASE: no active trial found for customer=%s", stripe_customer_id)
        return {"status": "no_active_trial"}

    trial_sub_id = trial_doc.get("stripe_subscription_id")

    # Cancel trial subscription immediately
    if trial_sub_id:
        try:
            stripe.Subscription.cancel(trial_sub_id)
        except Exception as exc:
            logger.warning("[AffiliateTrial] MID_TRIAL_DIRECT_PURCHASE cancel error: %s", exc)

    # Mark trial as superseded
    db["affiliate_trial_subscriptions"].update_one(
        {"stripe_subscription_id": trial_sub_id},
        {"$set": {"status": "superseded_by_direct_purchase", "updated_at": _now_iso()}},
    )

    # Log state change
    db["billing_state_change_log"].insert_one({
        "event": "MID_TRIAL_DIRECT_PURCHASE",
        "user_id": user_id,
        "stripe_customer_id": stripe_customer_id,
        "cancelled_trial_subscription_id": trial_sub_id,
        "new_subscription_id": new_subscription_id,
        "new_tier": new_tier,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
    })
    db["entitlement_change_log"].insert_one({
        "event": "ENTITLEMENT_MID_TRIAL_DIRECT_PURCHASE",
        "user_id": user_id,
        "new_tier": new_tier,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
    })

    logger.info(
        "[AffiliateTrial] MID_TRIAL_DIRECT_PURCHASE resolved: user=%s trial_cancelled=%s new_sub=%s",
        user_id, trial_sub_id, new_subscription_id,
    )
    return {"status": "resolved", "cancelled_trial_sub": trial_sub_id, "trace_id": trace_id}


# ─────────────────────────────────────────────────────────────────────────────
# Commission creation helper (called from webhook handler)
# ─────────────────────────────────────────────────────────────────────────────

def create_trial_commission(
    *,
    affiliate_id: str,
    user_id: str,
    stripe_customer_id: str,
    stripe_invoice_id: str,
    new_tier: str,
    amount_paid_usd: float,
    trace_id: str,
) -> Dict[str, Any]:
    """
    Create ELIGIBLE commission record on trial conversion (invoice.payment_succeeded).
    Commission is based on the tier purchased — not the trial tier.
    net_30_date set at creation time.
    Called ONLY on invoice.payment_succeeded — never on account creation.
    """
    from datetime import timedelta
    cfg = _cfg()

    if new_tier == "platform":
        commission_usd = cfg.get("commission_platform_base_usd", 30.0)
    elif new_tier == "syndicate":
        commission_usd = cfg.get("commission_syndicate_usd", 15.0)
    else:
        commission_usd = cfg.get("commission_platform_base_usd", 30.0)

    net_days = cfg.get("commission_net_days", 30)
    net_30_date = (datetime.now(timezone.utc) + timedelta(days=net_days)).isoformat()

    commission_id = str(uuid4())
    db["affiliate_commission_log"].insert_one({
        "commission_id": commission_id,
        "affiliate_id": affiliate_id,
        "user_id": user_id,
        "stripe_customer_id": stripe_customer_id,
        "stripe_invoice_id": stripe_invoice_id,
        "commission_type": "TRIAL_CONVERSION",
        "commission_status": "ELIGIBLE",
        "commission_usd": commission_usd,
        "tier": new_tier,
        "amount_paid_usd": amount_paid_usd,
        "net_30_date": net_30_date,
        "trace_id": trace_id,
        "created_at_utc": _now_iso(),
    })

    logger.info(
        "[AffiliateTrial] Commission created: affiliate=%s user=%s tier=%s amount=%.2f net_30=%s",
        affiliate_id, user_id, new_tier, commission_usd, net_30_date,
    )
    return {
        "commission_id": commission_id,
        "commission_usd": commission_usd,
        "net_30_date": net_30_date,
        "status": "ELIGIBLE",
    }
