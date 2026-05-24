"""
Phase 4F – Grading Agent Routes
POST /api/phase4/grade/{decision_id}  — agent-only, blocks manual overrides
POST /api/phase4/grade/batch          — agent-only batch job
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from services.phase4_grading_agent import (
    AGENT_ID,
    GradingAgent,
    ManualGradeOverrideError,
    grading_agent,
)

router = APIRouter(prefix="/api/phase4/grade", tags=["phase4-grading-agent"])


def _require_agent_identity(
    x_agent_id: str = Header(default="", alias="X-Agent-Id"),
) -> None:
    """
    Dependency: reject any request whose X-Agent-Id header != agent.grading.v1.
    On rejection: grading_agent.reject_manual_attempt() logs CRITICAL and raises.
    """
    if x_agent_id != AGENT_ID:
        try:
            grading_agent.reject_manual_attempt(
                decision_id="(header check)",
                source="http_route_guard",
                requester=x_agent_id or "anonymous",
            )
        except ManualGradeOverrideError as exc:
            raise HTTPException(status_code=403, detail=str(exc))


@router.post(
    "/{decision_id}",
    summary="Grade a Phase-4 decision (agent.grading.v1 only)",
    dependencies=[Depends(_require_agent_identity)],
)
def grade_decision(decision_id: str, force_regrade: bool = False):
    """
    Grade a single Phase-4 decision.

    ONLY callable with header  X-Agent-Id: agent.grading.v1.
    Any other caller receives HTTP 403 + CRITICAL sentinel log.
    """
    result = grading_agent.run_grade(decision_id, force_regrade=force_regrade)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found or game not yet final",
        )
    return result


@router.post(
    "/batch",
    summary="Batch-grade all pending Phase-4 decisions (agent.grading.v1 only)",
    dependencies=[Depends(_require_agent_identity)],
)
def batch_grade():
    """
    Grade all ungraded EDGE + LEAN Phase-4 decisions.

    ONLY callable with header  X-Agent-Id: agent.grading.v1.
    """
    counts = grading_agent.run_batch_grade()
    return {"status": "complete", "counts": counts, "agent_id": AGENT_ID}
