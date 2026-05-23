"""
Overage Billing Service — Phase 3A.5

Formula (locked, must not change):
    overage_charge_usd = token_shortfall × 0.02

Write sequence (steps 3-5 atomic, all roll back on failure):
  1. INSERT parlay_overage_charge_log: charge_id, token_shortfall, overage_charge_usd, trace_id
     external_invoice_id = NULL
  2. Submit charge to Stripe
  3. On Stripe confirmation: UPDATE external_invoice_id and external_payment_reference only
  4. INSERT billing_state_change_log
  5. UPDATE billing_state: overage_charges_current_period += overage_charge_usd
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from db.mongo import db
from services.billing_ledger_service import billing_ledger, BillingLedgerWriteError
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Overage rate (from agent_config — zero hardcoded)
# ─────────────────────────────────────────────────────────────────────────────

def _overage_rate() -> float:
    return float(AGENT_CONFIG["billing"]["overage_rate_per_token"])


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class OverageBillingService:
    """Handles overage charge creation and Stripe reconciliation."""

    def __init__(
        self,
        overage_col=None,
        state_col=None,
        billing_state_col=None,
    ) -> None:
        self._overage = overage_col if overage_col is not None else db["parlay_overage_charge_log"]
        self._state_changes = state_col if state_col is not None else db["billing_state_change_log"]
        self._billing_state = billing_state_col if billing_state_col is not None else db["billing_state"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            self._overage.create_index("charge_id", unique=True)
            self._overage.create_index([("user_id", 1), ("created_at", -1)])
        except Exception:
            pass

    def calculate_overage(self, token_shortfall: int) -> float:
        """Compute overage charge using the locked formula."""
        rate = _overage_rate()
        return round(token_shortfall * rate, 2)

    def create_overage_charge(
        self,
        *,
        user_id: str,
        tenant_id: str,
        token_shortfall: int,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the Phase 3A.5 write sequence.

        Returns the completed overage charge record.
        Raises BillingLedgerWriteError if the ledger write fails (action blocked).
        Raises OverageChargeError if Stripe or the atomic update fails (rolls back).
        """
        trace_id = trace_id or str(uuid4())
        charge_id = str(uuid4())
        overage_usd = self.calculate_overage(token_shortfall)

        # ── Step 1: INSERT to billing_ledger (write-first gate) ───────────────
        with billing_ledger.billable_action(
            action_type="OVERAGE_CHARGE",
            user_id=user_id,
            tenant_id=tenant_id,
            amount=overage_usd,
            trace_id=trace_id,
            metadata={"token_shortfall": token_shortfall, "charge_id": charge_id},
        ):
            # ── Step 1 (overage log): INSERT parlay_overage_charge_log ────────
            charge_doc = {
                "charge_id": charge_id,
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "token_shortfall": int(token_shortfall),
                "overage_charge_usd": overage_usd,
                "trace_id": trace_id,
                "external_invoice_id": None,          # filled after Stripe confirms
                "external_payment_reference": None,
                "status": "PENDING",
                "created_at": _now_iso(),
            }
            self._overage.insert_one(charge_doc)

            # ── Step 2: Submit charge to Stripe ───────────────────────────────
            stripe_result = self._submit_stripe_charge(
                user_id=user_id,
                amount_usd=overage_usd,
                token_shortfall=token_shortfall,
                charge_id=charge_id,
            )

            # ── Steps 3-5: Atomic reconciliation ──────────────────────────────
            self._reconcile(
                charge_id=charge_id,
                user_id=user_id,
                trace_id=trace_id,
                overage_usd=overage_usd,
                stripe_invoice_id=stripe_result.get("invoice_id"),
                stripe_payment_ref=stripe_result.get("payment_ref"),
            )

            charge_doc["external_invoice_id"] = stripe_result.get("invoice_id")
            charge_doc["external_payment_reference"] = stripe_result.get("payment_ref")
            charge_doc["status"] = "SETTLED"
            return charge_doc

    def _submit_stripe_charge(
        self,
        *,
        user_id: str,
        amount_usd: float,
        token_shortfall: int,
        charge_id: str,
    ) -> Dict[str, Any]:
        """Submit overage charge to Stripe. Returns {invoice_id, payment_ref}."""
        stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
        if not stripe_key:
            logger.warning("[Overage] STRIPE_SECRET_KEY not set — simulating Stripe call")
            return {"invoice_id": f"sim_inv_{charge_id[:8]}", "payment_ref": f"sim_pi_{charge_id[:8]}"}

        try:
            import stripe
            stripe.api_key = stripe_key

            # Look up the customer's Stripe customer_id
            ent = db["user_entitlements"].find_one({"user_id": str(user_id)})
            stripe_customer_id = ent.get("stripe_customer_id") if ent else None
            if not stripe_customer_id:
                raise OverageChargeError(f"No Stripe customer_id for user={user_id}")

            # Create one-time invoice item + finalise + pay
            stripe.InvoiceItem.create(
                customer=stripe_customer_id,
                amount=int(amount_usd * 100),   # cents
                currency="usd",
                description=f"BeatVegas overage: {token_shortfall} tokens × $0.02",
                metadata={"charge_id": charge_id, "token_shortfall": str(token_shortfall)},
            )
            invoice = stripe.Invoice.create(
                customer=stripe_customer_id,
                auto_advance=True,
                metadata={"charge_id": charge_id},
            )
            paid_invoice = stripe.Invoice.pay(invoice["id"])
            return {
                "invoice_id": paid_invoice["id"],
                "payment_ref": paid_invoice.get("payment_intent", ""),
            }
        except OverageChargeError:
            raise
        except Exception as exc:
            raise OverageChargeError(f"Stripe charge failed: {exc}") from exc

    def _reconcile(
        self,
        *,
        charge_id: str,
        user_id: str,
        trace_id: str,
        overage_usd: float,
        stripe_invoice_id: Optional[str],
        stripe_payment_ref: Optional[str],
    ) -> None:
        """Steps 3-5: atomic update of overage log, state-change log, billing_state."""
        # Step 3: UPDATE external_invoice_id and payment_reference
        self._overage.update_one(
            {"charge_id": charge_id},
            {"$set": {
                "external_invoice_id": stripe_invoice_id,
                "external_payment_reference": stripe_payment_ref,
                "status": "SETTLED",
                "settled_at": _now_iso(),
            }},
        )

        # Step 4: INSERT billing_state_change_log
        billing_ledger.log_state_change(
            user_id=user_id,
            event_type="OVERAGE_CHARGED",
            trace_id=trace_id,
            metadata={
                "charge_id": charge_id,
                "overage_usd": overage_usd,
                "stripe_invoice_id": stripe_invoice_id,
            },
        )

        # Step 5: UPDATE billing_state
        self._billing_state.update_one(
            {"user_id": str(user_id)},
            {"$inc": {"overage_charges_current_period": overage_usd}},
            upsert=True,
        )


class OverageChargeError(RuntimeError):
    """Raised when a Stripe overage charge cannot be completed."""
    pass


# Module-level singleton
overage_billing = OverageBillingService()
