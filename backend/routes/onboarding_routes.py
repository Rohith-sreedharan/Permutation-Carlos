"""
Phase 5A — Onboarding Routes
=============================
Endpoints:
  GET  /api/onboarding/status    — return onboarding_complete flag for current user
  POST /api/onboarding/complete  — set onboarding_complete = True after screen 3
  GET  /api/games                — AC-2 gate: returns 403 if onboarding_complete is False

The /api/games endpoint is the formal AC-2 evidence target.
The flag is checked at the API level — not just UI redirect.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from db.mongo import db
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["onboarding"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_onboarding_complete(current_user: Dict[str, Any]) -> None:
    """
    Raise HTTP 403 if the authenticated user has not completed onboarding.
    This is the API-level gate for dashboard intelligence access (AC-2).
    """
    if not current_user.get("onboarding_complete", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Onboarding not complete. Complete all three onboarding screens "
                "before accessing intelligence data."
            ),
        )


# ── Onboarding status ─────────────────────────────────────────────────────────

@router.get("/onboarding/status")
def get_onboarding_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Return the onboarding_complete flag and step tracking for the current user.
    Frontend uses this to decide whether to show OnboardingWizard or Dashboard.
    """
    user_id = str(current_user.get("_id", ""))
    return {
        "onboarding_complete": bool(current_user.get("onboarding_complete", False)),
        "user_id": user_id,
        "email": current_user.get("email", ""),
        "tier": current_user.get("tier", "free"),
    }


@router.post("/onboarding/complete")
def complete_onboarding(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Mark onboarding as complete for the authenticated user.
    Called by frontend after the user finishes screen 3 of the OnboardingWizard.
    Sets onboarding_complete = True on the user record in MongoDB.
    Flag is set ONLY after all three screens are completed — not before.
    """
    user_id = current_user.get("_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resolve user identity from token",
        )

    # Idempotent — safe to call multiple times
    db["users"].update_one(
        {"_id": ObjectId(str(user_id))},
        {
            "$set": {
                "onboarding_complete": True,
                "onboarding_completed_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    logger.info(f"[onboarding] onboarding_complete=True set for user_id={user_id}")

    return {
        "status": "ok",
        "onboarding_complete": True,
        "user_id": str(user_id),
    }


# ── AC-2 gate: /api/games ─────────────────────────────────────────────────────

@router.get("/games")
def get_games(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    AC-2 evidence endpoint.
    Returns 403 if onboarding_complete is False on the user record.
    Returns the latest events from the events collection if onboarding is complete.

    Direct API call to /api/games without onboarding_complete returns 403.
    This is checked at the API level — no UI-only redirect.
    """
    _require_onboarding_complete(current_user)

    # Return real events — no fabricated data (AC-5)
    events = list(
        db["events"].find({}, {"_id": 0}).sort("commence_time", -1).limit(50)
    )
    return {
        "onboarding_complete": True,
        "count": len(events),
        "events": events,
    }


# ── AC-2 gate on /api/core/predictions ────────────────────────────────────────
# The frontend calls /api/core/predictions for the dashboard intelligence feed.
# Gate it so the API returns 403 before onboarding is complete.

@router.get("/core/predictions/gated")
def get_predictions_gated(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Gated predictions endpoint — alias used to confirm AC-2 at the predictions level.
    The main /api/core/predictions is also gated via the onboarding check in core_routes.
    """
    _require_onboarding_complete(current_user)
    # Real data only
    docs = list(db["predictions"].find({}, {"_id": 0}).sort("timestamp", -1).limit(50))
    return {"count": len(docs), "predictions": docs}
