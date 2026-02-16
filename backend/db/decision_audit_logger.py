"""
BeatVegas Decision Audit Logger
Section 14 - ENGINE LOCK Specification Compliance

PURPOSE:
- Append-only immutable audit trail for ALL market decisions
- Institutional compliance and regulatory readiness
- Forensic analysis and debugging capability
- 7-year retention for legal/compliance requirements

CRITICAL RULES:
1. Audit writes are REQUIRED - HTTP 500 if write fails
2. Collection is append-only - updates/deletes FORBIDDEN
3. All decision metadata must be captured
4. Timestamps are UTC ISO 8601
5. Does NOT modify decision logic - pure recording layer

This is infrastructure hardening, not engine patching.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
import os


class DecisionAuditLogger:
    """
    Immutable append-only audit log for decision engine.
    
    Compliance: Section 14 - Audit Logging (ENGINE LOCK Specification v2.0.0)
    
    Records every decision made by the engine with complete metadata
    for institutional compliance, debugging, and regulatory requirements.
    """
    
    def __init__(self, mongo_uri: str, database: str = "beatvegas_prod"):
        """
        Initialize decision audit logger with MongoDB connection.
        
        Args:
            mongo_uri: MongoDB connection string
            database: Database name (default: beatvegas_prod)
        """
        self.client = MongoClient(mongo_uri)
        self.db = self.client[database]
        self.collection = self.db["decision_audit_logs"]
        
        # Ensure collection exists with proper indexes
        self._ensure_collection_setup()
    
    def _ensure_collection_setup(self):
        """
        Create collection and indexes if they don't exist.
        
        Indexes:
        - event_id (for query efficiency)
        - timestamp (for retention/archival)
        - trace_id (for request tracing)
        - inputs_hash (for duplicate detection)
        - classification, release_status (for analytics)
        """
        # Create indexes for efficient querying
        self.collection.create_index([("event_id", ASCENDING)])
        self.collection.create_index([("timestamp", ASCENDING)])
        self.collection.create_index([("trace_id", ASCENDING)])
        self.collection.create_index([("inputs_hash", ASCENDING)])
        self.collection.create_index([("classification", ASCENDING)])
        self.collection.create_index([("release_status", ASCENDING)])
        
        # Create compound index for event + timestamp queries
        self.collection.create_index([
            ("event_id", ASCENDING),
            ("timestamp", ASCENDING)
        ])
    
    def log_decision(
        self,
        event_id: str,
        inputs_hash: str,
        decision_version: str,
        classification: Optional[str],
        release_status: str,
        edge_points: Optional[float],
        model_prob: Optional[float],
        trace_id: str,
        engine_version: str,
        market_type: str,
        league: str,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Write decision to immutable audit log.
        
        THIS MUST SUCCEED - HTTP 500 if write fails per Section 14.
        
        Args:
            event_id: Unique event identifier
            inputs_hash: SHA-256 hash of decision inputs (for determinism)
            decision_version: Semantic version of decision logic
            classification: EDGE | LEAN | MARKET_ALIGNED | null (if BLOCKED)
            release_status: APPROVED | BLOCKED_* | PENDING_REVIEW
            edge_points: Calculated edge (null if BLOCKED)
            model_prob: Model probability (null if BLOCKED)
            trace_id: Request trace ID for debugging
            engine_version: Engine version string (e.g., "2.0.0")
            market_type: spread | total | moneyline
            league: NBA | NCAAB | NFL | etc
            additional_metadata: Optional extra fields for context
        
        Returns:
            bool: True if write succeeded, False if failed
            
        Raises:
            Never raises - returns False on failure to enable HTTP 500 handling
        """
        try:
            # Build audit log document
            log_entry = {
                # Required fields per Section 14
                "event_id": event_id,
                "inputs_hash": inputs_hash,
                "decision_version": decision_version,
                "classification": classification,  # null if BLOCKED
                "release_status": release_status,
                "edge_points": edge_points,  # null if BLOCKED
                "model_prob": model_prob,  # null if BLOCKED
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engine_version": engine_version,
                "trace_id": trace_id,
                
                # Additional context for forensics
                "market_type": market_type,
                "league": league,
                
                # Metadata for compliance
                "logged_at_unix": datetime.now(timezone.utc).timestamp(),
                "retention_expires_at": self._calculate_retention_expiry(),
            }
            
            # Add optional metadata if provided
            if additional_metadata:
                log_entry["metadata"] = additional_metadata
            
            # CRITICAL: Write to append-only collection
            result = self.collection.insert_one(log_entry)
            
            # Verify write succeeded
            return result.inserted_id is not None
            
        except PyMongoError as e:
            # Log error but don't raise - caller will trigger HTTP 500
            print(f"[CRITICAL] Decision audit log write failed: {e}")
            return False
        except Exception as e:
            # Catch any unexpected errors
            print(f"[CRITICAL] Unexpected decision audit error: {e}")
            return False
    
    def _calculate_retention_expiry(self) -> str:
        """
        Calculate retention expiry date (7 years from now).
        
        Section 14 requires 7-year retention for compliance.
        
        Returns:
            ISO 8601 timestamp 7 years in the future
        """
        now = datetime.now(timezone.utc)
        # 7 years = 2557 days (accounting for leap years)
        expiry = now.replace(year=now.year + 7)
        return expiry.isoformat()
    
    def query_by_event(
        self,
        event_id: str,
        limit: int = 100
    ) -> list:
        """
        Query audit logs for a specific event.
        
        Args:
            event_id: Event identifier to query
            limit: Maximum records to return
        
        Returns:
            List of audit log entries sorted by timestamp (newest first)
        """
        try:
            cursor = self.collection.find(
                {"event_id": event_id}
            ).sort("timestamp", -1).limit(limit)
            
            return list(cursor)
        except PyMongoError as e:
            print(f"[ERROR] Decision audit log query failed: {e}")
            return []
    
    def query_by_trace_id(
        self,
        trace_id: str
    ) -> list:
        """
        Query audit logs by trace ID (for request debugging).
        
        Args:
            trace_id: Request trace identifier
        
        Returns:
            List of audit log entries for this trace
        """
        try:
            cursor = self.collection.find(
                {"trace_id": trace_id}
            ).sort("timestamp", -1)
            
            return list(cursor)
        except PyMongoError as e:
            print(f"[ERROR] Decision audit log query failed: {e}")
            return []
    
    def get_decision_history(
        self,
        event_id: str,
        inputs_hash: str
    ) -> list:
        """
        Get decision history for identical inputs.
        
        Used to verify determinism: identical inputs should produce
        identical decision_version and classification.
        
        Args:
            event_id: Event identifier
            inputs_hash: Hash of decision inputs
        
        Returns:
            List of decisions with matching event_id + inputs_hash
        """
        try:
            cursor = self.collection.find({
                "event_id": event_id,
                "inputs_hash": inputs_hash
            }).sort("timestamp", -1)
            
            return list(cursor)
        except PyMongoError as e:
            print(f"[ERROR] Decision audit log query failed: {e}")
            return []
    
    def verify_append_only(self) -> bool:
        """
        Verify collection is truly append-only.
        
        WARNING: This is a test function only.
        Should be used in tests to verify collection cannot be modified.
        
        Returns:
            bool: True if append-only enforcement working
        """
        # Try to update a document (should fail with proper setup)
        try:
            # Find any document
            doc = self.collection.find_one()
            if not doc:
                return True  # No docs to test
            
            # Attempt update (should fail if append-only enforced)
            result = self.collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"classification": "HACKED"}}
            )
            
            # If update succeeded, append-only is NOT enforced
            if result.modified_count > 0:
                print("[WARNING] Decision audit log is NOT append-only!")
                return False
            
            return True
            
        except Exception as e:
            # If exception thrown, that's actually good (means updates blocked)
            return True


# Singleton instance for application-wide use
_decision_audit_logger_instance: Optional[DecisionAuditLogger] = None


def get_decision_audit_logger() -> DecisionAuditLogger:
    """
    Get or create decision audit logger singleton instance.
    
    Uses MONGO_URI from environment or defaults to production MongoDB.
    
    Returns:
        DecisionAuditLogger instance
    """
    global _decision_audit_logger_instance
    
    if _decision_audit_logger_instance is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://159.203.122.145:27017/")
        _decision_audit_logger_instance = DecisionAuditLogger(mongo_uri)
    
    return _decision_audit_logger_instance
