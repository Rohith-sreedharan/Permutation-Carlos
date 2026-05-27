from __future__ import annotations

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from services.phase8_operator_auth import require_operator
from services.phase8_recovery_agent import evaluate_recovery, latest_recovery, operator_approve_recovery
from services.phase8_approval_queue import (
    create_approval_request,
    decide_approval,
    get_pending_approvals,
    get_recent_approval_events,
)
from services.phase8_response_agent import log_response_action

router = APIRouter(prefix="/api/phase8", tags=["phase8"])


class RecoveryEvalRequest(BaseModel):
    triggered_by_action_id: str
    severity: str
    recovery_type: str
    trace_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@router.post("/recovery/evaluate")
def recovery_evaluate(req: RecoveryEvalRequest):
    try:
        return evaluate_recovery(
            triggered_by_action_id=req.triggered_by_action_id,
            severity=req.severity,
            recovery_type=req.recovery_type,
            trace_id=req.trace_id,
            details=req.details,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/recovery/latest")
def recovery_latest(limit: int = Query(default=20, le=200)):
    return {"rows": latest_recovery(limit=limit)}


class RecoveryApproveRequest(BaseModel):
    recovery_id: str


@router.post("/recovery/approve")
def recovery_approve(req: RecoveryApproveRequest, operator=Depends(require_operator)):
    try:
        return operator_approve_recovery(
            recovery_id=req.recovery_id,
            operator_id=operator["operator_id"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class ApprovalCreateRequest(BaseModel):
    queue_type: str
    requested_by_agent: str
    trace_id: str
    payload: Optional[Dict[str, Any]] = None


@router.post("/approvals/create")
def approvals_create(req: ApprovalCreateRequest, _operator=Depends(require_operator)):
    return create_approval_request(
        queue_type=req.queue_type,
        requested_by_agent=req.requested_by_agent,
        trace_id=req.trace_id,
        payload=req.payload,
    )


@router.get("/approvals/pending")
def approvals_pending(limit: int = Query(default=100, le=500), _operator=Depends(require_operator)):
    return {"rows": get_pending_approvals(limit=limit)}


class ApprovalDecisionRequest(BaseModel):
    decision: str
    trace_id: Optional[str] = None
    note: Optional[str] = None


@router.post("/approvals/{approval_id}/decision")
def approvals_decide(approval_id: str, req: ApprovalDecisionRequest, operator=Depends(require_operator)):
    try:
        return decide_approval(
            approval_id=approval_id,
            decision=req.decision,
            operator_id=operator["operator_id"],
            trace_id=req.trace_id,
            note=req.note,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/approvals/events")
def approvals_events(limit: int = Query(default=50, le=500), _operator=Depends(require_operator)):
    return {"rows": get_recent_approval_events(limit=limit)}


class ResponseActionRequest(BaseModel):
    action: str
    reason: str
    trace_id: str
    source_agent_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/response/log-action")
def response_log_action(req: ResponseActionRequest):
    """Writes a canonical response_action_log entry as agent.response.v1."""
    return log_response_action(
        action=req.action,
        reason=req.reason,
        trace_id=req.trace_id,
        source_agent_id=req.source_agent_id,
        metadata=req.metadata,
    )
