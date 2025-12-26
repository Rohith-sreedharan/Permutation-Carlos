"""
BeatVegas Audit Logging Service — FINAL APPROVED SPECIFICATION

Version: Final | Retention: 7 Years | Audit Ready: Yes

Lightweight append-only logging to audit tables for regulatory compliance.
Designed to integrate with existing code paths without refactors.

Usage:
    from db.audit_logger import get_audit_logger
    
    audit_logger = get_audit_logger()
    
    # Log simulation
    audit_logger.log_simulation(game_id, sport, sim_count, vegas_line, model_total, stddev, rcl_passed, edge_flagged)
    
    # Log bet
    audit_logger.log_bet(user_id, game_id, odds, closing_odds, clv, profit, sport)
    
    # Log RCL check
    audit_logger.log_rcl(game_id, rcl_passed, rcl_reason, sport)

Compliance Requirements:
- Immutable audit logs (no destructive updates)
- 7-year retention with automatic expiration dates
- JSON logging compatibility
- Non-blocking error handling

Developer Handoff Document Approved: December 20, 2025
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import logging
from pymongo.database import Database

logger = logging.getLogger(__name__)

# 7-year retention period (in days)
RETENTION_PERIOD_DAYS = 7 * 365  # 2555 days


class AuditLogger:
    """
    BeatVegas Audit Logging Service
    
    Provides compliant logging methods for sim_audit, bet_history, rcl_log, and calibration_weekly.
    All records are immutable with 7-year retention expiration dates.
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.sim_audit = db['sim_audit']
        self.bet_history = db['bet_history']
        self.rcl_log = db['rcl_log']
        self.calibration_weekly = db['calibration_weekly']
    
    def _get_retention_date(self) -> datetime:
        """Calculate 7-year retention expiration date"""
        return datetime.now(timezone.utc) + timedelta(days=RETENTION_PERIOD_DAYS)
    
    # ========================================================================
    # TABLE 1: sim_audit
    # ========================================================================
    
    def log_simulation(
        self,
        game_id: str,
        sport: str,
        sim_count: int,
        vegas_line: float,
        model_total: float,
        stddev: float,
        rcl_passed: bool,
        edge_flagged: bool,
        actual_result: Optional[float] = None
    ) -> bool:
        """
        Log simulation to sim_audit collection
        
        Purpose: Stores every simulation batch for transparency, grading, and audits.
        Retention: 7 years
        
        Args:
            game_id: Unique game identifier
            sport: nba / nfl / ncaaf / ncaab / mlb / nhl
            sim_count: Number of simulations run (10K-100K)
            vegas_line: Sportsbook line at time of simulation
            model_total: Model projected median/mean total or spread
            stddev: Simulation distribution standard deviation
            rcl_passed: Whether Reality Check Logic passed
            edge_flagged: Whether mispricing was detected
            actual_result: Final game result for grading (optional, populated post-game)
        
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            now = datetime.now(timezone.utc)
            
            audit_record = {
                # Required fields (per specification)
                'game_id': game_id,
                'sport': sport,
                'sim_count': sim_count,
                'vegas_line': vegas_line,
                'model_total': model_total,
                'stddev': stddev,
                'rcl_passed': rcl_passed,
                'edge_flagged': edge_flagged,
                
                # Grading field (populated post-game)
                'actual_result': actual_result,
                
                # Compliance metadata
                'timestamp': now,
                'retention_date': self._get_retention_date(),
                'immutable': True  # Audit log immutability flag
            }
            
            # Insert (immutable append-only)
            self.sim_audit.insert_one(audit_record)
            logger.debug(f"✅ Logged simulation audit: {game_id} ({sport})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log simulation audit: {e}")
            return False
    
    def grade_simulation(
        self,
        game_id: str,
        actual_result: float
    ) -> bool:
        """
        Update sim_audit record with actual game result
        
        Note: This is the ONLY allowed update to sim_audit (one-time grading).
        All other fields remain immutable.
        
        Args:
            game_id: Game identifier
            actual_result: Final game result for grading
        
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            result = self.sim_audit.update_one(
                {'game_id': game_id, 'actual_result': None},
                {'$set': {'actual_result': actual_result}}
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ Graded simulation: {game_id} → {actual_result}")
                return True
            else:
                logger.warning(f"⚠️  No simulation found to grade for {game_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to grade simulation: {e}")
            return False
    
    # ========================================================================
    # TABLE 2: bet_history
    # ========================================================================
    
    def log_bet(
        self,
        user_id: str,
        game_id: str,
        odds: float,
        closing_odds: float,
        clv: float,
        profit: float,
        sport: Optional[str] = None
    ) -> bool:
        """
        Log bet to bet_history collection
        
        Purpose: Tracks user bets, CLV, and profitability.
        Retention: 7 years
        
        Args:
            user_id: Internal BeatVegas user identifier
            game_id: Linked game identifier
            odds: Odds at bet placement time (American odds)
            closing_odds: Closing sportsbook odds
            clv: Closing Line Value (closing_odds - odds)
            profit: Profit or loss from bet
            sport: Sport key (optional, for indexing)
        
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            now = datetime.now(timezone.utc)
            
            bet_record = {
                # Required fields (per specification)
                'user_id': user_id,
                'game_id': game_id,
                'odds': odds,
                'closing_odds': closing_odds,
                'clv': clv,
                'profit': profit,
                
                # Metadata
                'timestamp': now,
                'sport': sport,
                'retention_date': self._get_retention_date(),
                'immutable': True  # Audit log immutability flag
            }
            
            # Insert (immutable append-only)
            self.bet_history.insert_one(bet_record)
            logger.debug(f"✅ Logged bet: {user_id} → {game_id} (CLV: {clv:+.2f})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log bet: {e}")
            return False
    
    # ========================================================================
    # TABLE 3: rcl_log
    # ========================================================================
    
    def log_rcl(
        self,
        game_id: str,
        rcl_passed: bool,
        rcl_reason: str,
        sport: Optional[str] = None
    ) -> bool:
        """
        Log RCL evaluation to rcl_log collection
        
        Purpose: Logs every Reality Check Logic evaluation for transparency and debugging.
        Retention: 7 years
        
        Args:
            game_id: Game evaluated
            rcl_passed: Pass/fail status
            rcl_reason: Explanation for the evaluation result
            sport: Sport key (optional, for indexing)
        
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            now = datetime.now(timezone.utc)
            
            rcl_record = {
                # Required fields (per specification)
                'game_id': game_id,
                'rcl_passed': rcl_passed,
                'rcl_reason': rcl_reason,
                'timestamp': now,
                
                # Metadata
                'sport': sport,
                'retention_date': self._get_retention_date(),
                'immutable': True  # Audit log immutability flag
            }
            
            # Insert (immutable append-only)
            self.rcl_log.insert_one(rcl_record)
            logger.debug(f"✅ Logged RCL: {game_id} ({'PASS' if rcl_passed else 'FAIL'})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log RCL: {e}")
            return False
    
    # ========================================================================
    # TABLE 4: calibration_weekly
    # ========================================================================
    
    def log_calibration(
        self,
        sport: str,
        win_rate: float,
        brier_score: float,
        std_dev: float,
        n_games: int,
        week_start: Optional[datetime] = None,
        week_end: Optional[datetime] = None
    ) -> bool:
        """
        Log weekly calibration metrics to calibration_weekly collection
        
        Purpose: Stores weekly model calibration metrics.
        Retention: 7 years
        
        Args:
            sport: nba / nfl / ncaaf / ncaab / mlb / nhl
            win_rate: Weekly accuracy percent (0.0 - 1.0)
            brier_score: Calibration score (lower = better)
            std_dev: Distribution deviation
            n_games: Number of games in calibration sample
            week_start: Week start date (optional)
            week_end: Week end date (optional)
        
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            now = datetime.now(timezone.utc)
            
            calibration_record = {
                # Required fields (per specification)
                'sport': sport,
                'win_rate': win_rate,
                'brier_score': brier_score,
                'std_dev': std_dev,
                'n_games': n_games,
                
                # Metadata
                'week_start': week_start,
                'week_end': week_end,
                'timestamp': now,
                'retention_date': self._get_retention_date(),
                'immutable': True  # Audit log immutability flag
            }
            
            # Insert (immutable append-only)
            self.calibration_weekly.insert_one(calibration_record)
            logger.info(f"✅ Logged calibration: {sport} ({n_games} games, {win_rate:.1%} win rate)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to log calibration: {e}")
            return False
    
    # ========================================================================
    # RETENTION CLEANUP (7-year expiration)
    # ========================================================================
    
    def cleanup_expired_records(self) -> Dict[str, int]:
        """
        Delete records older than 7 years (based on retention_date)
        
        Should be run periodically (e.g., monthly cron job).
        
        Returns:
            Dict with count of deleted records per collection
        """
        try:
            now = datetime.now(timezone.utc)
            deleted_counts = {}
            
            for coll_name in ['sim_audit', 'bet_history', 'rcl_log', 'calibration_weekly']:
                collection = self.db[coll_name]
                result = collection.delete_many({
                    'retention_date': {'$lt': now}
                })
                deleted_counts[coll_name] = result.deleted_count
                
                if result.deleted_count > 0:
                    logger.info(f"🗑️  Deleted {result.deleted_count} expired records from {coll_name}")
            
            return deleted_counts
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup expired records: {e}")
            return {}


# ============================================================================
# SINGLETON (will be initialized in main.py after DB connection)
# ============================================================================

_audit_logger_instance = None


def get_audit_logger(db: Optional[Database] = None) -> AuditLogger:
    """
    Get or create audit logger singleton
    
    Args:
        db: Database instance (required on first call)
    
    Returns:
        AuditLogger instance
    """
    global _audit_logger_instance
    
    if _audit_logger_instance is None:
        if db is None:
            raise ValueError("Database instance required for first initialization")
        _audit_logger_instance = AuditLogger(db)
    
    return _audit_logger_instance
