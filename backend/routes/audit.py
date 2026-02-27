"""
Audit Log Query Endpoint
Section 14 - ENGINE LOCK Specification Compliance

Provides read-only access to decision audit logs.
Used for institutional compliance verification and debugging.

NOTE: Collection is append-only. No deletion/update endpoints permitted.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from backend.db.decision_audit_logger import get_decision_audit_logger

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditLogEntry(BaseModel):
    """Audit log entry response model."""
    event_id: str
    inputs_hash: str
    decision_version: str
    classification: Optional[str]
    release_status: str
    edge_points: Optional[float]
    model_prob: Optional[float]
    timestamp: str
    trace_id: str
    engine_version: str
    market_type: str
    league: str
    retention_expires_at: str
    logged_at_unix: float
    metadata: Optional[dict] = None


@router.get("/decisions/{event_id}", response_model=List[AuditLogEntry])
async def get_decision_audit_logs(
    event_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Max results to return")
):
    """
    Query audit logs for a specific event.
    
    Returns all decision logs for the given event_id.
    Useful for:
    - Verifying decision determinism (same inputs → same output)
    - Tracing decision history over time
    - Institutional compliance audits
    
    Args:
        event_id: The event ID to query
        limit: Maximum number of results (default 100, max 1000)
    
    Returns:
        List of audit log entries, newest first
    """
    try:
        logger = get_decision_audit_logger()
        logs = logger.query_by_event(event_id, limit=limit)
        
        # Convert MongoDB documents to response model
        return [
            AuditLogEntry(
                event_id=log["event_id"],
                inputs_hash=log["inputs_hash"],
                decision_version=log["decision_version"],
                classification=log.get("classification"),
                release_status=log["release_status"],
                edge_points=log.get("edge_points"),
                model_prob=log.get("model_prob"),
                timestamp=log["timestamp"],
                trace_id=log["trace_id"],
                engine_version=log["engine_version"],
                market_type=log["market_type"],
                league=log["league"],
                retention_expires_at=log["retention_expires_at"],
                logged_at_unix=log["logged_at_unix"],
                metadata=log.get("metadata")
            )
            for log in logs
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query audit logs: {str(e)}"
        )


@router.get("/trace/{trace_id}", response_model=List[AuditLogEntry])
async def get_trace_audit_logs(
    trace_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Max results to return")
):
    """
    Query audit logs by trace ID.
    
    Returns all decision logs for a given trace_id.
    Useful for:
    - Debugging multi-decision workflows
    - Tracing decision pipeline execution
    - Analyzing batch decision operations
    
    Args:
        trace_id: The trace ID to query
        limit: Maximum number of results (default 100, max 1000)
    
    Returns:
        List of audit log entries, newest first
    """
    try:
        logger = get_decision_audit_logger()
        logs = logger.query_by_trace_id(trace_id, limit=limit)
        
        return [
            AuditLogEntry(
                event_id=log["event_id"],
                inputs_hash=log["inputs_hash"],
                decision_version=log["decision_version"],
                classification=log.get("classification"),
                release_status=log["release_status"],
                edge_points=log.get("edge_points"),
                model_prob=log.get("model_prob"),
                timestamp=log["timestamp"],
                trace_id=log["trace_id"],
                engine_version=log["engine_version"],
                market_type=log["market_type"],
                league=log["league"],
                retention_expires_at=log["retention_expires_at"],
                logged_at_unix=log["logged_at_unix"],
                metadata=log.get("metadata")
            )
            for log in logs
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query audit logs: {str(e)}"
        )


@router.get("/history/{event_id}/{inputs_hash}", response_model=List[AuditLogEntry])
async def get_decision_history(
    event_id: str,
    inputs_hash: str,
    limit: int = Query(100, ge=1, le=1000, description="Max results to return")
):
    """
    Query decision history for identical inputs.
    
    Returns all decisions for the same event_id + inputs_hash combination.
    Used to verify determinism: same inputs should produce same output.
    
    Args:
        event_id: The event ID
        inputs_hash: Hash of the decision inputs
        limit: Maximum number of results (default 100, max 1000)
    
    Returns:
        List of audit log entries, newest first
    """
    try:
        logger = get_decision_audit_logger()
        logs = logger.get_decision_history(event_id, inputs_hash, limit=limit)
        
        return [
            AuditLogEntry(
                event_id=log["event_id"],
                inputs_hash=log["inputs_hash"],
                decision_version=log["decision_version"],
                classification=log.get("classification"),
                release_status=log["release_status"],
                edge_points=log.get("edge_points"),
                model_prob=log.get("model_prob"),
                timestamp=log["timestamp"],
                trace_id=log["trace_id"],
                engine_version=log["engine_version"],
                market_type=log["market_type"],
                league=log["league"],
                retention_expires_at=log["retention_expires_at"],
                logged_at_unix=log["logged_at_unix"],
                metadata=log.get("metadata")
            )
            for log in logs
        ]
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query decision history: {str(e)}"
        )
