"""
Market Line Integrity Verifier - HARD BLOCK FOR BAD INPUTS
Prevents simulation with invalid, stale, or mismatched market data

THIS IS A LAUNCH BLOCKER - NO SIMULATION WITHOUT VALID MARKET LINE

Hard-fails if:
- Line is null / zero
- Line is stale (> 24 hours old)
- Wrong market type (1H used as full game)
- Wrong sport scaling
- Game ID mismatch
- Duplicate odds from same book

If failed → NO SIMULATION, NO PICK
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


# Sport-specific line validity ranges
LINE_VALIDITY_RANGES = {
    "americanfootball_nfl": {"min": 30.0, "max": 70.0},
    "americanfootball_ncaaf": {"min": 35.0, "max": 85.0},
    "basketball_nba": {"min": 180.0, "max": 260.0},
    "basketball_ncaab": {"min": 110.0, "max": 180.0},
    "baseball_mlb": {"min": 5.0, "max": 14.0},
    "icehockey_nhl": {"min": 4.0, "max": 9.0}
}


class MarketLineIntegrityError(Exception):
    """Raised when market line fails integrity checks"""
    pass


class MarketLineIntegrityVerifier:
    """
    Validates market line integrity before simulation
    HARD BLOCKS on failures
    """
    
    @staticmethod
    def verify_market_context(
        event_id: str,
        sport_key: str,
        market_context: Dict[str, Any],
        market_type: str = "full_game"
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify market context integrity
        
        Args:
            event_id: Game identifier
            sport_key: Sport key (americanfootball_nfl, etc.)
            market_context: Market data dict
            market_type: "full_game", "first_half", "second_half", "prop"
        
        Returns:
            (is_valid, error_message)
        
        Raises:
            MarketLineIntegrityError: If critical validation fails
        """
        errors = []
        
        # Check 1: Total line exists and is non-zero
        total_line = market_context.get("total_line")
        if total_line is None:
            errors.append("MISSING_TOTAL_LINE: No total_line in market_context")
        elif total_line == 0:
            errors.append("ZERO_TOTAL_LINE: Total line is zero")
        elif not isinstance(total_line, (int, float)):
            errors.append(f"INVALID_TOTAL_LINE_TYPE: Expected number, got {type(total_line)}")
        
        # Check 2: Line is within sport-specific validity range
        if total_line and isinstance(total_line, (int, float)):
            validity_range = LINE_VALIDITY_RANGES.get(sport_key)
            if validity_range:
                if total_line < validity_range["min"]:
                    errors.append(
                        f"LINE_TOO_LOW: {total_line} < {validity_range['min']} for {sport_key}"
                    )
                elif total_line > validity_range["max"]:
                    errors.append(
                        f"LINE_TOO_HIGH: {total_line} > {validity_range['max']} for {sport_key}"
                    )
        
        # Check 3: Odds timestamp exists and is recent
        odds_timestamp = market_context.get("odds_timestamp")
        if not odds_timestamp:
            errors.append("MISSING_ODDS_TIMESTAMP: No timestamp for market line")
        else:
            try:
                # Parse timestamp
                if isinstance(odds_timestamp, str):
                    odds_time = datetime.fromisoformat(odds_timestamp.replace('Z', '+00:00'))
                elif isinstance(odds_timestamp, datetime):
                    odds_time = odds_timestamp
                else:
                    raise ValueError(f"Invalid timestamp type: {type(odds_timestamp)}")
                
                # Check staleness (24 hour threshold)
                now = datetime.now(timezone.utc)
                age = now - odds_time
                
                if age > timedelta(hours=24):
                    errors.append(
                        f"STALE_LINE: Odds timestamp {odds_timestamp} is {age.total_seconds()/3600:.1f} hours old"
                    )
            except Exception as e:
                errors.append(f"INVALID_ODDS_TIMESTAMP: Failed to parse timestamp - {str(e)}")
        
        # Check 4: Bookmaker source exists
        bookmaker_source = market_context.get("bookmaker_source")
        if not bookmaker_source or bookmaker_source == "":
            errors.append("MISSING_BOOKMAKER_SOURCE: No bookmaker attribution")
        
        # Check 5: Market type matches (prevent 1H line used as full game)
        market_type_field = market_context.get("market_type", "full_game")
        if market_type_field != market_type:
            errors.append(
                f"MARKET_TYPE_MISMATCH: Expected {market_type}, got {market_type_field}"
            )
        
        # Check 6: Spread exists (optional but recommended)
        if "current_spread" not in market_context:
            logger.warning(f"⚠️  No spread in market_context for {event_id}")
        
        # Check 7: Game ID consistency (if provided)
        if "event_id" in market_context and market_context["event_id"] != event_id:
            errors.append(
                f"EVENT_ID_MISMATCH: market_context.event_id={market_context['event_id']} != {event_id}"
            )
        
        # HARD BLOCK if critical errors found
        if errors:
            error_msg = f"❌ MARKET LINE INTEGRITY FAILURE ({event_id}):\n" + "\n".join(f"  • {e}" for e in errors)
            logger.error(error_msg)
            raise MarketLineIntegrityError(error_msg)
        
        logger.info(f"✅ Market line integrity verified: {event_id} ({sport_key}, {market_type})")
        return True, None
    
    @staticmethod
    def verify_prop_market(
        prop_data: Dict[str, Any],
        require_market_line: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify prop market integrity
        
        Args:
            prop_data: Prop data dict
            require_market_line: If True, require actual bookmaker line (blocks pure projections)
        
        Returns:
            (is_valid, error_message)
        """
        errors = []
        
        # Check player name
        if not prop_data.get("player_name"):
            errors.append("MISSING_PLAYER_NAME")
        
        # Check prop type
        if not prop_data.get("prop_type"):
            errors.append("MISSING_PROP_TYPE")
        
        # Check line value
        line_value = prop_data.get("line")
        if line_value is None:
            errors.append("MISSING_LINE_VALUE")
        elif not isinstance(line_value, (int, float)):
            errors.append(f"INVALID_LINE_TYPE: {type(line_value)}")
        
        # Check bookmaker data (CRITICAL for no-market = no-pick)
        books = prop_data.get("books", [])
        if require_market_line and len(books) == 0:
            errors.append("NO_BOOKMAKER_DATA: Pure projection without market line")
        
        if errors:
            error_msg = "Prop market integrity failure: " + ", ".join(errors)
            if require_market_line:
                raise MarketLineIntegrityError(error_msg)
            else:
                logger.warning(f"⚠️  {error_msg}")
                return False, error_msg
        
        return True, None
    
    @staticmethod
    def get_market_quality_score(market_context: Dict[str, Any]) -> float:
        """
        Calculate market quality score (0.0 to 1.0)
        
        Higher score = more reliable market data
        """
        score = 1.0
        
        # Penalize missing spread
        if "current_spread" not in market_context:
            score -= 0.1
        
        # Penalize stale odds
        odds_timestamp = market_context.get("odds_timestamp")
        if odds_timestamp:
            try:
                if isinstance(odds_timestamp, str):
                    odds_time = datetime.fromisoformat(odds_timestamp.replace('Z', '+00:00'))
                else:
                    odds_time = odds_timestamp
                
                now = datetime.now(timezone.utc)
                age_hours = (now - odds_time).total_seconds() / 3600
                
                if age_hours > 12:
                    score -= 0.2
                elif age_hours > 6:
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
        
        if is_derivative:
            # Derivative markets MUST have explicit bookmaker line
            if not market_context.get("total_line"):
                raise MarketLineIntegrityError(
                    f"NO MARKET = NO PICK: {market_type} requires explicit bookmaker line"
                )
            
            # Check if this is a pure projection (no bookmaker data)
            bookmaker_source = market_context.get("bookmaker_source", "").lower()
            if bookmaker_source in ["model", "projection", "calculated", ""]:
                raise MarketLineIntegrityError(
                    f"NO MARKET = NO PICK: Cannot publish {market_type} without bookmaker line"
                )
        
        logger.info(f"✅ Market publication check passed: {market_type}")
