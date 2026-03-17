"""Billing state writer service.

This service is the single writer for `billing_state` and
`billing_state_change_log` collections.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db


class BillingStateService:
    """Owns all writes for billing state and billing change logs."""

    def __init__(self, billing_state_collection=None, change_log_collection=None) -> None:
        self._billing_state = billing_state_collection or db["billing_state"]
        self._change_log = change_log_collection or db["billing_state_change_log"]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._billing_state.find_one({"user_id": user_id})

    def upsert_state(self, user_id: str, updates: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Upsert billing state and write one change-log row per changed field."""
        existing = self.get_state(user_id) or {}
        now = self._now_iso()

        next_state = {
            **existing,
            **updates,
            "user_id": user_id,
            "updated_at_utc": now,
        }

        self._billing_state.update_one({"user_id": user_id}, {"$set": next_state}, upsert=True)

        changed_fields = [
            key
            for key, value in updates.items()
            if existing.get(key) != value
        ]

        for field_name in changed_fields:
            self._change_log.insert_one(
                {
                    "change_id": str(uuid4()),
                    "user_id": user_id,
                    "trace_id": trace_id,
                    "field_changed": field_name,
                    "old_value": existing.get(field_name),
                    "new_value": updates.get(field_name),
                    "created_at_utc": now,
                }
            )

        return next_state


billing_state_service = BillingStateService()
