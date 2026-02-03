"""
BeatVegas Audit Logger — Immutable Compliance Log

Provides investor/regulator-grade audit trail of all simulation decisions.

Features:
- Append-only JSON Lines format (immutable)
- Cryptographic signatures for tamper detection
- Export API for investor/auditor review
- Automatic rotation and archival
"""
import json
import hashlib
import hmac
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class AuditLogger:
    """
    Immutable audit log for investor/regulatory compliance
    
    Log Format (JSON Lines):
    {"event_id": "...", "timestamp": "...", "tier": "...", "signature": "..."}
    {"event_id": "...", "timestamp": "...", "tier": "...", "signature": "..."}
    
    Each line is a complete JSON object with cryptographic signature
    """
    
    # Log file location (configurable via env var)
    LOG_DIR = os.environ.get("BEATVEGAS_AUDIT_LOG_DIR", "/var/log/beatvegas")
    LOG_FILE = "audit.jsonl"
    
    # Secret key for HMAC signatures (MUST be set in production)
    SECRET_KEY = os.environ.get("BEATVEGAS_AUDIT_SECRET", "CHANGE_ME_IN_PRODUCTION")
    
    # Max log file size before rotation (10 MB)
    MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024
    
    @classmethod
    def _ensure_log_dir(cls) -> None:
        """Create log directory if it doesn't exist"""
        Path(cls.LOG_DIR).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def _get_log_path(cls) -> str:
        """Get current log file path"""
        cls._ensure_log_dir()
        return os.path.join(cls.LOG_DIR, cls.LOG_FILE)
    
    @classmethod
    def _generate_signature(cls, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for tamper detection
        
        Args:
            payload: JSON string to sign
        
        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            cls.SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @classmethod
    def _verify_signature(cls, payload: str, signature: str) -> bool:
        """
        Verify HMAC signature
        
        Args:
            payload: JSON string (without signature field)
            signature: Claimed signature
        
        Returns:
            True if signature valid, False otherwise
        """
        expected = cls._generate_signature(payload)
        return hmac.compare_digest(expected, signature)
    
    @classmethod
    def log_simulation(cls, simulation: Dict[str, Any]) -> None:
        """
        Log simulation decision to immutable audit log
        
        Required fields:
        - event_id
        - market_type
        - selection_id
        - tier
        - prob_edge
        - snapshot_hash
        
        Generates:
        - timestamp (ISO 8601 UTC)
        - signature (HMAC-SHA256)
        """
        try:
            # Extract required fields
            record = {
                "event_id": simulation.get("event_id"),
                "market_type": simulation.get("market_type", "SPREAD"),
                "selection_id": simulation.get("selection_id"),
                "team_a": simulation.get("team_a"),
                "team_b": simulation.get("team_b"),
                "tier": simulation.get("pick_state") or simulation.get("tier"),
                "prob_edge": simulation.get("prob_edge"),
                "snapshot_hash": simulation.get("snapshot_hash"),
                "iterations": simulation.get("iterations"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                
                # Additional context
                "home_win_prob": simulation.get("team_a_win_probability"),
                "away_win_prob": simulation.get("team_b_win_probability"),
                "sharp_side": simulation.get("sharp_analysis", {}).get("spread", {}).get("sharp_side"),
                "safety_suppressed": simulation.get("safety", {}).get("is_suppressed", False),
                "suppression_reason": simulation.get("safety", {}).get("suppression_reason"),
                
                # User context
                "user_tier": simulation.get("metadata", {}).get("user_tier"),
                "user_id": simulation.get("metadata", {}).get("user_id"),
            }
            
            # Generate payload (JSON without signature)
            payload_json = json.dumps(record, sort_keys=True)
            
            # Generate signature
            signature = cls._generate_signature(payload_json)
            
            # Add signature to record
            record["signature"] = signature
            
            # Write to log file (append-only)
            log_path = cls._get_log_path()
            with open(log_path, 'a') as f:
                f.write(json.dumps(record) + '\n')
            
            # Check if rotation needed
            cls._rotate_if_needed()
            
            logger.debug(f"✅ Audit log written: {record['event_id']} - {record['tier']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to write audit log: {e}")
            # Don't raise - audit logging failure shouldn't break simulation
    
    @classmethod
    def _rotate_if_needed(cls) -> None:
        """Rotate log file if it exceeds max size"""
        log_path = cls._get_log_path()
        
        if not os.path.exists(log_path):
            return
        
        file_size = os.path.getsize(log_path)
        
        if file_size > cls.MAX_LOG_SIZE_BYTES:
            # Generate archive filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_name = f"audit_{timestamp}.jsonl"
            archive_path = os.path.join(cls.LOG_DIR, archive_name)
            
            # Rename current log to archive
            os.rename(log_path, archive_path)
            
            logger.info(f"📦 Audit log rotated: {archive_path}")
    
    @classmethod
    def export_logs(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_id: Optional[str] = None,
        tier: Optional[str] = None,
        verify_signatures: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Export audit logs for date range / filters
        
        Args:
            start_date: ISO 8601 date (e.g., "2026-02-01T00:00:00Z")
            end_date: ISO 8601 date
            event_id: Filter by specific event
            tier: Filter by tier (EDGE/LEAN/NO_PLAY)
            verify_signatures: Verify HMAC signatures (default: True)
        
        Returns:
            List of audit records matching filters
        """
        records = []
        
        try:
            log_path = cls._get_log_path()
            
            if not os.path.exists(log_path):
                logger.warning(f"No audit log found at {log_path}")
                return []
            
            with open(log_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        record = json.loads(line)
                        
                        # Verify signature if requested
                        if verify_signatures:
                            signature = record.pop("signature")
                            payload = json.dumps(record, sort_keys=True)
                            
                            if not cls._verify_signature(payload, signature):
                                logger.warning(f"⚠️ Invalid signature for record: {record.get('event_id')}")
                                continue
                            
                            # Add signature back
                            record["signature"] = signature
                        
                        # Apply filters
                        if start_date and record["timestamp"] < start_date:
                            continue
                        if end_date and record["timestamp"] > end_date:
                            continue
                        if event_id and record["event_id"] != event_id:
                            continue
                        if tier and record["tier"] != tier:
                            continue
                        
                        records.append(record)
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in audit log: {e}")
                        continue
            
            logger.info(f"📊 Exported {len(records)} audit records")
            return records
            
        except Exception as e:
            logger.error(f"❌ Failed to export audit logs: {e}")
            return []
    
    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        Get audit log statistics
        
        Returns:
            {
                "total_records": int,
                "file_size_mb": float,
                "oldest_record": str,
                "newest_record": str,
                "tier_breakdown": {
                    "EDGE": int,
                    "LEAN": int,
                    "NO_PLAY": int
                }
            }
        """
        try:
            log_path = cls._get_log_path()
            
            if not os.path.exists(log_path):
                return {
                    "total_records": 0,
                    "file_size_mb": 0,
                    "error": "No audit log found"
                }
            
            # Get file size
            file_size_mb = os.path.getsize(log_path) / (1024 * 1024)
            
            # Count records and get timestamps
            total_records = 0
            oldest_record = None
            newest_record = None
            tier_breakdown = {"EDGE": 0, "LEAN": 0, "NO_PLAY": 0, "MARKET_ALIGNED": 0, "BLOCKED": 0}
            
            with open(log_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        record = json.loads(line)
                        total_records += 1
                        
                        timestamp = record.get("timestamp")
                        if not oldest_record or timestamp < oldest_record:
                            oldest_record = timestamp
                        if not newest_record or timestamp > newest_record:
                            newest_record = timestamp
                        
                        tier = record.get("tier")
                        if tier in tier_breakdown:
                            tier_breakdown[tier] += 1
                        
                    except json.JSONDecodeError:
                        continue
            
            return {
                "total_records": total_records,
                "file_size_mb": round(file_size_mb, 2),
                "oldest_record": oldest_record,
                "newest_record": newest_record,
                "tier_breakdown": tier_breakdown
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get audit log statistics: {e}")
            return {"error": str(e)}


# ============================================================================
# FASTAPI INTEGRATION
# ============================================================================

"""
Example FastAPI routes for audit log access:

from fastapi import APIRouter, HTTPException
from backend.utils.audit_logger import AuditLogger

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/export")
async def export_audit_logs(
    start_date: str = None,
    end_date: str = None,
    event_id: str = None,
    tier: str = None
):
    '''
    Export audit logs for investor/regulator review
    
    Query params:
    - start_date: ISO 8601 (e.g., "2026-02-01T00:00:00Z")
    - end_date: ISO 8601
    - event_id: Filter by specific event
    - tier: Filter by tier (EDGE/LEAN/NO_PLAY)
    '''
    records = AuditLogger.export_logs(
        start_date=start_date,
        end_date=end_date,
        event_id=event_id,
        tier=tier
    )
    
    return {
        "total_records": len(records),
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "event_id": event_id,
            "tier": tier
        },
        "records": records
    }

@router.get("/stats")
async def get_audit_stats():
    '''Get audit log statistics'''
    return AuditLogger.get_statistics()
"""


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

"""
# In simulation routes (after canonical contract enforcement):

from backend.utils.audit_logger import AuditLogger

@app.get("/api/simulations/{event_id}")
async def get_simulation(event_id: str):
    simulation = await run_simulation(event_id)
    
    # Enforce canonical contract
    simulation = enforce_canonical_contract(simulation)
    
    # Log to immutable audit trail
    AuditLogger.log_simulation(simulation)
    
    return simulation
"""
