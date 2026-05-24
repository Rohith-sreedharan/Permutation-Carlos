"""
Stripe Webhook Routes — Phase 3A.2

Handles all required events. All handlers are idempotent:
duplicate delivery never creates duplicate state changes (guarded by
the Stripe event_id written to webhook_event_log before processing).

Events handled:
  invoice.created               → acknowledge + log (no entitlement change; pre-payment)
  invoice.payment_succeeded     → activate entitlement + billing_state_change_log
  invoice.payment_failed        → send failure email + log (no immediate revoke)
  customer.subscription.updated → update tier + log
  customer.subscription.deleted → revoke entitlement + invalidate session + log
  charge.dispute.created        → suspend entitlement + log CHARGEBACK_INITIATED + alert sentinel
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from db.mongo import db
from services.billing_ledger_service import billing_ledger
from services.phase3_tiers import TIERS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks-phase3"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency guard
# ─────────────────────────────────────────────────────────────────────────────

def _is_duplicate_event(stripe_event_id: str) -> bool:
    """
    Return True if this event_id has already been processed.
    Uses find_one_and_update with $setOnInsert for atomic check-and-insert.
    """
    try:
        existing = db["webhook_event_log"].find_one_and_update(
            {"stripe_event_id": stripe_event_id},
            {"$setOnInsert": {
                "stripe_event_id": stripe_event_id,
                "received_at": _now_iso(),
                "processed": False,
            }},
            upsert=True,
            return_document=True,  # BEFORE the update
        )
        # If the document existed before our upsert, it's a duplicate
        # find_one_and_update with return_document=True (pymongo default ReturnDocument.BEFORE)
        # returns None when the doc was newly inserted (upsert), and the old doc when it existed
        return existing is not None
    except Exception as exc:
        logger.error("[Webhook] idempotency check failed for %s: %s", stripe_event_id, exc)
        return False


def _mark_event_processed(stripe_event_id: str) -> None:
    try:
        db["webhook_event_log"].update_one(
            {"stripe_event_id": stripe_event_id},
            {"$set": {"processed": True, "processed_at": _now_iso()}},
        )
    except Exception:
        pass


def _log_webhook_failure(stripe_event_id: str, event_type: str, error: str) -> None:
    try:
        db["sentinel_event_log"].insert_one({
            "event_type": "WEBHOOK_FAILURE",
            "stripe_event_id": stripe_event_id,
            "webhook_event_type": event_type,
            "error": str(error)[:500],
            "trace_id": str(uuid4()),
            "timestamp": _now_iso(),
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Helper: resolve user from Stripe customer_id
# ─────────────────────────────────────────────────────────────────────────────

def _user_id_for_customer(stripe_customer_id: str) -> Optional[str]:
    ent = db["user_entitlements"].find_one({"stripe_customer_id": stripe_customer_id}, {"user_id": 1})
    if ent:
        return str(ent["user_id"])
    user = db["users"].find_one({"stripe_customer_id": stripe_customer_id}, {"_id": 1})
    if user:
        return str(user["_id"])
    return None


def _tier_from_price_id(price_id: str) -> Optional[str]:
    """Map a Stripe price_id back to a tier key."""
    for tier_key, tier in TIERS.items():
        if tier.get("stripe_price_id") == price_id:
            return tier_key
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Event handlers
# ─────────────────────────────────────────────────────────────────────────────

def _handle_payment_succeeded(event: Dict[str, Any]) -> None:
    """invoice.payment_succeeded → activate entitlement + log state change."""
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    stripe_sub_id = invoice.get("subscription")
    amount_paid = invoice.get("amount_paid", 0) / 100  # cents → USD
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        logger.warning("[Webhook] payment_succeeded: no user for customer=%s", customer_id)
        return

    # Determine tier from line items
    tier = None
    for line in invoice.get("lines", {}).get("data", []):
        price_id = line.get("price", {}).get("id", "")
        tier = _tier_from_price_id(price_id)
        if tier:
            break

    # Activate / renew entitlement
    from datetime import timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(days=32)).isoformat()
    db["user_entitlements"].update_one(
        {"user_id": user_id},
        {"$set": {
            "active": True,
            "tier": tier or "platform",
            "stripe_subscription_id": stripe_sub_id,
            "stripe_customer_id": customer_id,
            "expires_at": expires_at,
            "activated_at": _now_iso(),
            "revoke_reason": None,
        }},
        upsert=True,
    )

    billing_ledger.log_state_change(
        user_id=user_id,
        event_type="SUBSCRIPTION_ACTIVATED",
        trace_id=trace_id,
        new_tier=tier,
        stripe_subscription_id=stripe_sub_id,
        metadata={"amount_paid_usd": amount_paid, "stripe_invoice_id": invoice.get("id")},
    )

    # Send subscription receipt email
    try:
        from services.transactional_email_service import email_service
        email_service.send_subscription_receipt(
            user_id=user_id,
            amount_usd=amount_paid,
            tier_name=(TIERS.get(tier or "platform", {}).get("display_name", "Platform")),
            stripe_invoice_id=invoice.get("id"),
        )
    except Exception as exc:
        logger.error("[Webhook] receipt email failed for user=%s: %s", user_id, exc)


def _handle_payment_failed(event: Dict[str, Any]) -> None:
    """invoice.payment_failed → send failure email + log (no immediate revoke)."""
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    amount = invoice.get("amount_due", 0) / 100
    next_attempt = invoice.get("next_payment_attempt")
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        return

    billing_ledger.log_state_change(
        user_id=user_id,
        event_type="PAYMENT_FAILED",
        trace_id=trace_id,
        metadata={
            "amount_due_usd": amount,
            "stripe_invoice_id": invoice.get("id"),
            "next_attempt": next_attempt,
        },
    )

    # Send payment failure email (entitlement not immediately revoked)
    try:
        from services.transactional_email_service import email_service
        email_service.send_payment_failed(
            user_id=user_id,
            amount_usd=amount,
            next_attempt_ts=next_attempt,
            stripe_invoice_id=invoice.get("id"),
        )
    except Exception as exc:
        logger.error("[Webhook] payment_failed email failed for user=%s: %s", user_id, exc)


def _handle_subscription_updated(event: Dict[str, Any]) -> None:
    """customer.subscription.updated → update tier + log."""
    sub = event["data"]["object"]
    customer_id = sub.get("customer")
    stripe_sub_id = sub.get("id")
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        return

    # Determine new tier
    new_tier = None
    for item in sub.get("items", {}).get("data", []):
        price_id = item.get("price", {}).get("id", "")
        new_tier = _tier_from_price_id(price_id)
        if new_tier:
            break

    old_ent = db["user_entitlements"].find_one({"user_id": user_id}, {"tier": 1})
    old_tier = old_ent.get("tier") if old_ent else None

    db["user_entitlements"].update_one(
        {"user_id": user_id},
        {"$set": {
            "tier": new_tier or "platform",
            "stripe_subscription_id": stripe_sub_id,
            "updated_at": _now_iso(),
        }},
        upsert=True,
    )

    billing_ledger.log_state_change(
        user_id=user_id,
        event_type="SUBSCRIPTION_TIER_UPDATED",
        trace_id=trace_id,
        old_tier=old_tier,
        new_tier=new_tier,
        stripe_subscription_id=stripe_sub_id,
    )


def _handle_subscription_deleted(event: Dict[str, Any]) -> None:
    """customer.subscription.deleted → revoke entitlement + invalidate sessions + log."""
    sub = event["data"]["object"]
    customer_id = sub.get("customer")
    stripe_sub_id = sub.get("id")
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        return

    old_ent = db["user_entitlements"].find_one({"user_id": user_id}, {"tier": 1})
    old_tier = old_ent.get("tier") if old_ent else None

    # Revoke entitlement immediately
    db["user_entitlements"].update_one(
        {"user_id": user_id},
        {"$set": {
            "active": False,
            "revoked_at": _now_iso(),
            "revoke_reason": "SUBSCRIPTION_DELETED",
        }},
    )

    # Invalidate all active sessions for this user
    db["user_sessions"].update_many(
        {"user_id": user_id, "revoked": {"$ne": True}},
        {"$set": {"revoked": True, "revoked_at": _now_iso(), "revoke_reason": "SUBSCRIPTION_DELETED"}},
    )

    billing_ledger.log_state_change(
        user_id=user_id,
        event_type="SUBSCRIPTION_CANCELLED",
        trace_id=trace_id,
        old_tier=old_tier,
        new_tier=None,
        stripe_subscription_id=stripe_sub_id,
    )

    db["sentinel_event_log"].insert_one({
        "event_type": "SUBSCRIPTION_EXPIRED",
        "user_id": user_id,
        "reason": "SUBSCRIPTION_DELETED_BY_STRIPE",
        "trace_id": trace_id,
        "timestamp": _now_iso(),
    })

    # Send cancellation confirmation email
    try:
        from services.transactional_email_service import email_service
        email_service.send_cancellation_confirmation(
            user_id=user_id,
            effective_date=_now_iso(),
            old_tier=old_tier,
        )
    except Exception as exc:
        logger.error("[Webhook] cancellation email failed for user=%s: %s", user_id, exc)


def _handle_invoice_created(event: Dict[str, Any]) -> None:
    """
    invoice.created — PF-8 (Phase 3 canonical spec requirement).

    Fires when Stripe generates a new invoice draft (before payment is attempted).
    Entitlement is NOT changed — payment has not been confirmed.
    Action: acknowledge event, log to billing_state_change_log for audit trail.
    """
    invoice = event["data"]["object"]
    customer_id = invoice.get("customer")
    trace_id = str(uuid4())

    user_id = _user_id_for_customer(customer_id)
    if not user_id:
        logger.debug("[Webhook] invoice.created: unknown customer=%s (ignored)", customer_id)
        return

    billing_ledger.log_state_change(
        user_id=user_id,
        event_type="INVOICE_CREATED",
        trace_id=trace_id,
        metadata={
            "stripe_invoice_id": invoice.get("id"),
            "amount_due_usd": invoice.get("amount_due", 0) / 100,
            "status": invoice.get("status"),
        },
    )
    logger.info("[Webhook] invoice.created acknowledged for user=%s invoice=%s", user_id, invoice.get("id"))


def _handle_charge_dispute_created(event: Dict[str, Any]) -> None:
    """
    charge.dispute.created — PF-7 Chargeback Handling Protocol.

    On dispute:
      1. Suspend entitlement immediately (active=False, revoke_reason=CHARGEBACK_DISPUTE)
      2. Invalidate all active sessions
      3. Log CHARGEBACK_INITIATED to sentinel_event_log (ALERT threshold=1)
      4. Log state change to billing_state_change_log
      5. Do NOT delete user data — suspension only, pending dispute resolution
    See: backend/docs/CHARGEBACK_HANDLING_PROTOCOL.md
    """
    dispute = event["data"]["object"]
    charge_id = dispute.get("charge")
    dispute_id = dispute.get("id")
    amount = dispute.get("amount", 0) / 100
    trace_id = str(uuid4())

    # Resolve user from charge → payment_intent → customer
    user_id = None
    customer_id = dispute.get("customer") or dispute.get("payment_intent_customer")

    # Try to resolve via charge if customer not directly available
    if not customer_id and charge_id:
        try:
            import stripe
            charge = stripe.Charge.retrieve(charge_id)
            customer_id = charge.get("customer")
        except Exception:
            pass

    if customer_id:
        user_id = _user_id_for_customer(customer_id)

    if not user_id:
        logger.warning("[Chargeback] dispute=%s charge=%s — could not resolve user, logging unlinked", dispute_id, charge_id)

    # 1. Suspend entitlement immediately
    if user_id:
        db["user_entitlements"].update_one(
            {"user_id": user_id},
            {"$set": {
                "active": False,
                "revoked_at": _now_iso(),
                "revoke_reason": "CHARGEBACK_DISPUTE",
                "dispute_id": dispute_id,
            }},
        )

        # 2. Invalidate all active sessions
        db["user_sessions"].update_many(
            {"user_id": user_id, "revoked": {"$ne": True}},
            {"$set": {
                "revoked": True,
                "revoked_at": _now_iso(),
                "revoke_reason": "CHARGEBACK_DISPUTE",
            }},
        )

    # 3. Log CHARGEBACK_INITIATED to sentinel (immediate alert — threshold=1)
    db["sentinel_event_log"].insert_one({
        "event_type": "CHARGEBACK_INITIATED",
        "user_id": user_id or "UNKNOWN",
        "dispute_id": dispute_id,
        "charge_id": charge_id,
        "amount_usd": amount,
        "trace_id": trace_id,
        "timestamp": _now_iso(),
    })

    # 4. Log state change
    if user_id:
        billing_ledger.log_state_change(
            user_id=user_id,
            event_type="CHARGEBACK_INITIATED",
            trace_id=trace_id,
            metadata={
                "dispute_id": dispute_id,
                "charge_id": charge_id,
                "amount_usd": amount,
            },
        )

    logger.warning(
        "[Chargeback] ENTITLEMENT SUSPENDED user=%s dispute=%s amount=$%.2f",
        user_id or "UNKNOWN", dispute_id, amount,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Webhook endpoint
# ─────────────────────────────────────────────────────────────────────────────

EVENT_HANDLERS = {
    "invoice.created": _handle_invoice_created,
    "invoice.payment_succeeded": _handle_payment_succeeded,
    "invoice.payment_failed": _handle_payment_failed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "charge.dispute.created": _handle_charge_dispute_created,
}


@router.post("/stripe/phase3")
async def phase3_stripe_webhook(request: Request):
    """
    Phase 3A.2 — Idempotent Stripe webhook handler.
    Signature-verified. Duplicate event_id → 200 (acknowledged, not processed twice).
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # ── Signature verification ────────────────────────────────────────────────
    if STRIPE_WEBHOOK_SECRET:
        try:
            import stripe
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except Exception as exc:
            logger.warning("[Webhook] signature verification failed: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        # No secret configured (test/dev mode) — parse payload directly
        import json
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = event.get("id", str(uuid4()))
    event_type = event.get("type", "unknown")

    # ── Idempotency check ─────────────────────────────────────────────────────
    if _is_duplicate_event(event_id):
        logger.info("[Webhook] duplicate event ignored: %s type=%s", event_id, event_type)
        return {"status": "duplicate", "event_id": event_id}

    # ── Dispatch ─────────────────────────────────────────────────────────────
    handler = EVENT_HANDLERS.get(event_type)
    if not handler:
        _mark_event_processed(event_id)
        return {"status": "ignored", "event_type": event_type}

    try:
        handler(event)
        _mark_event_processed(event_id)
        logger.info("[Webhook] processed %s event_id=%s", event_type, event_id)
        return {"status": "ok", "event_type": event_type, "event_id": event_id}
    except Exception as exc:
        _log_webhook_failure(event_id, event_type, str(exc))
        logger.error("[Webhook] handler failed for %s event_id=%s: %s", event_type, event_id, exc)
        raise HTTPException(status_code=500, detail=f"Webhook handler error: {exc}")
