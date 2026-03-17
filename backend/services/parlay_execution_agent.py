"""Parlay execution writer agent.

This service is the single writer for `parlay_execution_log` and
`parlay_overage_charge_log` collections.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db


class ParlayExecutionAgent:
    """Owns all writes for parlay execution and overage charge logs."""

    def __init__(self, execution_log_collection=None, overage_log_collection=None) -> None:
        self._execution_log = execution_log_collection or db["parlay_execution_log"]
        self._overage_log = overage_log_collection or db["parlay_overage_charge_log"]

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_execution_event(
        self,
        run_id: str,
        user_id: str,
        trace_id: str,
        decision_id: Optional[str],
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        event_id = str(uuid4())
        self._execution_log.insert_one(
            {
                "event_id": event_id,
                "run_id": run_id,
                "user_id": user_id,
                "trace_id": trace_id,
                "decision_id": decision_id,
                "event_type": event_type,
                "payload": payload or {},
                "created_at_utc": self._now_iso(),
            }
        )
        return event_id

    def log_overage_charge(
        self,
        parlay_run_id: str,
        user_id: str,
        trace_id: str,
        billing_period_start: str,
        token_shortfall: int,
        charge_usd: float,
    ) -> str:
        charge_id = str(uuid4())
        self._overage_log.insert_one(
            {
                "charge_id": charge_id,
                "parlay_run_id": parlay_run_id,
                "user_id": user_id,
                "trace_id": trace_id,
                "billing_period_start": billing_period_start,
                "token_shortfall": token_shortfall,
                "charge_usd": charge_usd,
                "created_at_utc": self._now_iso(),
            }
        )
        return charge_id


parlay_execution_agent = ParlayExecutionAgent()
