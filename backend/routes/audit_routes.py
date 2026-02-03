"""
Audit API Routes — Investor/Regulator Access

Provides read-only access to immutable audit logs
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.utils.audit_logger import AuditLogger
from backend.core.kill_switch import KillSwitch
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/export")
async def export_audit_logs(
    start_date: Optional[str] = Query(None, description="ISO 8601 start date (e.g., '2026-02-01T00:00:00Z')"),
    end_date: Optional[str] = Query(None, description="ISO 8601 end date"),
    event_id: Optional[str] = Query(None, description="Filter by specific event ID"),
    tier: Optional[str] = Query(None, description="Filter by tier (EDGE/LEAN/MARKET_ALIGNED/NO_PLAY)"),
    verify_signatures: bool = Query(True, description="Verify cryptographic signatures")
):
    """
    Export audit logs for investor/regulator review
    
    **Authentication Required:** Admin or Investor role
    
    Returns:
    - total_records: Number of matching records
    - filters: Applied filters
    - records: Array of audit log entries
    
    Example:
    ```
    GET /api/audit/export?start_date=2026-02-01T00:00:00Z&tier=EDGE
    ```
    """
    try:
        records = AuditLogger.export_logs(
            start_date=start_date,
            end_date=end_date,
            event_id=event_id,
            tier=tier,
            verify_signatures=verify_signatures
        )
        
        return {
            "total_records": len(records),
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "event_id": event_id,
                "tier": tier
            },
            "signature_verification": "enabled" if verify_signatures else "disabled",
            "records": records
        }
    except Exception as e:
        logger.error(f"Failed to export audit logs: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/stats")
async def get_audit_statistics():
    """
    Get audit log statistics
    
    Returns:
    - total_records: Total number of logged simulations
    - file_size_mb: Current log file size
    - oldest_record: Timestamp of oldest record
    - newest_record: Timestamp of newest record
    - tier_breakdown: Count by tier (EDGE/LEAN/etc)
    
    Example:
    ```json
    {
        "total_records": 12543,
        "file_size_mb": 8.32,
        "oldest_record": "2026-02-01T00:00:00Z",
        "newest_record": "2026-02-02T15:30:00Z",
        "tier_breakdown": {
            "EDGE": 1243,
            "LEAN": 3421,
            "NO_PLAY": 7879
        }
    }
    ```
    """
    try:
        stats = AuditLogger.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get audit stats: {e}")
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {str(e)}")


@router.get("/kill-switch/status")
async def get_kill_switch_status():
    """
    Get kill switch status
    
    Returns:
    - active: Whether kill switch is currently active
    - sources: Activation sources (env_var, override_file)
    - activated_at: Timestamp of activation (if active)
    - reason: Reason for activation (if active)
    """
    try:
        status = KillSwitch.get_status()
        return status
    except Exception as e:
        logger.error(f"Failed to get kill switch status: {e}")
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@router.post("/kill-switch/activate")
async def activate_kill_switch(reason: str = "Manual activation via API"):
    """
    Activate kill switch (ADMIN ONLY)
    
    **Authentication Required:** Admin role
    
    Body:
    - reason: Reason for activation
    
    Returns:
    - active: True
    - activated_at: Timestamp
    - reason: Activation reason
    """
    try:
        KillSwitch.activate(reason=reason)
        status = KillSwitch.get_status()
        return {
            "message": "Kill switch activated",
            "status": status
        }
    except Exception as e:
        logger.error(f"Failed to activate kill switch: {e}")
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(e)}")


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch():
    """
    Deactivate kill switch (ADMIN ONLY)
    
    **Authentication Required:** Admin role
    
    Returns:
    - active: False
    - message: Success message
    """
    try:
        KillSwitch.deactivate()
        status = KillSwitch.get_status()
        return {
            "message": "Kill switch deactivated",
            "status": status
        }
    except Exception as e:
        logger.error(f"Failed to deactivate kill switch: {e}")
        raise HTTPException(status_code=500, detail=f"Deactivation failed: {str(e)}")


@router.get("/health")
async def audit_system_health():
    """
    Audit system health check
    
    Returns:
    - audit_logging: Status of audit logging system
    - kill_switch: Status of kill switch
    - log_file_accessible: Whether log file can be written
    """
    try:
        # Test audit log write
        test_simulation = {
            "event_id": "health_check",
            "market_type": "HEALTH_CHECK",
            "selection_id": "test",
            "tier": "TEST",
            "snapshot_hash": "test_hash"
        }
        AuditLogger.log_simulation(test_simulation)
        
        # Get stats
        stats = AuditLogger.get_statistics()
        
        # Get kill switch status
        kill_switch_status = KillSwitch.get_status()
        
        return {
            "audit_logging": "operational",
            "kill_switch": kill_switch_status,
            "log_file_accessible": True,
            "total_audit_records": stats.get("total_records", 0),
            "log_size_mb": stats.get("file_size_mb", 0)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "audit_logging": "error",
            "kill_switch": None,
            "log_file_accessible": False,
            "error": str(e)
        }
