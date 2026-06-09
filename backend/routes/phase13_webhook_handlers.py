"""
Phase 13 — Webhook Handlers: Trial System
==========================================
Extends phase3_webhook_routes with three handlers required for the affiliate
3-day trial system:

  NEW:      customer.subscription.trial_will_end  → log + trigger hour-68 Growth Agent
  EXTENDED: invoice.payment_succeeded             → trial conversion path (commission +
                                                    token carry-forward + idempotency)
  NEW:      customer.subscription.created         → mid-trial direct purchase detection
  EXTENDED: charge.dispute.created                → affiliate commission FRAUD_HOLD
  EXTENDED: invoice.payment_failed                → trial charge failure → entitlement revert

All handlers are idempotent via the existing webhook_event_log guard in
phase3_webhook_routes.py. This file registers its handlers into the
EVENT_HANDLERS dict at import time.

Part 4.2, 4.3, 9, 11.3 of the Phase 13 spec.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import stripe

from config.agent_config import AGENT_CONFIG
from db.mongo import db
from services.phase13_affiliate_trial import (
    cancel_trial,
    carry_forward_trial_tokens_on_conversion,
    create_trial_commission,
    resolve_mid_trial_direct_purchase,
    zero_trial_tokens,
)

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def _cfg() -> Dict[str, Any]:
    return AGENT_CONFIG.get("phase13", {})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id_for_customer(stripe_customer_id: str) -> Optional[str]:
    """Resolve user_id from stripe_customer_id — mirrors phase3 helper."""
    ent = db["user_entitlements"].find_one(
        {"stripe_customer_id": stripe_customer_id}, {"user_id": 1}
    )
    if ent:
        return str(ent["user_id"])
    user = db["users"].find_one({"stripe_customer_id": stripe_customer_id}, {"_id": 1})
    if user:
        return str(user["_id"])
    return None


def _is_trial_subscription(stripe_subscription_id: str) -> bool:
    """Check if this subscription is a known affiliate trial."""
    return bool(
        db["affiliate_trial_subscriptions"].find_one(
            {"stripe_subscription_id": stripe_subscription_id, "status": "active"},
            {"_id": 1},
        )
    )


def _affiliate_id_for_subscription(stripe_subscription_id: str) -> Optional[str]:
    """Return affiliate_id linked to this trial subscription (if any)."""
    doc = db["affiliate_trial_subscriptions"].find_one(
        {"stripe_subscription_id": stripe_subscription_id},
        {"affiliate_id": 1},
    )
    return doc.get("affiliate_id") if doc else None


# ─────────────────────────────────────────────────────────────────────────────
# Handler: customer.subscription.trial_will_end (NEW — Part 4.2)
# ─────────────────────────────────────────────────────────────────────────────

def handle_trial_will_end(event: Dict[str, Any]) -> None:
    """
    customer.subscription.trial_will_end — Stripe fires 3 days before trial ends.
    For 3-day trials this fires at T+0 (trial start), which is the designed behaviour.
    For QR (24h) trials, fires at T+0 — no Growth Agent action needed.

    Action: log to billing_state_change_log, confirm trial active.
    Trigger Growth Agent affiliate_trial_hour68 template (4h before charge).
    """
    sub = event["data"]["object"]
    customer_id = sub.get("customer")
    stripe_sub_id = sub.get("id")
    trial_end_ts = sub.get("trial_end")
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        logger.warning("[Trial] trial_will_end: unknown customer=%s", customer_id)
        return

    # Log state change
    db["billing_state_change_log"].insert_one({
        "event": "TRIAL_WILL_END_WEBHOOK",
        "user_id": user_id,
        "stripe_subscription_id": stripe_sub_id,
        "trial_end_unix": trial_end_ts,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
    })

    # For affiliate trials: schedule hour-68 and hour-71 Growth Agent messages.
    # Growth Agent reads from outbound_message_schedule and fires at the correct offset.
    # We write the schedule entry here — Growth Agent executes on cron.
    if _is_trial_subscription(stripe_sub_id or ""):
        _schedule_trial_growth_agent_messages(user_id, trial_end_ts, trace_id)

    logger.info(
        "[Trial] trial_will_end: user=%s sub=%s trial_end=%s",
        user_id, stripe_sub_id, trial_end_ts,
    )


def _schedule_trial_growth_agent_messages(
    user_id: str,
    trial_end_unix: Optional[int],
    trace_id: str,
) -> None:
    """Write scheduled entries for hour-68 and hour-71 Growth Agent messages."""
    if not trial_end_unix:
        return

    from datetime import timedelta
    trial_end_dt = datetime.fromtimestamp(trial_end_unix, tz=timezone.utc)

    h68_offset = _cfg().get("trial_hour68_hours", 68)
    h71_offset = _cfg().get("trial_hour71_hours", 71)

    # Calculate from trial_end backward — trial is 72h, so:
    # hour-68 fires at trial_end - 4h, hour-71 fires at trial_end - 1h
    h68_fire_at = (trial_end_dt - timedelta(hours=4)).isoformat()
    h71_fire_at = (trial_end_dt - timedelta(hours=1)).isoformat()

    for template_id, fire_at in [
        ("affiliate_trial_hour68", h68_fire_at),
        ("affiliate_trial_hour71", h71_fire_at),
    ]:
        db["outbound_message_schedule"].update_one(
            {"user_id": user_id, "template_id": template_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "template_id": template_id,
                    "fire_at": fire_at,
                    "sent": False,
                    "trace_id": trace_id,
                    "created_at": _now_iso(),
                }
            },
            upsert=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Handler: invoice.payment_succeeded — trial conversion extension (Part 4.2 / 4.3)
# ─────────────────────────────────────────────────────────────────────────────

def handle_trial_payment_succeeded(event: Dict[str, Any]) -> None:
    """
    Extension of invoice.payment_succeeded for trial conversion path.
    Called AFTER the existing phase3 handler activates entitlement.

    Trial-specific actions:
      1. Check if this is a trial conversion (subscription has trial metadata)
      2. Create ELIGIBLE commission record (ONLY on payment — never on account creation)
      3. Token balance carry-forward (do NOT re-initialise)
      4. Mark affiliate_trial_subscriptions as 'converted'
      5. Schedule affiliate_trial_converted Growth Agent message

    Idempotency: guarded by stripe_event_id in webhook_event_log (phase3 layer).
    Additionally guarded by $setOnInsert on commission creation.
    """
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    stripe_sub_id = invoice.get("subscription")
    stripe_invoice_id = invoice.get("id")
    amount_paid = invoice.get("amount_paid", 0) / 100
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        return

    # Only proceed for trial conversions
    if not _is_trial_subscription(stripe_sub_id or ""):
        return

    affiliate_id = _affiliate_id_for_subscription(stripe_sub_id or "")

    # Determine tier
    tier = "platform"
    for line in invoice.get("lines", {}).get("data", []):
        price_id = line.get("price", {}).get("id", "")
        if price_id == os.getenv("STRIPE_PRICE_ID_SYNDICATE", "___"):
            tier = "syndicate"
            break

    # Commission — ELIGIBLE (created only here, on payment)
    if affiliate_id:
        # Idempotency: check if commission already exists for this invoice
        existing_commission = db["affiliate_commission_log"].find_one(
            {"stripe_invoice_id": stripe_invoice_id},
            {"commission_id": 1},
        )
        if not existing_commission:
            create_trial_commission(
                affiliate_id=affiliate_id,
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_invoice_id=stripe_invoice_id,
                new_tier=tier,
                amount_paid_usd=amount_paid,
                trace_id=trace_id,
            )
        else:
            logger.info(
                "[Trial] commission already exists for invoice=%s — skipping (idempotent)",
                stripe_invoice_id,
            )
            db["billing_state_change_log"].insert_one({
                "event": "WEBHOOK_DUPLICATE_COMMISSION_SKIP",
                "stripe_invoice_id": stripe_invoice_id,
                "trace_id": trace_id,
                "timestamp_utc": _now_iso(),
            })

    # Token carry-forward — do NOT re-initialise
    carry_forward_trial_tokens_on_conversion(user_id)

    # Mark trial subscription as converted
    db["affiliate_trial_subscriptions"].update_one(
        {"stripe_subscription_id": stripe_sub_id},
        {"$set": {"status": "converted", "converted_at": _now_iso()}},
    )

    # Schedule affiliate_trial_converted Growth Agent message
    try:
        from services.phase5_growth_agent import growth_agent
        growth_agent.send_message(
            user_id=user_id,
            template_id="affiliate_trial_converted",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Trial] growth agent fire failed on conversion: %s", exc)

    logger.info(
        "[Trial] Conversion complete: user=%s sub=%s affiliate=%s tier=%s amount=%.2f",
        user_id, stripe_sub_id, affiliate_id, tier, amount_paid,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler: invoice.payment_failed — trial charge failure (Part 4.2 extended)
# ─────────────────────────────────────────────────────────────────────────────

def handle_trial_payment_failed(event: Dict[str, Any]) -> None:
    """
    invoice.payment_failed for trial subscriptions.
    If the hour-72 charge fails: entitlement reverts, token balance zeroed,
    Growth Agent fires trial charge failure template.
    """
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    stripe_sub_id = invoice.get("subscription")
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        return

    if not _is_trial_subscription(stripe_sub_id or ""):
        return

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
    )

    # Zero token balance
    zero_trial_tokens(user_id, reason="TRIAL_CHARGE_FAILED")

    # Mark trial as failed
    db["affiliate_trial_subscriptions"].update_one(
        {"stripe_subscription_id": stripe_sub_id},
        {"$set": {"status": "charge_failed", "failed_at": _now_iso()}},
    )

    db["billing_state_change_log"].insert_one({
        "event": "TRIAL_CHARGE_FAILED",
        "user_id": user_id,
        "stripe_subscription_id": stripe_sub_id,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
    })

    # Growth Agent: fire trial charge failure template
    try:
        from services.phase5_growth_agent import growth_agent
        growth_agent.send_message(
            user_id=user_id,
            template_id="affiliate_trial_churned",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Trial] growth agent fire failed on charge_failed: %s", exc)

    logger.info("[Trial] Charge failed: user=%s sub=%s", user_id, stripe_sub_id)


# ─────────────────────────────────────────────────────────────────────────────
# Handler: customer.subscription.created — mid-trial direct purchase (Part 9)
# ─────────────────────────────────────────────────────────────────────────────

def handle_subscription_created_mid_trial(event: Dict[str, Any]) -> None:
    """
    customer.subscription.created fires when any new subscription is created.
    If the user has an active trial, this is a mid-trial direct purchase.
    Direct purchase wins — trial cancelled atomically.
    Attribution preserved within 30-day bv_ref cookie window.
    """
    sub = event["data"]["object"]
    customer_id = sub.get("customer")
    new_sub_id = sub.get("id")
    trace_id = str(uuid4())

    # Skip if this IS the trial subscription being created
    if sub.get("trial_end") and not db["affiliate_trial_subscriptions"].find_one(
        {"stripe_customer_id": customer_id, "status": "active"}, {"_id": 1}
    ):
        return

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        return

    # Check for active trial
    active_trial = db["affiliate_trial_subscriptions"].find_one(
        {"stripe_customer_id": customer_id, "status": "active"},
        {"stripe_subscription_id": 1},
    )
    if not active_trial:
        return

    # Determine new tier
    tier = "platform"
    for item in sub.get("items", {}).get("data", []):
        price_id = item.get("price", {}).get("id", "")
        if price_id == os.getenv("STRIPE_PRICE_ID_SYNDICATE", "___"):
            tier = "syndicate"
            break

    result = resolve_mid_trial_direct_purchase(
        user_id=user_id,
        stripe_customer_id=customer_id,
        new_subscription_id=new_sub_id,
        new_tier=tier,
        trace_id=trace_id,
    )

    # Growth Agent: trial churned (trial cancelled) + standard subscriber welcome
    try:
        from services.phase5_growth_agent import growth_agent
        growth_agent.send_message(
            user_id=user_id,
            template_id="affiliate_trial_churned",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Trial] mid-trial direct purchase growth agent failed: %s", exc)

    logger.info(
        "[Trial] Mid-trial direct purchase resolved: user=%s result=%s",
        user_id, result.get("status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Handler: charge.dispute.created — Phase 13 commission FRAUD_HOLD (Part 11.3)
# ─────────────────────────────────────────────────────────────────────────────

def handle_dispute_created_commission_hold(event: Dict[str, Any]) -> None:
    """
    charge.dispute.created extension for Phase 13.
    In addition to the phase3 entitlement suspension (already handled there),
    this handler:
      - Sets affiliate commission status → FRAUD_HOLD for this customer
      - Fires Sentinel WARNING
      - Notifies operator via ops channel
    Commission not paid until dispute is resolved.
    If dispute resolved in platform's favour: commission returned to ELIGIBLE.
    If against: FRAUD_HOLD permanent.
    """
    dispute = event["data"]["object"]
    charge_id = dispute.get("charge")
    dispute_id = dispute.get("id")
    trace_id = str(uuid4())

    # Resolve customer_id
    customer_id = dispute.get("customer")
    if not customer_id and charge_id:
        try:
            charge = stripe.Charge.retrieve(charge_id)
            customer_id = charge.get("customer")
        except Exception:
            pass

    if not customer_id:
        logger.warning("[Trial] dispute=%s — cannot resolve customer_id", dispute_id)
        return

    # Set any ELIGIBLE commissions for this customer to FRAUD_HOLD
    update_result = db["affiliate_commission_log"].update_many(
        {
            "stripe_customer_id": customer_id,
            "commission_status": {"$in": ["ELIGIBLE", "PENDING"]},
        },
        {
            "$set": {
                "commission_status": "FRAUD_HOLD",
                "fraud_hold_reason": "CHARGEBACK_DISPUTE",
                "dispute_id": dispute_id,
                "fraud_hold_at": _now_iso(),
            }
        },
    )

    if update_result.modified_count > 0:
        # Sentinel WARNING — operator must review before any commission released
        db["sentinel_event_log"].insert_one({
            "event_type": "AFFILIATE_COMMISSION_FRAUD_HOLD",
            "severity": "WARNING",
            "agent_id": "agent.sentinel.v1",
            "dispute_id": dispute_id,
            "charge_id": charge_id,
            "stripe_customer_id": customer_id,
            "commissions_held": update_result.modified_count,
            "trace_id": trace_id,
            "timestamp": _now_iso(),
            "note": "Commissions held pending dispute resolution. Operator must review before release.",
        })
        logger.warning(
            "[Trial] FRAUD_HOLD: %d commission(s) held for customer=%s dispute=%s",
            update_result.modified_count, customer_id, dispute_id,
        )
    else:
        logger.info(
            "[Trial] dispute=%s: no ELIGIBLE commissions found for customer=%s",
            dispute_id, customer_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Register Phase 13 handlers into phase3 EVENT_HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def register_phase13_webhook_handlers() -> None:
    """
    Import and extend the phase3 EVENT_HANDLERS dict with Phase 13 handlers.
    Called from main.py after both router imports complete.

    Phase 13 handlers run AFTER phase3 handlers via chained dispatch.
    """
    try:
        from routes.phase3_webhook_routes import EVENT_HANDLERS

        # NEW: customer.subscription.trial_will_end
        EVENT_HANDLERS["customer.subscription.trial_will_end"] = handle_trial_will_end

        # EXTENDED: invoice.payment_succeeded — chain trial handler after base handler
        _existing_payment_succeeded = EVENT_HANDLERS.get("invoice.payment_succeeded")

        def _chained_payment_succeeded(event: Dict[str, Any]) -> None:
            if _existing_payment_succeeded:
                _existing_payment_succeeded(event)
            handle_trial_payment_succeeded(event)

        EVENT_HANDLERS["invoice.payment_succeeded"] = _chained_payment_succeeded

        # EXTENDED: invoice.payment_failed — chain trial handler
        _existing_payment_failed = EVENT_HANDLERS.get("invoice.payment_failed")

        def _chained_payment_failed(event: Dict[str, Any]) -> None:
            if _existing_payment_failed:
                _existing_payment_failed(event)
            handle_trial_payment_failed(event)

        EVENT_HANDLERS["invoice.payment_failed"] = _chained_payment_failed

        # NEW: customer.subscription.created (mid-trial direct purchase detection)
        EVENT_HANDLERS["customer.subscription.created"] = handle_subscription_created_mid_trial

        # EXTENDED: charge.dispute.created — chain commission FRAUD_HOLD
        _existing_dispute = EVENT_HANDLERS.get("charge.dispute.created")

        def _chained_dispute_created(event: Dict[str, Any]) -> None:
            if _existing_dispute:
                _existing_dispute(event)
            handle_dispute_created_commission_hold(event)

        EVENT_HANDLERS["charge.dispute.created"] = _chained_dispute_created

        logger.info("[Phase13] Webhook handlers registered successfully")
    except ImportError as exc:
        logger.error("[Phase13] Failed to register webhook handlers: %s", exc)
