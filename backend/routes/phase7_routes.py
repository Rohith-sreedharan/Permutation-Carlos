"""
Phase 7 API routes:
  GET  /api/phase7/performance                        — 7A: main metrics endpoint
  POST /api/phase7/sentinel/write-attempt             — 7B: AC-1 block + log
  GET  /api/phase7/performance/trace/{metric_key}     — 7A: AC-3 traceability
  GET  /api/phase7/sentinel/suppression-log           — 7B: AC-2 evidence
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.phase7_trust_record import get_performance_metrics, trace_metric
from services.phase7_sentinel_monitors import (
    check_write_attempt,
    check_sample_gate,
    check_page_availability,
    get_suppression_log,
)

router = APIRouter(prefix="/api/phase7", tags=["phase7"])


# ─────────────────────────────────────────────────────────────────────────────
# 7A: Public Trust Record
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/performance")
def performance_endpoint():
    """
    Public performance dashboard — all metrics sample-gated (N≥50 per segment).
    Every response includes:
      - disclosure: "Past performance does not guarantee future results…"
      - powered_by: "Powered by agentic simulation"
            - response_hash: SHA256 of sorted metrics JSON (logged to system_performance)
    """
    try:
        return get_performance_metrics()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/performance/trace/{metric_key:path}")
def trace_metric_endpoint(
    metric_key: str,
    response_hash: str = Query(..., description="response_hash from the API call you want to trace"),
):
    """
    AC-3: Trace a metric key back through the full chain:
            API response → system_performance → source table → decisions.snapshot_hash
    """
    result = trace_metric(metric_key, response_hash)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 7B: AOS Trust Monitoring Sentinel
# ─────────────────────────────────────────────────────────────────────────────

class WriteAttemptRequest(BaseModel):
    collection_name: str
    actor: str
    action: str
    trace_id: Optional[str] = None


@router.post("/sentinel/write-attempt")
def sentinel_write_attempt(req: WriteAttemptRequest):
    """
    AC-1: Attempt a manual write to a truth-source collection.
    Protected collections (truth_dataset, grading, calibration_versions,
    calibration_segments, calibration_audit_log)
    are unconditionally blocked.  Every attempt — allowed or blocked — is logged
    to sentinel_event_log with CRITICAL severity.
    """
    result = check_write_attempt(
        collection_name=req.collection_name,
        actor=req.actor,
        action=req.action,
        trace_id=req.trace_id,
    )
    # Always 200 — the block is conveyed in the response body for audit/evidence
    return result


class SampleGateRequest(BaseModel):
    segment_key: str
    n_actual: int
    n_required: int
    trace_id: Optional[str] = None


@router.post("/sentinel/sample-gate-check")
def sentinel_sample_gate(req: SampleGateRequest):
    """Check and log sample gate suppression for the given segment."""
    return check_sample_gate(
        segment_key=req.segment_key,
        n_actual=req.n_actual,
        n_required=req.n_required,
        trace_id=req.trace_id,
    )


class PageAvailabilityRequest(BaseModel):
    status_code: int
    response_time_ms: float
    page_path: str = "/performance"
    trace_id: Optional[str] = None


@router.post("/sentinel/page-availability")
def sentinel_page_availability(req: PageAvailabilityRequest):
    """Log and evaluate /performance page availability probe result."""
    return check_page_availability(
        status_code=req.status_code,
        response_time_ms=req.response_time_ms,
        page_path=req.page_path,
        trace_id=req.trace_id,
    )


@router.get("/sentinel/suppression-log")
def suppression_log_endpoint(limit: int = Query(50, le=200)):
    """
    AC-2 evidence: Returns the most recent sample-gate suppression events
    and manual-write-blocked events from sentinel_event_log.
    """
    return {
        "events": get_suppression_log(limit=limit),
        "count": limit,
    }
