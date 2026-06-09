"""
Phase 13 — Affiliate Trial Routes
====================================
Backend routes for the 3-day affiliate referral trial system.

Routes:
  GET  /api/trial/affiliate/{affiliate_id}     — page load: validate affiliate, charge timing
  POST /api/trial/affiliate/start              — start trial: dedup + Stripe subscription
  POST /api/trial/affiliate/turnstile-verify   — Cloudflare Turnstile verification
  GET  /api/trial/status                       — current trial status for authenticated user
  POST /api/trial/cancel                       — cancel trial (one-click, entry point #3)

Parts: 2, 3, 4, 5, 8, 11.4
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx
import stripe
from fastapi import APIRouter, Cookie, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from config.agent_config import AGENT_CONFIG
from db.mongo import db
from services.phase11_affiliate_engine import affiliate_engine as _aff_engine
from services.phase13_affiliate_trial import (
    cancel_trial,
    check_deduplication,
    create_trial_subscription,
    get_affiliate_display_name,
    get_charge_disclosure,
    initialise_trial_tokens,
    sanitise_html,
)
from services.transactional_email_service import send_affiliate_trial_receipt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trial", tags=["phase13-trial"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def _cfg() -> Dict[str, Any]:
    return AGENT_CONFIG.get("phase13", {})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Stripe API retry helper — exponential backoff (Item 10)
# Stripe live mode enforces stricter rate limits than test mode.
# Retries on RateLimitError and APIConnectionError only — not card declines.
# ─────────────────────────────────────────────────────────────────────────────
_STRIPE_RETRY_STATUSES = (stripe.error.RateLimitError, stripe.error.APIConnectionError)
_STRIPE_MAX_RETRIES = 3
_STRIPE_BACKOFF_BASE = 0.5  # seconds; doubles each attempt: 0.5, 1.0, 2.0


def _stripe_call_with_retry(fn, *args, **kwargs):
    """
    Execute a Stripe SDK call with exponential backoff retry.
    Retries up to _STRIPE_MAX_RETRIES times on transient errors.
    Raises the original exception after all retries are exhausted.
    """
    last_exc = None
    for attempt in range(_STRIPE_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except _STRIPE_RETRY_STATUSES as exc:
            last_exc = exc
            if attempt == _STRIPE_MAX_RETRIES:
                break
            wait = _STRIPE_BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "[Stripe] Transient error on attempt %d/%d, retrying in %.1fs: %s",
                attempt + 1, _STRIPE_MAX_RETRIES, wait, exc,
            )
            time.sleep(wait)
    raise last_exc


# ─────────────────────────────────────────────────────────────────────────────
# Part 11.4 — Cloudflare Turnstile verification
# ─────────────────────────────────────────────────────────────────────────────

async def _verify_turnstile(token: str, remote_ip: str) -> bool:
    """
    Verify Cloudflare Turnstile challenge token.
    Returns True if verification passes, False otherwise.
    Invisible to real users on modern browsers — blocks automated scripts.
    """
    secret = _cfg().get("turnstile_secret_key", "")
    if not secret:
        # No secret configured — dev mode, allow all
        logger.debug("[Turnstile] No secret configured — skipping verification (dev mode)")
        return True

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": secret,
                    "response": token,
                    "remoteip": remote_ip,
                },
            )
            result = resp.json()
            return result.get("success", False)
    except Exception as exc:
        logger.error("[Turnstile] Verification request failed: %s", exc)
        return False


def _log_turnstile_fail(ip: str, token_id: Optional[str] = None) -> None:
    """Log TURNSTILE_FAIL to promo_scans for monitoring."""
    try:
        db["promo_scans"].insert_one({
            "event_type": "TURNSTILE_FAIL",
            "ip_address": ip,
            "token_id": token_id,
            "created_at": _now_iso(),
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Part 11.5 — URL parameter sanitisation helper
# ─────────────────────────────────────────────────────────────────────────────

def _sanitise_all_params(params: Dict[str, str]) -> Dict[str, str]:
    """
    HTML-encode all URL parameters before any DOM insertion or response.
    Zero raw URL parameter values returned to the client. Ever.
    """
    return {k: sanitise_html(str(v)) for k, v in params.items()}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/trial/affiliate/{affiliate_id} — page load data
# Part 3, 3.4, 3.5
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/affiliate/{affiliate_id}")
async def get_affiliate_trial_page_data(
    affiliate_id: str,
    request: Request,
    state: Optional[str] = None,
    tz: Optional[str] = None,
    bv_ref: Optional[str] = Cookie(default=None),
):
    """
    Returns page data for the affiliate trial landing page.
    - Validates affiliate_id, returns sanitised display_name
    - Calculates exact local charge date/time (FTC requirement)
    - Returns token expiry countdown
    - Zero intelligence output — no sample decisions, no classifications

    All URL parameters sanitised before response.
    """
    # Sanitise affiliate_id before any use — Part 11.5
    safe_affiliate_id = sanitise_html(affiliate_id)

    # Validate affiliate + get display name (returns fallback if invalid)
    display_name = get_affiliate_display_name(safe_affiliate_id)

    # Charge timing disclosure (FTC Negative Option Rule 2024)
    trial_hours = _cfg().get("trial_duration_affiliate_hours", 72)
    state_code = sanitise_html(state) if state else None
    tz_code = sanitise_html(tz) if tz else None

    # Use GeoIP state from middleware if available
    if not state_code and hasattr(request.state, "geo_state"):
        state_code = request.state.geo_state

    charge_info = get_charge_disclosure(
        trial_duration_hours=trial_hours,
        state_code=state_code,
        iana_tz=tz_code,
    )

    # Offer expiry: compute from clicked_at_utc in bv_ref cookie when present;
    # fall back to offer_expiry_seconds from now so the page always has a valid timer.
    offer_expiry_seconds = _cfg().get("affiliate_trial_offer_expiry_seconds", 86400)
    now_dt = datetime.now(timezone.utc)

    offer_expires_at_utc: Optional[str] = None
    if bv_ref:
        parsed_cookie, cookie_err = _aff_engine.parse_signed_cookie(bv_ref)
        if parsed_cookie and not cookie_err:
            try:
                clicked_at = datetime.fromisoformat(
                    parsed_cookie["clicked_at_utc"].replace("Z", "+00:00")
                )
                offer_expires_at_utc = (
                    clicked_at + timedelta(seconds=offer_expiry_seconds)
                ).isoformat()
            except (KeyError, ValueError):
                pass

    if offer_expires_at_utc is None:
        # No valid cookie — offer window starts now (first page load)
        offer_expires_at_utc = (now_dt + timedelta(seconds=offer_expiry_seconds)).isoformat()

    platform_price = _cfg().get("platform_price_display", "$97/month")
    turnstile_site_key = _cfg().get("turnstile_site_key", "")

    return {
        "affiliate_id": safe_affiliate_id,
        "display_name": display_name,
        "trial_duration_hours": trial_hours,
        "platform_price": platform_price,
        "charge_disclosure": charge_info["disclosure_text"],
        "charge_display": charge_info["charge_display"],
        "trial_ends_at_utc": charge_info["trial_ends_at_utc"],
        "timezone_used": charge_info["timezone_used"],
        "timezone_note": charge_info["timezone_note"],
        "offer_expires_at_utc": offer_expires_at_utc,
        "turnstile_site_key": turnstile_site_key,
        # Zero intelligence output — Part 3.6 compliance
        "intelligence_preview": None,
        "sample_decisions": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/trial/affiliate/start — trial creation
# Parts 2, 4.1, 10, 12
# ─────────────────────────────────────────────────────────────────────────────

class StartTrialRequest(BaseModel):
    affiliate_id: str
    payment_method_id: str           # real pm_xxx from Stripe.js createPaymentMethod()
    device_fingerprint: Optional[str] = None
    turnstile_token: Optional[str] = None
    # stripe_customer_id is resolved server-side from the authenticated user record
    # so it is never a client-supplied value (prevents customer ID spoofing)


@router.post("/affiliate/start")
async def start_affiliate_trial(
    body: StartTrialRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    Create a 3-day affiliate trial subscription.

    Order of operations (Part 2 — check BEFORE create):
    1. Turnstile verification
    2. Card fingerprint retrieval from Stripe
    3. Deduplication check (email + card fingerprint) — BEFORE Stripe subscription
    4. Create Stripe trial subscription
    5. Mark promo_token redeemed
    6. Initialise token balance (1,500)
    7. Create affiliate_trial_subscriptions record
    8. Send affiliate_trial_receipt email (FTC requirement)
    9. Fire Growth Agent affiliate_trial_welcome (with overlap suppression)
    """
    trace_id = str(uuid4())
    client_ip = request.client.host if request.client else "unknown"

    # ── Auth: resolve user from token ─────────────────────────────────────
    # Authorization is required — we need the user's Stripe customer ID
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    auth_token = authorization.split(" ", 1)[1]
    from services.auth_service import get_user_from_token_safe
    user_id = get_user_from_token_safe(auth_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    # Resolve Stripe customer ID server-side — never accepted from client body
    user_doc = db["users"].find_one(
        {"$or": [{"_id": user_id}, {"user_id": user_id}]},
        {"stripe_customer_id": 1, "email": 1},
    )
    stripe_customer_id = (user_doc or {}).get("stripe_customer_id", "") if user_doc else ""
    user_email = (user_doc or {}).get("email", "") if user_doc else ""

    # If no Stripe customer yet, create one now
    if not stripe_customer_id and user_email:
        try:
            customer = _stripe_call_with_retry(
                stripe.Customer.create, email=user_email, metadata={"user_id": user_id}
            )
            stripe_customer_id = customer["id"]
            db["users"].update_one(
                {"$or": [{"_id": user_id}, {"user_id": user_id}]},
                {"$set": {"stripe_customer_id": stripe_customer_id}},
            )
        except Exception as exc:
            logger.error("[Trial] Stripe customer creation failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to create customer record.")

    if not stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account not eligible for trial.")

    # ── 1. Turnstile verification ──────────────────────────────────────────
    turnstile_token = body.turnstile_token or ""
    turnstile_ok = await _verify_turnstile(turnstile_token, client_ip)
    if not turnstile_ok:
        _log_turnstile_fail(client_ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bot protection check failed. Please try again.",
        )

    # ── 2. Sanitise all inputs — Part 11.5 ────────────────────────────────
    affiliate_id = sanitise_html(body.affiliate_id)
    payment_method_id = sanitise_html(body.payment_method_id)
    # stripe_customer_id already resolved server-side above — sanitise for safety
    stripe_customer_id = sanitise_html(stripe_customer_id)

    # ── 3. Retrieve card fingerprint from Stripe ───────────────────────────
    # payment_method_id is a real pm_xxx created by Stripe.js on the client.
    # Stripe.PaymentMethod.retrieve() returns card.fingerprint — a Stripe-level
    # hash of the card number that is stable across different tokenisations of
    # the same physical card. Used for deduplication (Part 2 of spec).
    pm_fingerprint = ""
    try:
        pm = _stripe_call_with_retry(stripe.PaymentMethod.retrieve, payment_method_id)
        pm_fingerprint = pm.get("card", {}).get("fingerprint", "") or ""
    except Exception as exc:
        logger.error("[Trial] PaymentMethod retrieve failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to verify payment method.",
        )

    # ── 4. Deduplication — BEFORE Stripe subscription creation ────────────
    is_dup, dup_reason = check_deduplication(
        stripe_customer_id=stripe_customer_id,
        payment_method_fingerprint=pm_fingerprint,
    )
    if is_dup:
        logger.info("[Trial] Dedup block: customer=%s reason=%s", stripe_customer_id, dup_reason)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A trial for this account has already been used.",
        )

    # ── 4a. Device fingerprint deduplication ──────────────────────────────
    # Same device creating a second trial within 30 days → TRIAL_ALREADY_USED
    if body.device_fingerprint:
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        existing_device = db["promo_tokens"].find_one({
            "device_fingerprint": body.device_fingerprint,
            "redeemed": True,
            "created_at": {"$gt": thirty_days_ago},
        })
        if existing_device:
            logger.info(
                "[Trial] DEVICE_FINGERPRINT block: fingerprint=%s user=%s",
                body.device_fingerprint[:16],
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="TRIAL_ALREADY_USED",
            )

    # ── 4b. IP velocity check ─────────────────────────────────────────────
    # 3+ trial signups from the same IP within 24 hours → flag affiliate
    twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_from_ip = db["promo_tokens"].count_documents({
        "client_ip": client_ip,
        "created_at": {"$gt": twenty_four_hours_ago},
    })
    if recent_from_ip >= 3:
        logger.warning(
            "[Trial] IP_VELOCITY flag: ip=%s affiliate=%s count=%d",
            client_ip,
            affiliate_id,
            recent_from_ip,
        )
        # Flag the affiliate for fraud review — non-blocking for user
        try:
            db["affiliate_fraud_flags"].insert_one({
                "affiliate_id": affiliate_id,
                "reason": "IP_VELOCITY",
                "client_ip": client_ip,
                "count_24h": recent_from_ip,
                "user_id": user_id,
                "trace_id": trace_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            db["affiliate_accounts"].update_one(
                {"affiliate_id": affiliate_id},
                {"$set": {"fraud_hold": True, "fraud_hold_reason": "IP_VELOCITY", "fraud_hold_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception as _flag_exc:
            logger.error("[Trial] Fraud flag write failed: %s", _flag_exc)

    # user_id already resolved from auth token above (Step Auth)

    # ── 4c. $0 Card Authorization check ───────────────────────────────────
    # Stripe performs a $0 authorization automatically when a PaymentMethod is
    # attached to a subscription with a trial period. We verify it succeeded
    # before granting any entitlement. If it fails we log CARD_AUTH_FAILED and
    # return a clean user-facing error — the promo token is NOT consumed.
    try:
        import stripe as _stripe_sdk
        # Attach the PaymentMethod to the Customer so Stripe can authorize it
        _stripe_call_with_retry(
            _stripe_sdk.PaymentMethod.attach,
            body.payment_method_id,
            customer=stripe_customer_id,
        )
        # Set as default so the upcoming subscription uses it
        _stripe_call_with_retry(
            _stripe_sdk.Customer.modify,
            stripe_customer_id,
            invoice_settings={"default_payment_method": body.payment_method_id},
        )
        # Perform a $0 SetupIntent to confirm card is authorizable
        setup_intent = _stripe_call_with_retry(
            _stripe_sdk.SetupIntent.create,
            customer=stripe_customer_id,
            payment_method=body.payment_method_id,
            confirm=True,
            usage="off_session",
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        )
        if setup_intent.status not in ("succeeded", "processing"):
            raise ValueError(f"SetupIntent status: {setup_intent.status}")
    except Exception as auth_exc:
        auth_err_msg = str(auth_exc)
        logger.warning("[Trial] CARD_AUTH_FAILED: customer=%s pm=%s err=%s",
                       stripe_customer_id, body.payment_method_id, auth_err_msg)
        db["promo_scans"].insert_one({
            "scan_id": str(uuid4()),
            "affiliate_id": affiliate_id,
            "user_id": user_id,
            "stripe_customer_id": stripe_customer_id,
            "payment_method_id": body.payment_method_id,
            "blocked_reason": "CARD_AUTH_FAILED",
            "error_detail": auth_err_msg[:500],
            "created_at": _now_iso(),
            "trace_id": trace_id,
        })
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your card could not be verified. Please try a different card.",
        )

    # ── 5. Create token record (pre-subscription) ─────────────────────────
    token_id = str(uuid4())
    token_expiry_min = _cfg().get("promo_token_expiry_minutes", 60)
    from datetime import timedelta
    token_expires_at = (datetime.now(timezone.utc) + timedelta(minutes=token_expiry_min)).isoformat()
    trial_hours = _cfg().get("trial_duration_affiliate_hours", 72)

    db["promo_tokens"].insert_one({
        "token_id": token_id,
        "user_id": user_id,
        "stripe_customer_id": stripe_customer_id,
        "affiliate_id": affiliate_id,
        "trial_source": "AFFILIATE_REFERRAL",
        "trial_duration_hours": trial_hours,
        "payment_method_fingerprint": pm_fingerprint,
        "device_fingerprint": body.device_fingerprint,
        "client_ip": client_ip,
        "redeemed": False,
        "expires_at": token_expires_at,
        "created_at": _now_iso(),
        "trace_id": trace_id,
    })

    # ── 6. Create Stripe trial subscription ───────────────────────────────
    # Dedup passed — safe to create
    try:
        sub_result = create_trial_subscription(
            stripe_customer_id=stripe_customer_id,
            trial_duration_hours=trial_hours,
            user_id=user_id,
            affiliate_id=affiliate_id,
            token_id=token_id,
        )
    except Exception as exc:
        # Stripe creation failed — clean up token record
        db["promo_tokens"].delete_one({"token_id": token_id})
        logger.error("[Trial] Stripe subscription creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Subscription creation failed. Your card has not been charged.",
        )

    stripe_sub_id = sub_result["subscription_id"]
    trial_end_unix = sub_result.get("trial_end")

    # ── 8. Mark token redeemed + store subscription ID ────────────────────
    db["promo_tokens"].update_one(
        {"token_id": token_id},
        {
            "$set": {
                "redeemed": True,
                "redeemed_at": _now_iso(),
                "stripe_subscription_id": stripe_sub_id,
            }
        },
    )

    # ── 9. Initialise entitlement ──────────────────────────────────────────
    db["user_entitlements"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "active": True,
                "tier": "platform",
                "trial_active": True,
                "stripe_subscription_id": stripe_sub_id,
                "stripe_customer_id": stripe_customer_id,
                "updated_at": _now_iso(),
            }
        },
        upsert=True,
    )

    # ── 10. Initialise token balance (1,500 platform allocation) ───────────
    initialise_trial_tokens(user_id)

    # ── 11. Create affiliate_trial_subscriptions tracking record ──────────
    # Get charge disclosure for email
    charge_info = get_charge_disclosure(trial_duration_hours=trial_hours)
    trial_ends_at = charge_info["trial_ends_at_utc"]

    db["affiliate_trial_subscriptions"].update_one(
        {"stripe_customer_id": stripe_customer_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_sub_id,
                "affiliate_id": affiliate_id,
                "token_id": token_id,
                "trial_source": "AFFILIATE_REFERRAL",
                "trial_duration_hours": trial_hours,
                "trial_starts_at": _now_iso(),
                "trial_ends_at": trial_ends_at,
                "status": "active",
                "trace_id": trace_id,
            }
        },
        upsert=True,
    )

    # ── 12. Send affiliate_trial_receipt email (FTC requirement) ──────────
    try:
        send_affiliate_trial_receipt(
            user_id=user_id,
            charge_display=charge_info["charge_display"],
            trial_ends_at_utc=trial_ends_at,
            stripe_subscription_id=stripe_sub_id,
        )
    except Exception as exc:
        logger.error("[Trial] trial_receipt email failed: %s", exc)
        # Do not block — Stripe subscription created, log failure for monitoring

    # ── 13. Growth Agent: affiliate_trial_welcome (overlap suppression applied inside)
    try:
        from services.phase5_growth_agent import growth_agent
        growth_agent.send_message(
            user_id=user_id,
            template_id="affiliate_trial_welcome",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Trial] growth agent welcome failed: %s", exc)

    # ── 14. Log rapid conversion velocity for Sentinel ────────────────────
    _check_rapid_conversion_velocity(affiliate_id, trace_id)

    logger.info(
        "[Trial] Started: user=%s affiliate=%s sub=%s trace=%s",
        user_id, affiliate_id, stripe_sub_id, trace_id,
    )

    return {
        "status": "trial_started",
        "stripe_subscription_id": stripe_sub_id,
        "trial_ends_at": trial_ends_at,
        "charge_display": charge_info["charge_display"],
        "trace_id": trace_id,
    }


def _check_rapid_conversion_velocity(affiliate_id: str, trace_id: str) -> None:
    """
    Part 11.1 — Rapid conversion velocity monitor.
    If affiliate_id exceeds threshold conversions in rolling window → FRAUD_HOLD + WARNING.
    Thresholds from agent_config.phase13.
    """
    from datetime import timedelta
    cfg = _cfg()
    threshold = cfg.get("affiliate_rapid_conversion_threshold", 5)
    window_days = cfg.get("affiliate_rapid_conversion_window_days", 7)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    # Count conversions in window (use affiliate_trial_subscriptions as proxy)
    count = db["affiliate_trial_subscriptions"].count_documents({
        "affiliate_id": affiliate_id,
        "trial_starts_at": {"$gte": cutoff},
    })

    if count > threshold:
        # FRAUD_HOLD all commissions from this affiliate in the window
        db["affiliate_commission_log"].update_many(
            {
                "affiliate_id": affiliate_id,
                "created_at_utc": {"$gte": cutoff},
                "commission_status": {"$in": ["ELIGIBLE", "PENDING"]},
            },
            {
                "$set": {
                    "commission_status": "FRAUD_HOLD",
                    "fraud_hold_reason": "RAPID_CONVERSION_VELOCITY",
                    "fraud_hold_at": _now_iso(),
                }
            },
        )

        # Sentinel WARNING
        db["sentinel_event_log"].insert_one({
            "event_type": "AFFILIATE_RAPID_CONVERSION_VELOCITY",
            "severity": "WARNING",
            "agent_id": "agent.sentinel.v1",
            "affiliate_id": affiliate_id,
            "conversion_count": count,
            "window_days": window_days,
            "threshold": threshold,
            "trace_id": trace_id,
            "timestamp": _now_iso(),
            "note": f"Affiliate generated {count} conversions in {window_days} days (threshold: {threshold}). Commissions held for review.",
        })

        logger.warning(
            "[Trial] RAPID_CONVERSION_VELOCITY: affiliate=%s count=%d threshold=%d",
            affiliate_id, count, threshold,
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/trial/status — trial status for authenticated user
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_trial_status(authorization: Optional[str] = Header(default=None)):
    """
    Returns current trial status, trial_ends_at, and charge_display for the
    authenticated user. Used by the dashboard cancellation banner (Part 5.1).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    token = authorization.split(" ", 1)[1]
    # Resolve user from token — mirrors existing auth pattern
    from services.auth_service import get_user_from_token_safe
    user_id = get_user_from_token_safe(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    trial_doc = db["affiliate_trial_subscriptions"].find_one(
        {"user_id": user_id, "status": "active"},
        {"trial_ends_at": 1, "stripe_subscription_id": 1, "trial_source": 1},
    )
    if not trial_doc:
        return {"trial_active": False}

    # Re-compute charge display for freshness
    trial_ends_iso = trial_doc.get("trial_ends_at", "")
    charge_display = trial_ends_iso  # Fallback to ISO if parsing fails
    try:
        from datetime import datetime
        ends_dt = datetime.fromisoformat(trial_ends_iso.replace("Z", "+00:00"))
        charge_display = ends_dt.strftime("%A, %B %-d at %-I:%M %p %Z")
    except Exception:
        pass

    return {
        "trial_active": True,
        "trial_ends_at": trial_ends_iso,
        "charge_display": charge_display,
        "stripe_subscription_id": trial_doc.get("stripe_subscription_id"),
        "trial_source": trial_doc.get("trial_source"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/trial/cancel — one-click trial cancellation (entry point #3)
# Part 5.1
# ─────────────────────────────────────────────────────────────────────────────

class CancelTrialRequest(BaseModel):
    stripe_subscription_id: Optional[str] = None


@router.post("/cancel")
async def cancel_trial_endpoint(
    body: CancelTrialRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    One-click trial cancellation. FTC Negative Option Rule 2024 requires
    cancellation to be as easy as enrollment.
    - One click in welcome email
    - One click in dashboard banner
    - One click in billing page
    No confirmation dialog. Processed immediately.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    token = authorization.split(" ", 1)[1]
    from services.auth_service import get_user_from_token_safe
    user_id = get_user_from_token_safe(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Find active trial
    trial_doc = db["affiliate_trial_subscriptions"].find_one(
        {"user_id": user_id, "status": "active"},
        {"stripe_subscription_id": 1},
    )

    stripe_sub_id = body.stripe_subscription_id
    if not stripe_sub_id and trial_doc:
        stripe_sub_id = trial_doc.get("stripe_subscription_id")

    if not stripe_sub_id:
        return {"status": "no_active_trial"}

    trace_id = str(uuid4())
    result = cancel_trial(
        user_id=user_id,
        stripe_subscription_id=stripe_sub_id,
        trace_id=trace_id,
    )

    # Growth Agent: affiliate_trial_churned
    try:
        from services.phase5_growth_agent import growth_agent
        growth_agent.send_message(
            user_id=user_id,
            template_id="affiliate_trial_churned",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Trial] growth agent churned failed: %s", exc)

    # Schedule win-back sequence
    try:
        from services.phase5_growth_agent import growth_agent
        from datetime import timedelta
        growth_agent.send_message(
            user_id=user_id,
            template_id="affiliate_winback_day2",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Trial] growth agent winback schedule failed: %s", exc)

    return {"status": "cancelled", "trace_id": result.get("trace_id")}
