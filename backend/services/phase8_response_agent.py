"""
Phase 8 — Response Agent canonical logger (agent.response.v1)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db

AGENT_ID = "agent.response.v1"
_response_action_col = db["response_action_log"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_response_action(
    *,
    action: str,
    reason: str,
    trace_id: str,
    source_agent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = {
        "action_id": str(uuid4()),
        "agent_id": AGENT_ID,
        "action": action,
        "reason": reason,
        "trace_id": trace_id,
        "timestamp_utc": _now_iso(),
        "source_agent_id": source_agent_id,
        "metadata": metadata or {},
    }
    _response_action_col.insert_one({**row})
    return {k: v for k, v in row.items() if k != "_id"}
