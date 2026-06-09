"""
Billing Ledger Service — Phase 3A.1
Source of truth for all billable actions.

Write-First Protocol (non-negotiable):
  1. INSERT billing_ledger row with status=PENDING  ← must succeed first
  2. Execute billable action
  3. UPDATE row status to SETTLED  (or FAILED on error)

If step 1 fails → reject action, return error to caller, fire BILLING_WRITE_FAIL alert.
No silent deductions. No deductions after execution. Append-only log.

Collections:
  billing_ledger           — immutable per-action rows
  billing_state_change_log — subscription lifecycle events (activated, tier change, revoked)
  parlay_overage_charge_log — overage charge records with Stripe invoice references
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional
from uuid import uuid4

from db.mongo import db

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Internal: Sentinel alert helper
# ─────────────────────────────────────────────────────────────────────────────

def _fire_billing_write_fail_alert(trace_id: str, user_id: str, action_type: str, error: str) -> None:
    """Write BILLING_WRITE_FAIL to sentinel_event_log immediately."""
    try:
        db["sentinel_event_log"].insert_one({
            "event_type": "BILLING_WRITE_FAIL",
            "trace_id": trace_id,
            "user_id": str(user_id),
            "action_type": action_type,
            "error": str(error)[:500],
            "timestamp": _now_iso(),
        })
    except Exception as exc:
        logger.error("[BillingLedger] BILLING_WRITE_FAIL alert could not be persisted: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class BillingLedgerService:
    """
    Phase 3A.1 — Write-First billing ledger.

    All billable actions MUST call begin_billable_action() before executing,
    and settle_action() / fail_action() on completion. The recommended pattern
    is the billable_action() context manager which enforces ordering atomically.
    """

    def __init__(self, ledger_col=None, sentinel_col=None) -> None:
        self._ledger = ledger_col if ledger_col is not None else db["billing_ledger"]
        self._sentinel = sentinel_col if sentinel_col is not None else db["sentinel_event_log"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            self._ledger.create_index("trace_id", unique=True)
            self._ledger.create_index([("user_id", 1), ("created_at", -1)])
            self._ledger.create_index([("status", 1)])
            self._ledger.create_index([("tenant_id", 1), ("created_at", -1)])
        except Exception:
            pass  # indexes already exist

    # ── Core write-first primitives ───────────────────────────────────────────

    def begin_billable_action(
        self,
        *,
        action_type: str,
        user_id: str,
        tenant_id: str,
        amount: float,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Step 1: INSERT billing_ledger row with status=PENDING.
        Returns the trace_id on success.
        Raises BillingLedgerWriteError on failure — caller MUST reject the action.
        """
        trace_id = trace_id or str(uuid4())
        row = {
            "trace_id": trace_id,
            "action_type": str(action_type),
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "amount": float(amount),
            "status": "PENDING",
            "created_at": _now_iso(),
            "settled_at": None,
            "metadata": metadata or {},
        }
        try:
            self._ledger.insert_one(row)
            logger.debug("[BillingLedger] PENDING trace_id=%s action=%s user=%s", trace_id, action_type, user_id)
            return trace_id
        except Exception as exc:
            # Write BILLING_WRITE_FAIL alert using the injected sentinel collection
            try:
                self._sentinel.insert_one({
                    "event_type": "BILLING_WRITE_FAIL",
                    "trace_id": trace_id,
                    "user_id": str(user_id),
                    "action_type": action_type,
                    "error": str(exc)[:500],
                    "timestamp": _now_iso(),
                })
            except Exception as alert_exc:
                logger.error("[BillingLedger] BILLING_WRITE_FAIL alert could not be persisted: %s", alert_exc)
            raise BillingLedgerWriteError(
                f"Ledger write failed for action={action_type} user={user_id}: {exc}"
            ) from exc

    def settle_action(self, trace_id: str) -> None:
        """Step 3: Mark ledger row SETTLED after successful execution."""
        self._ledger.update_one(
            {"trace_id": trace_id},
            {"$set": {"status": "SETTLED", "settled_at": _now_iso()}},
        )
        logger.debug("[BillingLedger] SETTLED trace_id=%s", trace_id)

    def fail_action(self, trace_id: str, error: str = "") -> None:
        """Mark ledger row FAILED if execution errored after the write."""
        self._ledger.update_one(
            {"trace_id": trace_id},
            {"$set": {"status": "FAILED", "settled_at": _now_iso(), "error": str(error)[:500]}},
        )
        logger.warning("[BillingLedger] FAILED trace_id=%s error=%s", trace_id, error)

    # ── Context manager (recommended usage) ───────────────────────────────────

    @contextmanager
    def billable_action(
        self,
        *,
        action_type: str,
        user_id: str,
        tenant_id: str,
        amount: float,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """
        Context manager enforcing write → execute → settle ordering.

        Usage:
            with billing_ledger.billable_action(
                action_type="SUBSCRIPTION_ACTIVATE",
                user_id=user_id, tenant_id=tenant_id, amount=39.00,
            ) as trace_id:
                # execute the action here
                activate_subscription(user_id)

        If the ledger write fails, BillingLedgerWriteError is raised before
        entering the with-block — the action is never executed.
        """
        tid = self.begin_billable_action(
            action_type=action_type,
            user_id=user_id,
            tenant_id=tenant_id,
            amount=amount,
            trace_id=trace_id,
            metadata=metadata,
        )
        try:
            yield tid
            self.settle_action(tid)
        except BillingLedgerWriteError:
            raise  # already alerted; do not double-log
        except Exception as exc:
            self.fail_action(tid, str(exc))
            raise

    # ── State-change log ──────────────────────────────────────────────────────

    def log_state_change(
        self,
        *,
        user_id: str,
        event_type: str,
        trace_id: str,
        old_tier: Optional[str] = None,
        new_tier: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append to billing_state_change_log (subscription lifecycle events)."""
        try:
            change_id = str(uuid4())
            db["billing_state_change_log"].insert_one({
                "id": change_id,
                "change_id": change_id,
                "user_id": str(user_id),
                "event_type": str(event_type),
                "trace_id": trace_id,
                "old_tier": old_tier,
                "new_tier": new_tier,
                "stripe_subscription_id": stripe_subscription_id,
                "metadata": metadata or {},
                "created_at": _now_iso(),
            })
        except Exception as exc:
            logger.error("[BillingLedger] state_change log failed: %s", exc)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_ledger_row(self, trace_id: str) -> Optional[Dict[str, Any]]:
        row = self._ledger.find_one({"trace_id": trace_id}, {"_id": 0})
        return row


class BillingLedgerWriteError(RuntimeError):
    """Raised when the billing_ledger PENDING row cannot be inserted."""
    pass


# Module-level singleton (uses real DB when imported normally)
billing_ledger = BillingLedgerService()
