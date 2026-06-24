from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from services.phase8_operator_auth import require_operator, create_operator_token, decode_operator_token
from services.phase8_recovery_agent import evaluate_recovery, latest_recovery, operator_approve_recovery
from services.phase8_approval_queue import (
    create_approval_request,
    decide_approval,
    get_pending_approvals,
    get_recent_approval_events,
)
from services.phase8_response_agent import log_response_action
from services.phase8_observability_metrics import prometheus_metrics_text
from config.agent_config import AGENT_CONFIG
from db.mongo import db

router = APIRouter(prefix="/api/phase8", tags=["phase8"])


def _extract_heartbeat_utc(event: Optional[Dict[str, Any]]) -> Optional[str]:
    if not event:
        return None
    for key in (
        "heartbeat_at_utc",
        "timestamp_utc",
        "created_at_utc",
        "logged_at_utc",
        "timestamp",
        "graded_at",
        "sent_at_utc",
        "created_at",
    ):
        value = event.get(key)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str) and value:
            return value
    return None


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
    try:
        return create_approval_request(
            queue_type=req.queue_type,
            requested_by_agent=req.requested_by_agent,
            trace_id=req.trace_id,
            payload=req.payload,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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


class IssueTokenRequest(BaseModel):
    operator_id: str


@router.post("/approvals/issue-token")
def approvals_issue_token(req: IssueTokenRequest):
    team = AGENT_CONFIG["phase8"].get("OPERATOR_TEAM", AGENT_CONFIG["phase8"].get("operator_team", []))
    if req.operator_id not in team:
        raise HTTPException(status_code=403, detail="Operator is not authorized")
    token = create_operator_token(req.operator_id)
    claims = decode_operator_token(token)
    return {
        "token": token,
        "claims": {
            "operator_id": claims.get("operator_id"),
            "role": claims.get("role"),
            "exp": claims.get("exp"),
        },
    }


class ApprovalActionRequest(BaseModel):
    approval_id: str
    trace_id: Optional[str] = None
    note: Optional[str] = None


@router.post("/approvals/approve")
def approvals_approve(req: ApprovalActionRequest, operator=Depends(require_operator)):
    try:
        return decide_approval(
            approval_id=req.approval_id,
            decision="approved",
            operator_id=operator["operator_id"],
            trace_id=req.trace_id,
            note=req.note,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/approvals/reject")
def approvals_reject(req: ApprovalActionRequest, operator=Depends(require_operator)):
    try:
        return decide_approval(
            approval_id=req.approval_id,
            decision="rejected",
            operator_id=operator["operator_id"],
            trace_id=req.trace_id,
            note=req.note,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/approvals/events")
def approvals_events(limit: int = Query(default=50, le=500), _operator=Depends(require_operator)):
    return {"rows": get_recent_approval_events(limit=limit)}


@router.get("/approvals/validate")
def approvals_validate(operator=Depends(require_operator)):
    return {
        "ok": True,
        "operator_id": operator.get("operator_id"),
        "role": operator.get("role"),
    }


@router.get("/dashboard/overview")
def dashboard_overview(_operator=Depends(require_operator)):
    now_rows = {
        "sentinel_events": list(db["sentinel_event_log"].find({}, {"_id": 0}).sort("timestamp", -1).limit(50)),
        "response_actions": list(db["response_action_log"].find({}, {"_id": 0}).sort("timestamp_utc", -1).limit(20)),
        "recovery_actions": list(db["recovery_action_log"].find({}, {"_id": 0}).sort("created_at_utc", -1).limit(20)),
    }

    team = AGENT_CONFIG["phase8"].get("OPERATOR_TEAM", AGENT_CONFIG["phase8"].get("operator_team", []))
    agent_grid = [
        {"agent_id": "agent.sentinel.v1", "collection": "sentinel_event_log", "field": "agent_id"},
        {"agent_id": "agent.response.v1", "collection": "response_action_log", "field": "agent_id"},
        {"agent_id": "agent.recovery.v1", "collection": "recovery_action_log", "field": "agent_id"},
        {"agent_id": "agent.grading.v1", "collection": "decision_settlement_metrics", "field": "graded_by"},
        {"agent_id": "agent.calibration.v1", "collection": "calibration_audit_log", "field": "agent_id"},
        {"agent_id": "agent.distribution.v1", "collection": "distribution_audit_log", "field": "agent_id"},
        {"agent_id": "agent.growth.v1", "collection": "outbound_communication_log", "field": "agent_id"},
    ]

    states = []
    for row in agent_grid:
        col = db[row["collection"]]
        total = col.count_documents({row["field"]: row["agent_id"]})
        latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("timestamp", -1)])
        if latest is None:
            latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("timestamp_utc", -1)])
        if latest is None:
            latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("created_at_utc", -1)])
        if latest is None:
            latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("logged_at_utc", -1)])
        if latest is None:
            latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("graded_at", -1)])
        if latest is None:
            latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("sent_at_utc", -1)])
        if latest is None:
            latest = col.find_one({row["field"]: row["agent_id"]}, {"_id": 0}, sort=[("created_at", -1)])
        states.append({
            "agent_id": row["agent_id"],
            "status": "ACTIVE" if total > 0 else "PAUSED",
            "last_heartbeat_utc": _extract_heartbeat_utc(latest),
            "recent_event_count": total,
            "latest_event": latest,
        })

    return {
        "agent_status_grid": states,
        "sentinel_events": now_rows["sentinel_events"],
        "response_actions": now_rows["response_actions"],
        "recovery_actions": now_rows["recovery_actions"],
        "pending_approvals": get_pending_approvals(limit=100),
        "config_viewer": {
            "phase8": AGENT_CONFIG.get("phase8", {}),
            "operator_team": team,
        },
    }


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


@router.get("/metrics")
def phase8_metrics():
    """Prometheus scrape endpoint for Phase 8 observability stack."""
    content = prometheus_metrics_text()
    return Response(content=content, media_type="text/plain; version=0.0.4")
