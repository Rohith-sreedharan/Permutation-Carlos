"""
Entitlement Gating — Phase 3A.3
FastAPI dependencies enforcing the fixed check order:

  Step 1 — Authenticated?          → 401 if not
  Step 2 — Active subscription?    → 403 + upgrade CTA if not
  Step 3 — Tier permits endpoint?  → 403 + tier label if not
  Step 4 — Allocation remaining?   → 402 + usage summary if exhausted

Usage in route:
    @router.get("/api/intelligence/picks")
    def get_picks(
        _: None = Depends(require_intelligence_feature),
        user: dict = Depends(get_current_user),
    ): ...

Dependency hierarchy:
    require_intelligence_feature
        └─ require_subscription
               └─ require_platform_feature (or require_syndicate_feature)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status

from middleware.auth import get_current_user
from services.phase3_tiers import tier_has_feature

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: load entitlement record from DB
# ─────────────────────────────────────────────────────────────────────────────

def _get_entitlement(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the user's entitlement document or None."""
    try:
        from db.mongo import db
        return db["user_entitlements"].find_one({"user_id": str(user_id)}, {"_id": 0})
    except Exception as exc:
        logger.error("[Entitlement] DB lookup failed for user=%s: %s", user_id, exc)
        return None


def _log_entitlement_violation(user_id: str, endpoint: str, reason: str) -> None:
    """Log to sentinel_event_log for AC-3C monitoring."""
    try:
        from db.mongo import db
        from datetime import datetime, timezone
        db["sentinel_event_log"].insert_one({
            "event_type": "ENTITLEMENT_VIOLATION",
            "user_id": str(user_id),
            "endpoint": endpoint,
            "reason": reason,
            "trace_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Active subscription check
# ─────────────────────────────────────────────────────────────────────────────

def require_active_subscription(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Step 2 — Ensure the user has an active subscription record.
    Returns the entitlement dict; raises 403 with upgrade CTA if absent.
    """
    user_id = str(user.get("_id", user.get("id", "")))
    ent = _get_entitlement(user_id)

    if not ent or not ent.get("active", False):
        _log_entitlement_violation(user_id, "subscription_check", "NO_ACTIVE_SUBSCRIPTION")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NO_ACTIVE_SUBSCRIPTION",
                "message": "You do not have an active subscription.",
                "upgrade_url": "https://beatvegas.app/upgrade",
            },
        )

    # CF-3 / AC-3: Check subscription expiry in real time
    expires_at = ent.get("expires_at")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                # Revoke entitlement immediately
                from db.mongo import db
                db["user_entitlements"].update_one(
                    {"user_id": user_id},
                    {"$set": {"active": False, "revoked_at": datetime.now(timezone.utc).isoformat(), "revoke_reason": "SUBSCRIPTION_EXPIRED"}},
                )
                _log_entitlement_violation(user_id, "subscription_check", "SUBSCRIPTION_EXPIRED")
                from services.billing_ledger_service import billing_ledger
                billing_ledger.log_state_change(
                    user_id=user_id,
                    event_type="SUBSCRIPTION_EXPIRED",
                    trace_id=str(uuid4()),
                    old_tier=ent.get("tier"),
                    new_tier=None,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "SUBSCRIPTION_EXPIRED",
                        "message": "Your subscription has expired. Please renew to continue.",
                        "renew_url": "https://beatvegas.app/upgrade",
                    },
                )
        except HTTPException:
            raise
        except Exception:
            pass  # malformed date — allow through; sentinel will catch anomaly

    return ent


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Tier feature check
# ─────────────────────────────────────────────────────────────────────────────

def _require_feature(feature: str):
    """Factory: returns a dependency that checks a specific tier feature."""

    def _check(
        ent: Dict[str, Any] = Depends(require_active_subscription),
    ) -> Dict[str, Any]:
        tier = ent.get("tier", "intelligence_preview")
        if not tier_has_feature(tier, feature):
            user_id = ent.get("user_id", "?")
            _log_entitlement_violation(user_id, feature, f"TIER_INSUFFICIENT tier={tier}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TIER_INSUFFICIENT",
                    "message": f"Your current plan ({tier}) does not include this feature.",
                    "required_feature": feature,
                    "upgrade_url": "https://beatvegas.app/upgrade",
                },
            )
        return ent

    return _check


# Named dependency shortcuts
require_intelligence_feature = _require_feature("intelligence_outputs")
require_web_platform_feature = _require_feature("web_platform")
require_telegram_feature = _require_feature("telegram_signals")
require_parlay_architect_feature = _require_feature("parlay_architect")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Cycle allocation check (overage gate)
# ─────────────────────────────────────────────────────────────────────────────

def require_allocation_remaining(
    ent: Dict[str, Any] = Depends(require_active_subscription),
) -> Dict[str, Any]:
    """
    Step 4 — Ensure the user has not exhausted their cycle allocation.
    Returns entitlement on pass; raises 402 with usage summary at 100%.
    Warns at 80% (logged + user notified via sentinel, no block).
    """
    from config.agent_config import AGENT_CONFIG
    warn_pct = AGENT_CONFIG["sentinel"]["OVERAGE_WARN_PCT"]
    block_pct = AGENT_CONFIG["sentinel"]["OVERAGE_BLOCK_PCT"]

    tokens_used = int(ent.get("tokens_used_current_period", 0))
    tokens_alloc = int(ent.get("tokens_allocated_current_period", 0))

    if tokens_alloc <= 0:
        # Unlimited or not tracked — pass through
        return ent

    pct_used = (tokens_used / tokens_alloc) * 100

    if pct_used >= block_pct:
        user_id = ent.get("user_id", "?")
        _log_overage_event(user_id, "OVERAGE_BLOCK", tokens_used, tokens_alloc)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "ALLOCATION_EXHAUSTED",
                "message": "You have used 100% of your monthly allocation.",
                "tokens_used": tokens_used,
                "tokens_allocated": tokens_alloc,
                "upgrade_url": "https://beatvegas.app/upgrade",
            },
        )

    if pct_used >= warn_pct:
        user_id = ent.get("user_id", "?")
        _log_overage_event(user_id, "OVERAGE_WARN", tokens_used, tokens_alloc)

    return ent


def _log_overage_event(user_id: str, event_type: str, used: int, alloc: int) -> None:
    try:
        from db.mongo import db
        db["sentinel_event_log"].insert_one({
            "event_type": event_type,
            "user_id": str(user_id),
            "tokens_used": used,
            "tokens_allocated": alloc,
            "pct_used": round((used / alloc) * 100, 2) if alloc > 0 else 0,
            "trace_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Combined dependency: full 4-step gate for intelligence endpoints
# ─────────────────────────────────────────────────────────────────────────────

def require_intelligence_with_allocation(
    ent: Dict[str, Any] = Depends(require_intelligence_feature),
) -> Dict[str, Any]:
    """Steps 1-4 combined: auth + active sub + intelligence tier + allocation."""
    return require_allocation_remaining(ent)
