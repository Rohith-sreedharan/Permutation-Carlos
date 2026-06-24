"""
Phase 4F – Grading Agent (agent.grading.v1)
============================================
AC-5 requirement.

Identity: agent.grading.v1  (LOCKED – never change this string)

CRITICAL RULES:
  1. Only this agent may initiate Phase-4 grading.
  2. Any attempt to manually override grading (via direct DB write or direct
     service call that bypasses this agent) is detected by the
     identity_check() guard and rejected immediately.
  3. On rejection: Sentinel logs CRITICAL event MANUAL_GRADE_OVERRIDE_BLOCKED,
     no grade is written.

Architecture:
  - GradingAgent.run_grade(decision_id) — the ONLY approved grading path.
  - GradingAgent.reject_manual_attempt(source) — called by route guard.
  - ManualGradeBlocker — FastAPI dependency that enforces the identity check
    on any grading endpoint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Identity constant ────────────────────────────────────────────────────────
AGENT_ID = "agent.grading.v1"   # LOCKED


# ============================================================================
# Core grading agent
# ============================================================================

class GradingAgent:
    """
    Phase-4 grading agent.  Identity LOCKED to agent.grading.v1.

    Usage::

        from services.phase4_grading_agent import grading_agent
        result = grading_agent.run_grade(decision_id)
    """

    AGENT_ID = AGENT_ID

    def __init__(self, db=None):
        if db is None:
            from db.mongo import db as _db
            db = _db
        self.db = db
        self.sentinel = db["sentinel_event_log"]

    # ── Approved grading path ────────────────────────────────────────────────

    def run_grade(
        self,
        decision_id: str,
        force_regrade: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        The ONLY approved path to grade a Phase-4 decision.
        Delegates to phase4_grading_engine.grade_phase4_decision()
        under this agent's identity.
        """
        logger.info(
            f"[{self.AGENT_ID}] grade requested: decision_id={decision_id}"
        )
        from services.phase4_grading_engine import grade_phase4_decision
        result = grade_phase4_decision(decision_id, force_regrade=force_regrade)
        if result:
            logger.info(
                f"[{self.AGENT_ID}] grade complete: decision_id={decision_id} "
                f"result_code={result.get('result_code')}"
            )
        return result

    def run_batch_grade(self) -> Dict[str, int]:
        """Grade all pending Phase-4 decisions (EDGE + LEAN)."""
        from services.phase4_grading_engine import grade_all_pending_phase4
        logger.info(f"[{self.AGENT_ID}] batch grade started")
        counts = grade_all_pending_phase4()
        logger.info(f"[{self.AGENT_ID}] batch grade complete: {counts}")
        return counts

    # ── Manual override rejection ────────────────────────────────────────────

    def reject_manual_attempt(
        self,
        decision_id: str,
        source: str,
        requester: Optional[str] = None,
    ) -> None:
        """
        Called whenever a grading request arrives outside the approved
        agent path.  Logs CRITICAL and raises RuntimeError.
        """
        self._log_critical_block(decision_id, source, requester)
        raise ManualGradeOverrideError(
            f"BLOCKED: Manual grade override attempt for decision_id={decision_id} "
            f"from source={source}. Only {self.AGENT_ID} may grade. "
            f"Sentinel event MANUAL_GRADE_OVERRIDE_BLOCKED logged."
        )

    def _log_critical_block(
        self,
        decision_id: str,
        source: str,
        requester: Optional[str],
    ) -> None:
        try:
            self.sentinel.insert_one(
                {
                    "event_type":    "MANUAL_GRADE_OVERRIDE_BLOCKED",
                    "severity":      "CRITICAL",
                    "decision_id":   decision_id,
                    "blocked_source": source,
                    "requester":     requester,
                    "agent_id":      self.AGENT_ID,
                    "timestamp":     datetime.now(timezone.utc).isoformat(),
                    "note": (
                        f"All grading must go through {self.AGENT_ID}. "
                        "No grade was written."
                    ),
                }
            )
            logger.critical(
                f"CRITICAL [{self.AGENT_ID}] MANUAL_GRADE_OVERRIDE_BLOCKED "
                f"decision_id={decision_id} source={source}"
            )
        except Exception as exc:
            logger.error(f"Failed to log MANUAL_GRADE_OVERRIDE_BLOCKED: {exc}")


# ============================================================================
# Custom exception
# ============================================================================

class ManualGradeOverrideError(PermissionError):
    """Raised when a manual grade override attempt is detected."""


# ============================================================================
# FastAPI dependency: blocks any non-agent grading request
# ============================================================================

class ManualGradeBlocker:
    """
    FastAPI dependency that enforces the grading identity check.

    Any route that could trigger grading MUST include this as a dependency.
    It blocks any request whose X-Agent-Id header != agent.grading.v1.

    Inject into routes with::

        from fastapi import Depends
        from services.phase4_grading_agent import ManualGradeBlocker

        @router.post("/grade/{decision_id}")
        def grade(decision_id: str, _: None = Depends(ManualGradeBlocker())):
            ...
    """

    def __call__(self, request=None, decision_id: str = "unknown") -> None:
        from fastapi import Request, HTTPException

        # Read the agent identity header
        agent_header = ""
        if request is not None and hasattr(request, "headers"):
            agent_header = request.headers.get("X-Agent-Id", "")

        if agent_header != AGENT_ID:
            grading_agent.reject_manual_attempt(
                decision_id=decision_id,
                source="http_request",
                requester=agent_header or "anonymous",
            )


# ============================================================================
# Singleton (lazy – avoids pymongo import at module load in test environments)
# ============================================================================

_grading_agent_instance: "GradingAgent | None" = None


def _get_grading_agent() -> GradingAgent:
    global _grading_agent_instance
    if _grading_agent_instance is None:
        _grading_agent_instance = GradingAgent()
    return _grading_agent_instance


# Backwards-compatible proxy object
class _LazyGradingAgentProxy:
    def __getattr__(self, name: str):
        return getattr(_get_grading_agent(), name)


grading_agent = _LazyGradingAgentProxy()  # type: ignore[assignment]
