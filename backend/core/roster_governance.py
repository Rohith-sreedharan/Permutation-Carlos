"""
Roster Availability Governance System
======================================
Institutional-grade handling of missing roster data.

OFFICIAL PLATFORM DECISION:
Missing roster data is NOT an error - it's a deterministic BLOCKED state.

No guesses. No retries. No silent degradation.

Key Features:
- TTL-based cooldown to prevent retry loops
- Idempotent ops alerts (one per cooldown window)
- League-specific policies (NCAAB requires roster)
- Clean state transitions: PENDING → READY or BLOCKED
- Recovery: BLOCKED → READY when roster arrives
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import logging
from dataclasses import dataclass

from db.mongo import db
from core.simulation_context import SimulationStatus, BlockedReason

logger = logging.getLogger(__name__)


# Cooldown configuration
ROSTER_CHECK_COOLDOWN_MINUTES = 60  # Don't re-check for 1 hour
ROSTER_CHECK_COOLDOWN_COLLEGE = 240  # 4 hours for college (data slower to update)
OPS_ALERT_COOLDOWN_HOURS = 24  # Only alert ops once per day per team


class LeagueRosterPolicy(str, Enum):
    """League-specific roster requirements"""
    REQUIRED = "required"  # Must have roster (NCAAB, NCAAF)
    PREFERRED = "preferred"  # Nice to have but can proceed without
    OPTIONAL = "optional"  # Not needed for simulation


# League-specific policies
LEAGUE_ROSTER_POLICIES: Dict[str, LeagueRosterPolicy] = {
    "NBA": LeagueRosterPolicy.PREFERRED,
    "NFL": LeagueRosterPolicy.PREFERRED,
    "NHL": LeagueRosterPolicy.PREFERRED,
    "MLB": LeagueRosterPolicy.PREFERRED,
    "NCAAB": LeagueRosterPolicy.REQUIRED,  # College basketball REQUIRES roster
    "NCAAF": LeagueRosterPolicy.REQUIRED,  # College football REQUIRES roster
}


@dataclass
class RosterCheckResult:
    """Result of roster availability check"""
    available: bool
    blocked: bool  # True if should enter BLOCKED state
    reason: Optional[str] = None
    retry_after: Optional[datetime] = None
    cooldown_active: bool = False
    team_name: Optional[str] = None


class RosterGovernance:
    """
    Manages roster availability checks with cooldown and idempotency.
    
    Ensures:
    1. No retry loops for missing roster
    2. One ops alert per cooldown window
    3. Clean BLOCKED state transitions
    4. Recovery when roster data arrives
    """
    
    def __init__(self):
        self.roster_checks_collection = db.roster_availability_checks
        self.blocked_simulations_collection = db.blocked_simulations
        
        # Create indexes for performance
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for fast lookups"""
        try:
            # Index for checking cooldown
            self.roster_checks_collection.create_index([
                ("team_name", 1),
                ("league", 1),
                ("checked_at", -1)
            ])
            
            # Index for blocked simulations
            self.blocked_simulations_collection.create_index([
                ("event_id", 1),
                ("status", 1)
            ])
            
            # TTL index to auto-expire old checks
            self.roster_checks_collection.create_index(
                "checked_at",
                expireAfterSeconds=7 * 24 * 60 * 60  # Keep for 7 days
            )
        except Exception as e:
            logger.warning(f"Failed to create roster governance indexes: {e}")
    
    def check_roster_availability(
        self,
        team_name: str,
        league: str,
        event_id: str
    ) -> RosterCheckResult:
        """
        Check if roster data is available for a team.
        
        Implements cooldown to prevent retry loops.
        Returns BLOCKED state if roster missing and required.
        
        Args:
            team_name: Team name to check
            league: League identifier (NBA, NCAAB, etc.)
            event_id: Associated event ID
            
        Returns:
            RosterCheckResult with availability and blocking decision
        """
        now = datetime.now(timezone.utc)
        
        # Get league policy
        policy = LEAGUE_ROSTER_POLICIES.get(league, LeagueRosterPolicy.PREFERRED)
        
        # Check if we're in cooldown period
        cooldown_result = self._check_cooldown(team_name, league, now)
        if cooldown_result.cooldown_active:
            logger.info(
                f"Roster check for {team_name} ({league}) in cooldown. "
                f"Retry after {cooldown_result.retry_after}"
            )
            return cooldown_result
        
        # Actually check roster availability
        roster_available = self._query_roster_data(team_name, league)
        
        # Record this check
        self._record_roster_check(team_name, league, roster_available, now)
        
        if roster_available:
            # Roster found - clear any blocked state
            self._clear_blocked_state(event_id)
            return RosterCheckResult(
                available=True,
                blocked=False,
                team_name=team_name
            )
        
        # Roster not available - determine if should block
        should_block = (policy == LeagueRosterPolicy.REQUIRED)
        
        if should_block:
            # Calculate retry time based on league
            cooldown_minutes = (
                ROSTER_CHECK_COOLDOWN_COLLEGE
                if league in ["NCAAB", "NCAAF"]
                else ROSTER_CHECK_COOLDOWN_MINUTES
            )
            retry_after = now + timedelta(minutes=cooldown_minutes)
            
            # Record blocked state
            self._record_blocked_state(
                event_id=event_id,
                team_name=team_name,
                league=league,
                reason=BlockedReason.ROSTER_UNAVAILABLE,
                retry_after=retry_after
            )
            
            # Alert ops (idempotent)
            self._alert_ops_if_needed(team_name, league, now)
            
            logger.warning(
                f"BLOCKED: Roster unavailable for {team_name} ({league}). "
                f"Event {event_id} blocked until {retry_after}"
            )
            
            return RosterCheckResult(
                available=False,
                blocked=True,
                reason=f"No roster data available for {team_name}",
                retry_after=retry_after,
                team_name=team_name
            )
        else:
            # Not required - can proceed without roster
            logger.info(
                f"Roster unavailable for {team_name} ({league}) but not required. "
                f"Proceeding with simulation."
            )
            return RosterCheckResult(
                available=False,
                blocked=False,
                team_name=team_name
            )
    
    def _check_cooldown(
        self,
        team_name: str,
        league: str,
        now: datetime
    ) -> RosterCheckResult:
        """Check if team is in cooldown period from previous check"""
        
        # Get cooldown period for league
        cooldown_minutes = (
            ROSTER_CHECK_COOLDOWN_COLLEGE
            if league in ["NCAAB", "NCAAF"]
            else ROSTER_CHECK_COOLDOWN_MINUTES
        )
        cooldown_threshold = now - timedelta(minutes=cooldown_minutes)
        
        # Find most recent check
        recent_check = self.roster_checks_collection.find_one(
            {
                "team_name": team_name,
                "league": league,
                "checked_at": {"$gt": cooldown_threshold}
            },
            sort=[("checked_at", -1)]
        )
        
        if recent_check:
            # In cooldown - return last known state
            retry_after = recent_check["checked_at"] + timedelta(minutes=cooldown_minutes)
            
            return RosterCheckResult(
                available=recent_check.get("roster_available", False),
                blocked=recent_check.get("blocked", False),
                reason=f"Cooldown active until {retry_after.isoformat()}",
                retry_after=retry_after,
                cooldown_active=True,
                team_name=team_name
            )
        
        # No recent check - proceed with fresh check
        return RosterCheckResult(
            available=False,
            blocked=False,
            cooldown_active=False
        )
    
    def _query_roster_data(self, team_name: str, league: str) -> bool:
        """
        Query roster collection to check if data exists.
        
        Args:
            team_name: Team to check
            league: League identifier
            
        Returns:
            True if roster data exists, False otherwise
        """
        try:
            roster_count = db.rosters.count_documents({
                "team": team_name,
                "league": league
            })
            return roster_count > 0
        except Exception as e:
            logger.error(f"Error querying roster data for {team_name}: {e}")
            return False
    
    def _record_roster_check(
        self,
        team_name: str,
        league: str,
        roster_available: bool,
        checked_at: datetime
    ):
        """Record roster check for cooldown tracking"""
        try:
            self.roster_checks_collection.insert_one({
                "team_name": team_name,
                "league": league,
                "roster_available": roster_available,
                "checked_at": checked_at,
                "blocked": not roster_available
            })
        except Exception as e:
            logger.error(f"Failed to record roster check: {e}")
    
    def _record_blocked_state(
        self,
        event_id: str,
        team_name: str,
        league: str,
        reason: BlockedReason,
        retry_after: datetime
    ):
        """Record blocked simulation state in database"""
        try:
            self.blocked_simulations_collection.update_one(
                {"event_id": event_id},
                {
                    "$set": {
                        "event_id": event_id,
                        "team_name": team_name,
                        "league": league,
                        "status": SimulationStatus.BLOCKED,
                        "blocked_reason": reason.value,
                        "blocked_at": datetime.now(timezone.utc),
                        "retry_after": retry_after,
                        "ops_alerted": False
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to record blocked state: {e}")
    
    def _clear_blocked_state(self, event_id: str):
        """Clear blocked state when roster becomes available"""
        try:
            self.blocked_simulations_collection.update_one(
                {"event_id": event_id},
                {
                    "$set": {
                        "status": SimulationStatus.READY,
                        "unblocked_at": datetime.now(timezone.utc)
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to clear blocked state: {e}")
    
    def _alert_ops_if_needed(self, team_name: str, league: str, now: datetime):
        """
        Send ops alert for missing roster (idempotent).
        Only alerts once per OPS_ALERT_COOLDOWN_HOURS.
        """
        alert_threshold = now - timedelta(hours=OPS_ALERT_COOLDOWN_HOURS)
        
        # Check if we've already alerted recently
        recent_alert = self.roster_checks_collection.find_one({
            "team_name": team_name,
            "league": league,
            "ops_alerted": True,
            "checked_at": {"$gt": alert_threshold}
        })
        
        if recent_alert:
            logger.debug(
                f"Ops already alerted for {team_name} ({league}) within cooldown. "
                "Skipping duplicate alert."
            )
            return
        
        # Send alert (would integrate with ops monitoring system)
        logger.warning(
            f"OPS ALERT: Missing roster data for {team_name} ({league}). "
            f"Blocking simulations until data available."
        )
        
        # Mark this check as having triggered an alert
        try:
            self.roster_checks_collection.update_one(
                {
                    "team_name": team_name,
                    "league": league,
                    "checked_at": {"$gte": alert_threshold}
                },
                {"$set": {"ops_alerted": True}},
                upsert=False
            )
        except Exception as e:
            logger.error(f"Failed to mark ops alert: {e}")
    
    def get_blocked_status(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get blocked status for an event if it exists.
        
        Returns:
            Blocked status dict or None if not blocked
        """
        return self.blocked_simulations_collection.find_one(
            {"event_id": event_id, "status": SimulationStatus.BLOCKED}
        )
    
    def get_roster_metrics(self, league: Optional[str] = None) -> Dict[str, Any]:
        """
        Get roster availability metrics for monitoring/ops dashboard.
        
        Args:
            league: Optional league filter
            
        Returns:
            Metrics dict with availability stats
        """
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        
        query = {"checked_at": {"$gte": last_24h}}
        if league:
            query["league"] = league
        
        total_checks = self.roster_checks_collection.count_documents(query)
        available_checks = self.roster_checks_collection.count_documents({
            **query,
            "roster_available": True
        })
        blocked_checks = self.roster_checks_collection.count_documents({
            **query,
            "blocked": True
        })
        
        # Currently blocked simulations
        currently_blocked = self.blocked_simulations_collection.count_documents({
            "status": SimulationStatus.BLOCKED,
            "retry_after": {"$gt": now}
        })
        
        return {
            "last_24h": {
                "total_checks": total_checks,
                "available": available_checks,
                "unavailable": total_checks - available_checks,
                "blocked": blocked_checks,
                "availability_rate": (
                    (available_checks / total_checks * 100)
                    if total_checks > 0 else 100.0
                )
            },
            "currently_blocked": currently_blocked,
            "league": league or "all"
        }


# Singleton instance
roster_governance = RosterGovernance()
