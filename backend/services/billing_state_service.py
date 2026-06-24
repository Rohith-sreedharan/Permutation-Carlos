"""Append-only billing ledger service.

This service is the single writer for `billing_ledger`.
No mutable balance state is persisted; balance is derived from ledger sums.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db


class BillingLedgerService:
    """Owns append-only writes for billing ledger rows."""

    def __init__(self, ledger_collection=None) -> None:
        self._ledger = ledger_collection or db["billing_ledger"]
        self._ledger.create_index("id", unique=True)
        self._ledger.create_index([("user_id", 1), ("created_at", -1)])
        self._ledger.create_index([("reference_id", 1)])
        self._ledger.create_index([("event_type", 1), ("created_at", -1)])

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def append_ledger_entry(
        self,
        user_id: str,
        event_type: str,
        amount: float,
        reference_id: str,
    ) -> Dict[str, Any]:
        """Append one immutable billing ledger row."""
        normalized_event_type = str(event_type).upper()
        if normalized_event_type not in {"CHARGE", "CREDIT", "USAGE"}:
            raise ValueError("event_type must be one of CHARGE, CREDIT, USAGE")

        row = {
            "id": str(uuid4()),
            "user_id": str(user_id),
            "event_type": normalized_event_type,
            "amount": float(amount),
            "reference_id": str(reference_id),
            "created_at": self._now_iso(),
        }
        self._ledger.insert_one(row)
        return row

    def get_derived_balance(self, user_id: str) -> float:
        """Compute balance from SUM(ledger.amount) for a user."""
        pipeline = [
            {"$match": {"user_id": str(user_id)}},
            {"$group": {"_id": None, "balance": {"$sum": "$amount"}}},
        ]
        result = list(self._ledger.aggregate(pipeline))
        if not result:
            return 0.0
        return float(result[0].get("balance", 0.0))


billing_ledger_service = BillingLedgerService()
