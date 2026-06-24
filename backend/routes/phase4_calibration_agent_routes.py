"""
Phase 4G – Calibration Agent Routes
POST /api/phase4/calibration/propose
POST /api/phase4/calibration/{proposal_id}/approve
POST /api/phase4/calibration/{proposal_id}/promote
GET  /api/phase4/calibration/{proposal_id}
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from services.phase4_calibration_agent import (
    AGENT_ID,
    CalibrationApprovalError,
    CalibrationPromotionError,
    CalibrationProposalError,
    calibration_agent,
)

router = APIRouter(prefix="/api/phase4/calibration", tags=["phase4-calibration-agent"])


# ── Request models ────────────────────────────────────────────────────────────

class ProposeRequest(BaseModel):
    training_days: int = 30
    method: str = "isotonic"
    notes: Optional[str] = None


class ApproveRequest(BaseModel):
    approver_id: str


class PromoteRequest(BaseModel):
    promoted_by: str


# ── Agent identity check (propose only) ──────────────────────────────────────

def _require_calibration_agent(
    x_agent_id: str = Header(default="", alias="X-Agent-Id"),
) -> None:
    if x_agent_id != AGENT_ID:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Forbidden: calibration proposal requires "
                f"X-Agent-Id: {AGENT_ID}. Got: '{x_agent_id}'"
            ),
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/propose",
    summary="Propose a new calibration version (agent.calibration.v1 only)",
    dependencies=[Depends(_require_calibration_agent)],
)
def propose_calibration(body: ProposeRequest):
    """
    Train a new calibration model and write it to the promotion queue
    with status=PENDING_APPROVAL.

    Requires X-Agent-Id: agent.calibration.v1.
    Blocks if N < 500 graded decisions are available.
    """
    try:
        proposal = calibration_agent.propose_calibration(
            training_days=body.training_days,
            method=body.method,
            notes=body.notes,
        )
        return {"status": "proposed", "proposal": proposal}
    except CalibrationProposalError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{proposal_id}/approve",
    summary="Human approval for a calibration proposal (requires 2 distinct approvers)",
)
def approve_proposal(proposal_id: str, body: ApproveRequest):
    """
    Record a human approval.
    Two distinct approvers are required before promotion is allowed.
    """
    try:
        updated = calibration_agent.human_approve(
            proposal_id=proposal_id,
            approver_id=body.approver_id,
        )
        return {"status": "approval_recorded", "proposal": updated}
    except CalibrationApprovalError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/{proposal_id}/promote",
    summary="Promote a READY calibration version to ACTIVE (dual-approval gate)",
)
def promote_proposal(proposal_id: str, body: PromoteRequest):
    """
    Promote a READY proposal to ACTIVE.
    Blocked unless exactly REQUIRED_APPROVALS (2) distinct approvals exist.
    Calibration immutability guard fires before any ACTIVE record is retired.
    """
    try:
        result = calibration_agent.promote_calibration(
            proposal_id=proposal_id,
            promoted_by=body.promoted_by,
        )
        return {"status": "promoted", "result": result}
    except CalibrationPromotionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/{proposal_id}",
    summary="Get calibration proposal status",
)
def get_proposal(proposal_id: str):
    proposal = calibration_agent.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal
