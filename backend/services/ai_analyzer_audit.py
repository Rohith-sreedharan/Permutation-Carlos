"""
AI Analyzer - Audit Logger
Comprehensive audit logging for all analyzer operations.
"""

import uuid
from datetime import datetime
from typing import Optional
from pymongo.database import Database

from .ai_analyzer_schemas import MarketState, AnalyzerAudit


class AnalyzerAuditLogger:
    """
    Audit logger for AI Analyzer operations.
    
    Logs all analyzer calls to database for:
    - Compliance tracking
    - Performance monitoring
    - Abuse detection
    - Output quality analysis
    """
    
    def __init__(self, db: Database):
        """
        Initialize audit logger.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db.analyzer_audit
        
        # Ensure indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create necessary database indexes"""
        try:
            # Index on game_id for quick lookups
            self.collection.create_index("game_id")
            
            # Index on timestamp for time-based queries
            self.collection.create_index("timestamp")
            
            # Index on user_id for rate limiting
            self.collection.create_index("user_id")
            
            # Compound index for user + timestamp (rate limiting)
            self.collection.create_index([("user_id", 1), ("timestamp", -1)])
            
            # Index on blocked flag for monitoring
            self.collection.create_index("blocked")
            
            # Index on fallback_triggered for quality monitoring
            self.collection.create_index("fallback_triggered")
        except Exception as e:
            # Log warning but don't crash - app can run without indexes (slower queries)
            import logging
            logging.warning(f"⚠️  AIAnalyzerAudit index creation failed: {e}")
            logging.warning("   Audit logger will continue without indexes (may have performance impact)")
    
    def log(
        self,
        game_id: str,
        sport: str,
        state: MarketState,
        input_hash: str,
        output_hash: str,
        llm_model: str,
        response_time_ms: int,
        tokens_used: Optional[int] = None,
        user_id: Optional[str] = None,
        blocked: bool = False,
        block_reason: Optional[str] = None,
        fallback_triggered: bool = False
    ) -> str:
        """
        Log an analyzer operation.
        
        Args:
            game_id: Game identifier
            sport: Sport name
            state: Market state
            input_hash: Hash of input
            output_hash: Hash of output
            llm_model: LLM model identifier
            response_time_ms: Response time in milliseconds
            tokens_used: Tokens consumed (if available)
            user_id: User identifier (if available)
            blocked: Whether request was blocked
            block_reason: Reason for blocking (if blocked)
            fallback_triggered: Whether fallback was used
        
        Returns:
            Audit ID
        """
        audit_id = str(uuid.uuid4())
        
        audit_entry = AnalyzerAudit(
            audit_id=audit_id,
            timestamp=datetime.utcnow().isoformat(),
            game_id=game_id,
            sport=sport,
            state=state,
            input_hash=input_hash,
            output_hash=output_hash,
            llm_model=llm_model,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            user_id=user_id,
            blocked=blocked,
            block_reason=block_reason,
            fallback_triggered=fallback_triggered,
            cached=False  # Set by service if cached
        )
        
        # Insert to database
        self.collection.insert_one(audit_entry.dict())
        
        return audit_id
    
    def get_audit_entry(self, audit_id: str) -> Optional[dict]:
        """
        Retrieve audit entry by ID.
        
        Args:
            audit_id: Audit identifier
        
        Returns:
            Audit entry dict or None
        """
        return self.collection.find_one({"audit_id": audit_id})
    
    def get_game_audit_history(self, game_id: str, limit: int = 10) -> list:
        """
        Get audit history for a specific game.
        
        Args:
            game_id: Game identifier
            limit: Max number of entries
        
        Returns:
            List of audit entries
        """
        return list(
            self.collection.find({"game_id": game_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
    
    def get_user_audit_history(self, user_id: str, limit: int = 20) -> list:
        """
        Get audit history for a specific user.
        
        Args:
            user_id: User identifier
            limit: Max number of entries
        
        Returns:
            List of audit entries
        """
        return list(
            self.collection.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
    
    def get_blocked_requests(self, hours: int = 24) -> list:
        """
        Get blocked requests in the last N hours.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            List of blocked audit entries
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        return list(
            self.collection.find({
                "blocked": True,
                "timestamp": {"$gte": cutoff.isoformat()}
            })
            .sort("timestamp", -1)
        )
    
    def get_fallback_rate(self, hours: int = 24) -> float:
        """
        Calculate fallback rate in the last N hours.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            Fallback rate (0.0 to 1.0)
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        total_count = self.collection.count_documents({
            "timestamp": {"$gte": cutoff.isoformat()}
        })
        
        if total_count == 0:
            return 0.0
        
        fallback_count = self.collection.count_documents({
            "timestamp": {"$gte": cutoff.isoformat()},
            "fallback_triggered": True
        })
        
        return fallback_count / total_count
    
    def get_average_response_time(self, hours: int = 24) -> float:
        """
        Calculate average response time in the last N hours.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            Average response time in milliseconds
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff.isoformat()}}},
            {"$group": {
                "_id": None,
                "avg_response_time": {"$avg": "$response_time_ms"}
            }}
        ]
        
        result = list(self.collection.aggregate(pipeline))
        
        if result:
            return result[0]["avg_response_time"]
        
        return 0.0
    
    def get_total_tokens_used(self, hours: int = 24) -> int:
        """
        Calculate total tokens used in the last N hours.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            Total tokens consumed
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        pipeline = [
            {"$match": {
                "timestamp": {"$gte": cutoff.isoformat()},
                "tokens_used": {"$ne": None}
            }},
            {"$group": {
                "_id": None,
                "total_tokens": {"$sum": "$tokens_used"}
            }}
        ]
        
        result = list(self.collection.aggregate(pipeline))
        
        if result:
            return result[0]["total_tokens"]
        
        return 0
    
    def get_stats_summary(self, hours: int = 24) -> dict:
        """
        Get comprehensive stats summary.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            Dict with various statistics
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        total_requests = self.collection.count_documents({
            "timestamp": {"$gte": cutoff.isoformat()}
        })
        
        blocked_requests = self.collection.count_documents({
            "timestamp": {"$gte": cutoff.isoformat()},
            "blocked": True
        })
        
        fallback_requests = self.collection.count_documents({
            "timestamp": {"$gte": cutoff.isoformat()},
            "fallback_triggered": True
        })
        
        return {
            "total_requests": total_requests,
            "blocked_requests": blocked_requests,
            "fallback_requests": fallback_requests,
            "success_requests": total_requests - blocked_requests - fallback_requests,
            "blocked_rate": blocked_requests / total_requests if total_requests > 0 else 0.0,
            "fallback_rate": fallback_requests / total_requests if total_requests > 0 else 0.0,
            "success_rate": (total_requests - blocked_requests - fallback_requests) / total_requests if total_requests > 0 else 0.0,
            "avg_response_time_ms": self.get_average_response_time(hours),
            "total_tokens_used": self.get_total_tokens_used(hours),
            "period_hours": hours
        }
