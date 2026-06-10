"""
Phase 13 — Section 13.18 Subscriber Referral Routes
====================================================
Endpoints:
  GET  /api/referral/link          — get or generate referral link + QR
  GET  /api/referral/stats         — dashboard performance stats
  POST /api/referral/convert       — called by webhook on subscription confirmed
  POST /api/referral/payout-batch  — ops endpoint to trigger payout batch run
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from middleware.auth import get_current_user
from services.phase13_subscriber_referral import (
    ensure_referral_collections,
    get_or_create_referral_link,
    get_referral_stats,
    process_referral_conversion,
    process_referral_payout_batch,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/referral", tags=["referral"])


# Run on startup — called from main.py
def init_referral_service() -> None:
    ensure_referral_collections()


# ─── GET /api/referral/link ───────────────────────────────────────────────────

@router.get("/link")
async def get_referral_link(current_user: dict = Depends(get_current_user)):
    """
    Return the authenticated subscriber's referral link + QR code.
    Creates one if it doesn't exist yet.
    Requires active Platform subscription.
    """
    user_id = str(current_user["_id"])
    try:
        data = get_or_create_referral_link(user_id)
        return {"success": True, "data": data}
    except Exception as exc:
        logger.exception("[Referral] Failed to get/create referral link user=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to generate referral link") from exc


# ─── GET /api/referral/stats ──────────────────────────────────────────────────

@router.get("/stats")
async def get_referral_stats_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Return referral performance stats for the subscriber's dashboard panel.
    """
    user_id = str(current_user["_id"])
    try:
        stats = get_referral_stats(user_id)
        return {"success": True, "data": stats}
    except Exception as exc:
        logger.exception("[Referral] Failed to get stats user=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve referral stats") from exc


# ─── POST /api/referral/convert ──────────────────────────────────────────────

class ReferralConversionPayload(BaseModel):
    referral_code: str
    referred_user_id: str
    card_fingerprint: str
    stripe_subscription_id: str
    internal_webhook_secret: str


@router.post("/convert")
async def convert_referral(payload: ReferralConversionPayload, request: Request):
    """
    Internal webhook endpoint — called when a referred user's subscription is confirmed.
    Protected by shared secret (internal-only, not user-facing).
    """
    import os
    expected_secret = os.getenv("INTERNAL_WEBHOOK_SECRET", "")
    if not expected_secret or payload.internal_webhook_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    success, reason = process_referral_conversion(
        referral_code=payload.referral_code,
        referred_user_id=payload.referred_user_id,
        card_fingerprint=payload.card_fingerprint,
        stripe_subscription_id=payload.stripe_subscription_id,
    )
    if not success:
        if reason in ("INVALID_REFERRAL_CODE", "SELF_REFERRAL", "DUPLICATE_CARD_FINGERPRINT"):
            raise HTTPException(status_code=400, detail=reason)
        if reason == "ALREADY_PROCESSED":
            return {"success": True, "idempotent": True, "reason": reason}
        raise HTTPException(status_code=500, detail=reason)

    return {"success": True, "reason": reason}


# ─── POST /api/referral/payout-batch ─────────────────────────────────────────

@router.post("/payout-batch")
async def run_payout_batch(request: Request):
    """
    Ops-only endpoint to trigger the subscriber referral payout batch.
    Protected by INTERNAL_WEBHOOK_SECRET.
    """
    import os
    secret = request.headers.get("x-internal-secret", "")
    expected = os.getenv("INTERNAL_WEBHOOK_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    result = process_referral_payout_batch()
    return {"success": True, "result": result}
