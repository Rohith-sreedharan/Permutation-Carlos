"""
Market Line Integrity Verifier - SMART VALIDATION WITH GRACEFUL DEGRADATION

Validates market data with two-tier approach:
1. STRUCTURAL ERRORS → Hard fail (422): missing outcomes, wrong teams, impossible numbers
2. STALENESS → Soft warning (200 with status): old timestamps, but simulation still runs

This allows simulations to proceed with stale data while flagging the issue to users.
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass
import logging

# Import configurable thresholds
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.integrity_config import (
    get_max_odds_age, 
    get_auto_refresh_trigger,
    should_auto_refresh,
    LINE_VALIDITY_RANGES
)

logger = logging.getLogger(__name__)


class IntegrityStatus(Enum):
    """Market integrity status levels"""
    OK = "ok"                           # All checks passed, fresh data
    STALE_LINE = "stale_line"          # Odds timestamp old but usable
    PARTIAL_MARKETS = "partial_markets" # Some markets missing but can simulate
    STRUCTURAL_ERROR = "structural_error" # Critical validation failure


class StalenessReason(Enum):
    """Reasons for stale odds"""
    EVENT_START_PASSED = "event_start_passed"
    NO_RECENT_ODDS = "no_recent_odds"
    BOOKMAKER_INACTIVE = "bookmaker_inactive"
    MARKET_SUSPENDED = "market_suspended"


@dataclass
class IntegrityResult:
    """Result of market integrity validation"""
    status: IntegrityStatus
    is_valid: bool  # Can simulation proceed?
    errors: List[str]  # Structural errors (block simulation)
    warnings: List[str]  # Staleness warnings (allow simulation)
    odds_age_hours: Optional[float] = None
    staleness_reason: Optional[StalenessReason] = None
    last_updated_at: Optional[str] = None
    should_refresh: bool = False  # Should attempt auto-refresh?
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict"""
        return {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "odds_age_hours": self.odds_age_hours,
            "staleness_reason": self.staleness_reason.value if self.staleness_reason else None,
            "last_updated_at": self.last_updated_at,
            "should_refresh": self.should_refresh
        }


class MarketLineIntegrityError(Exception):
    """Raised ONLY for structural validation failures (not staleness)"""
    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.errors = errors


class MarketLineIntegrityVerifier:
    """
    Validates market line integrity with two-tier approach:
    - Structural errors (missing data, invalid formats) → HARD BLOCK
    - Staleness (old timestamps) → SOFT WARNING with simulation allowed
    """
    
    @staticmethod
    def verify_market_context(
        event_id: str,
        sport_key: str,
        market_context: Dict[str, Any],
        market_type: str = "full_game",
        event_start_time: Optional[datetime] = None
    ) -> IntegrityResult:
        """
        Verify market context integrity with graceful degradation
        
        Args:
            event_id: Game identifier
            sport_key: Sport key (americanfootball_nfl, etc.)
            market_context: Market data dict
            market_type: "full_game", "first_half", "second_half", "prop"
            event_start_time: Game start time (optional, for better staleness detection)
        
        Returns:
            IntegrityResult with status, errors, and warnings
        
        Raises:
            MarketLineIntegrityError: ONLY for critical structural failures
        """
        structural_errors = []
        staleness_warnings = []
        odds_age_hours = None
        staleness_reason = None
        last_updated_at = None
        should_refresh = False
        
        # ===== STRUCTURAL VALIDATIONS (HARD BLOCKS) =====
        
        # Check 1: Total line exists and is non-zero
        total_line = market_context.get("total_line")
        if total_line is None:
            structural_errors.append("MISSING_TOTAL_LINE: No total_line in market_context")
        elif total_line == 0:
            structural_errors.append("ZERO_TOTAL_LINE: Total line is zero")
        elif not isinstance(total_line, (int, float)):
            structural_errors.append(f"INVALID_TOTAL_LINE_TYPE: Expected number, got {type(total_line)}")
        
        # Check 2: Line is within sport-specific validity range (structural sanity check)
        if total_line and isinstance(total_line, (int, float)):
            validity_range = LINE_VALIDITY_RANGES.get(sport_key)
            if validity_range:
                if total_line < validity_range["min"]:
                    structural_errors.append(
                        f"LINE_TOO_LOW: {total_line} < {validity_range['min']} for {sport_key}"
                    )
                elif total_line > validity_range["max"]:
                    structural_errors.append(
                        f"LINE_TOO_HIGH: {total_line} > {validity_range['max']} for {sport_key}"
                    )
        
        # Check 3: Bookmaker source exists
        bookmaker_source = market_context.get("bookmaker_source")
        if not bookmaker_source or bookmaker_source == "":
            structural_errors.append("MISSING_BOOKMAKER_SOURCE: No bookmaker attribution")
        
        # Check 4: Market type matches (prevent 1H line used as full game)
        market_type_field = market_context.get("market_type", "full_game")
        if market_type_field != market_type:
            structural_errors.append(
                f"MARKET_TYPE_MISMATCH: Expected {market_type}, got {market_type_field}"
            )
        
        # Check 5: Game ID consistency (if provided)
        if "event_id" in market_context and market_context["event_id"] != event_id:
            structural_errors.append(
                f"EVENT_ID_MISMATCH: market_context.event_id={market_context['event_id']} != {event_id}"
            )
        
        # ===== STALENESS CHECKS (SOFT WARNINGS) =====
        
        # Check 6: Odds timestamp staleness (no longer a hard block)
        odds_timestamp = market_context.get("odds_timestamp")
        if not odds_timestamp:
            staleness_warnings.append("MISSING_ODDS_TIMESTAMP: No timestamp for market line")
        else:
            try:
                # Parse timestamp
                if isinstance(odds_timestamp, str):
                    odds_time = datetime.fromisoformat(odds_timestamp.replace('Z', '+00:00'))
                elif isinstance(odds_timestamp, datetime):
                    odds_time = odds_timestamp
                else:
                    raise ValueError(f"Invalid timestamp type: {type(odds_timestamp)}")
                
                last_updated_at = odds_timestamp if isinstance(odds_timestamp, str) else odds_timestamp.isoformat()
                
                # Calculate age
                now = datetime.now(timezone.utc)
                age = now - odds_time
                odds_age_hours = age.total_seconds() / 3600
                
                # Check against sport-specific threshold
                max_age = get_max_odds_age(sport_key)
                
                if age > max_age:
                    # Determine why odds are stale
                    if event_start_time and now > event_start_time:
                        staleness_reason = StalenessReason.EVENT_START_PASSED
                        staleness_warnings.append(
                            f"STALE_LINE_EVENT_PASSED: Odds {odds_age_hours:.1f}h old, event started at {event_start_time}"
                        )
                    else:
                        staleness_reason = StalenessReason.NO_RECENT_ODDS
                        staleness_warnings.append(
                            f"STALE_LINE: Odds timestamp {odds_timestamp} is {odds_age_hours:.1f} hours old (max: {max_age.total_seconds()/3600:.1f}h for {sport_key})"
                        )
                    
                    # Check if we should attempt auto-refresh
                    should_refresh = should_auto_refresh(sport_key, age)
                    
            except Exception as e:
                # Timestamp parsing error is structural
                structural_errors.append(f"INVALID_ODDS_TIMESTAMP: Failed to parse timestamp - {str(e)}")
        
        # Check 7: Spread exists (optional warning, not blocking)
        if "current_spread" not in market_context:
            staleness_warnings.append("MISSING_SPREAD: No spread in market_context")
        
        # ===== DETERMINE FINAL STATUS =====
        
        # HARD BLOCK if structural errors found
        if structural_errors:
            error_msg = f"❌ STRUCTURAL MARKET FAILURE ({event_id}):\n" + "\n".join(f"  • {e}" for e in structural_errors)
            logger.error(error_msg)
            raise MarketLineIntegrityError(error_msg, structural_errors)
        
        # Determine status based on warnings
        if staleness_warnings:
            status = IntegrityStatus.STALE_LINE
            logger.warning(
                f"⚠️  Stale odds detected for {event_id} ({sport_key}): "
                f"{odds_age_hours:.1f}h old, but allowing simulation. "
                f"Reason: {staleness_reason.value if staleness_reason else 'unknown'}"
            )
        else:
            status = IntegrityStatus.OK
            logger.info(f"✅ Market line integrity verified: {event_id} ({sport_key}, {market_type})")
        
        return IntegrityResult(
            status=status,
            is_valid=True,  # Simulation can proceed even with stale data
            errors=[],
            warnings=staleness_warnings,
            odds_age_hours=odds_age_hours,
            staleness_reason=staleness_reason,
            last_updated_at=last_updated_at,
            should_refresh=should_refresh
        )
    
    @staticmethod
    def verify_prop_market(
        prop_data: Dict[str, Any],
        require_market_line: bool = True
    ) -> IntegrityResult:
        """
        Verify prop market integrity
        
        Args:
            prop_data: Prop data dict
            require_market_line: If True, require actual bookmaker line (blocks pure projections)
        
        Returns:
            IntegrityResult
        """
        structural_errors = []
        warnings = []
        
        # Check player name
        if not prop_data.get("player_name"):
            structural_errors.append("MISSING_PLAYER_NAME")
        
        # Check prop type
        if not prop_data.get("prop_type"):
            structural_errors.append("MISSING_PROP_TYPE")
        
        # Check line value
        line_value = prop_data.get("line")
        if line_value is None:
            structural_errors.append("MISSING_LINE_VALUE")
        elif not isinstance(line_value, (int, float)):
            structural_errors.append(f"INVALID_LINE_TYPE: {type(line_value)}")
        
        # Check bookmaker data (CRITICAL for no-market = no-pick)
        books = prop_data.get("books", [])
        if require_market_line and len(books) == 0:
            structural_errors.append("NO_BOOKMAKER_DATA: Pure projection without market line")
        
        if structural_errors:
            error_msg = "Prop market integrity failure: " + ", ".join(structural_errors)
            if require_market_line:
                raise MarketLineIntegrityError(error_msg, structural_errors)
            else:
                logger.warning(f"⚠️  {error_msg}")
                return IntegrityResult(
                    status=IntegrityStatus.PARTIAL_MARKETS,
                    is_valid=False,
                    errors=structural_errors,
                    warnings=warnings
                )
        
        return IntegrityResult(
            status=IntegrityStatus.OK,
            is_valid=True,
            errors=[],
            warnings=warnings
        )
    
    @staticmethod
    def get_market_quality_score(market_context: Dict[str, Any], sport_key: str = "default") -> float:
        """
        Calculate market quality score (0.0 to 1.0)
        
        Higher score = more reliable market data
        Uses configurable thresholds per sport
        """
        score = 1.0
        
        # Penalize missing spread
        if "current_spread" not in market_context:
            score -= 0.1
        
        # Penalize stale odds based on sport-specific thresholds
        odds_timestamp = market_context.get("odds_timestamp")
        if odds_timestamp:
            try:
                if isinstance(odds_timestamp, str):
                    odds_time = datetime.fromisoformat(odds_timestamp.replace('Z', '+00:00'))
                else:
                    odds_time = odds_timestamp
                
                now = datetime.now(timezone.utc)
                age = now - odds_time
                age_hours = age.total_seconds() / 3600
                
                # Get sport-specific thresholds
                max_age = get_max_odds_age(sport_key)
                max_age_hours = max_age.total_seconds() / 3600
                
                # Progressive penalty based on age relative to threshold
                if age_hours > max_age_hours:
                    # Beyond threshold - significant penalty
                    score -= 0.3
                elif age_hours > max_age_hours * 0.75:
                    # 75% of threshold - moderate penalty
                    score -= 0.2
                elif age_hours > max_age_hours * 0.5:
                    # 50% of threshold - small penalty
                    score -= 0.1
            except:
                score -= 0.15
        
        # Penalize weak bookmaker source
        bookmaker = market_context.get("bookmaker_source", "").lower()
        if bookmaker in ["consensus", "average", "unknown"]:
            score -= 0.05
        
        # Penalize if market type not specified
        if "market_type" not in market_context:
            score -= 0.1
        
        return max(0.0, score)
    
    @staticmethod
    def enforce_no_market_no_pick(
        market_context: Dict[str, Any],
        market_type: str = "full_game"
    ) -> None:
        """
        Enforce NO MARKET = NO PICK rule
        
        For markets without bookmaker lines:
        - Projection allowed
        - Publishing FORBIDDEN
        - Parlay inclusion FORBIDDEN
        
        Raises:
            MarketLineIntegrityError if market line missing for publication
        """
        # Check if this is a derivative market (1H, alt total, prop)
        is_derivative = market_type in ["first_half", "second_half", "alt_total", "prop"]
        
        structural_errors = []
        
        if is_derivative:
            # Derivative markets MUST have explicit bookmaker line
            if not market_context.get("total_line"):
                structural_errors.append(
                    f"NO MARKET = NO PICK: {market_type} requires explicit bookmaker line"
                )
            
            # Check if this is a pure projection (no bookmaker data)
            bookmaker_source = market_context.get("bookmaker_source", "").lower()
            if bookmaker_source in ["model", "projection", "calculated", ""]:
                structural_errors.append(
                    f"NO MARKET = NO PICK: Cannot publish {market_type} without bookmaker line"
                )
        
        if structural_errors:
            error_msg = "\n".join(structural_errors)
            raise MarketLineIntegrityError(error_msg, structural_errors)
        
        logger.info(f"✅ Market publication check passed: {market_type}")
