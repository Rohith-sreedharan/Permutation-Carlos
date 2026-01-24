"""
SIM INTEGRITY LAYER
===================
Single source of truth for spread normalization, versioning, and validation.
This module prevents data mapping errors and ensures simulation consistency.

Created: January 24, 2026
Purpose: Stop spread direction bugs forever
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os

logger = logging.getLogger(__name__)

# CRITICAL: Increment this when cover logic or spread mapping changes
CURRENT_SIM_VERSION = 2
# Build ID should be git commit hash or deployment tag
ENGINE_BUILD_ID = os.getenv("ENGINE_BUILD_ID", "v2.0.0-integrity-layer")


@dataclass
class CanonicalOdds:
    """
    CANONICAL SPREAD FORMAT
    =======================
    Single source of truth: home_spread only (favorite negative, dog positive)
    All other fields are derived from this.
    
    Rules:
    - home_spread is ALWAYS relative to home team
    - Negative = home is favorite
    - Positive = home is underdog
    - away_spread = -home_spread (exact negatives)
    """
    home_team: str
    away_team: str
    home_spread: float  # ✅ CANONICAL - Only field stored
    
    # Derived fields (computed from home_spread)
    @property
    def away_spread(self) -> float:
        """Derived: Exact negative of home_spread"""
        return -self.home_spread
    
    @property
    def market_favorite_team(self) -> str:
        """Derived: Team with negative spread"""
        return self.home_team if self.home_spread < 0 else self.away_team
    
    @property
    def market_underdog_team(self) -> str:
        """Derived: Team with positive spread"""
        return self.away_team if self.home_spread < 0 else self.home_team
    
    @property
    def favorite_spread(self) -> float:
        """Derived: The negative spread value"""
        return min(self.home_spread, self.away_spread)
    
    @property
    def underdog_spread(self) -> float:
        """Derived: The positive spread value"""
        return max(self.home_spread, self.away_spread)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export canonical format with all derived fields"""
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_spread": self.home_spread,
            "away_spread": self.away_spread,
            "market_favorite_team": self.market_favorite_team,
            "market_underdog_team": self.market_underdog_team,
            "favorite_spread": self.favorite_spread,
            "underdog_spread": self.underdog_spread
        }


def normalize_spread_from_odds_api(
    home_team: str,
    away_team: str,
    home_spread_raw: Optional[float],
    away_spread_raw: Optional[float],
    tolerance: float = 0.01
) -> Optional[CanonicalOdds]:
    """
    SPREAD NORMALIZATION LAYER
    ==========================
    Converts OddsAPI response into canonical format.
    
    Hard fail conditions:
    1. If both spreads provided and NOT exact negatives (within tolerance)
    2. If neither spread provided
    
    Args:
        home_team: Home team name
        away_team: Away team name
        home_spread_raw: Raw home spread from API (may be None)
        away_spread_raw: Raw away spread from API (may be None)
        tolerance: Maximum allowed deviation from exact negatives (default 0.01)
    
    Returns:
        CanonicalOdds object or None if validation fails
    """
    # Case 1: Both spreads provided - validate they're exact negatives
    if home_spread_raw is not None and away_spread_raw is not None:
        spread_sum = abs(home_spread_raw + away_spread_raw)
        
        if spread_sum > tolerance:
            logger.error(
                f"❌ SPREAD INTEGRITY VIOLATION: {home_team} vs {away_team}\n"
                f"   Home spread: {home_spread_raw}\n"
                f"   Away spread: {away_spread_raw}\n"
                f"   Sum: {home_spread_raw + away_spread_raw} (should be ~0)\n"
                f"   Deviation: {spread_sum} > tolerance {tolerance}\n"
                f"   ⚠️ REJECTING ODDS SNAPSHOT - DO NOT SIMULATE"
            )
            return None
        
        # Validated - use home_spread as canonical
        return CanonicalOdds(
            home_team=home_team,
            away_team=away_team,
            home_spread=home_spread_raw
        )
    
    # Case 2: Only home spread provided
    elif home_spread_raw is not None:
        logger.info(f"Using home spread as canonical: {home_team} {home_spread_raw:+.1f}")
        return CanonicalOdds(
            home_team=home_team,
            away_team=away_team,
            home_spread=home_spread_raw
        )
    
    # Case 3: Only away spread provided - invert to home perspective
    elif away_spread_raw is not None:
        home_spread_canonical = -away_spread_raw
        logger.info(
            f"Deriving home spread from away: {away_team} {away_spread_raw:+.1f} "
            f"→ {home_team} {home_spread_canonical:+.1f}"
        )
        return CanonicalOdds(
            home_team=home_team,
            away_team=away_team,
            home_spread=home_spread_canonical
        )
    
    # Case 4: No spreads provided - cannot create canonical odds
    else:
        logger.warning(f"No spread data for {home_team} vs {away_team}")
        return None


def calculate_cover_outcomes(
    home_score: float,
    away_score: float,
    home_spread: float,
    push_threshold: float = 0.001
) -> Dict[str, Any]:
    """
    CANONICAL COVER LOGIC
    =====================
    Single source of truth for determining spread covers.
    
    Formula (LOCKED - DO NOT MODIFY):
        margin = home_score - away_score
        x = margin + home_spread
        
        if x > push_threshold:  home covers
        if x < -push_threshold: away covers
        else:                   push
    
    Args:
        home_score: Home team final score
        away_score: Away team final score
        home_spread: Canonical home spread (favorite negative)
        push_threshold: Tolerance for exact landing (default 0.001)
    
    Returns:
        {
            "margin": float,
            "home_covers": bool,
            "away_covers": bool,
            "is_push": bool,
            "cover_margin": float  # How much the cover won/lost by
        }
    """
    margin = home_score - away_score
    x = margin + home_spread
    
    is_push = abs(x) <= push_threshold
    home_covers = x > push_threshold
    away_covers = x < -push_threshold
    
    return {
        "margin": margin,
        "home_covers": home_covers,
        "away_covers": away_covers,
        "is_push": is_push,
        "cover_margin": x,
        "formula_used": f"({home_score} - {away_score}) + {home_spread:+.1f} = {x:+.2f}"
    }


@dataclass
class SimulationMetadata:
    """
    SIM VERSIONING SYSTEM
    =====================
    Tracks simulation version to invalidate stale results.
    
    Fields:
    - sim_version: Incremented when cover logic or spread mapping changes
    - engine_build_id: Git commit hash or deployment tag
    - odds_snapshot_id: Unique ID for the odds data used
    - generated_at: UTC timestamp of simulation run
    """
    sim_version: int
    engine_build_id: str
    odds_snapshot_id: str
    generated_at: datetime
    
    @classmethod
    def create_current(cls, odds_snapshot_id: str) -> "SimulationMetadata":
        """Create metadata for current simulation run"""
        return cls(
            sim_version=CURRENT_SIM_VERSION,
            engine_build_id=ENGINE_BUILD_ID,
            odds_snapshot_id=odds_snapshot_id,
            generated_at=datetime.utcnow()
        )
    
    def is_current(self) -> bool:
        """Check if this simulation is using current version"""
        return self.sim_version == CURRENT_SIM_VERSION
    
    def to_dict(self) -> Dict[str, Any]:
        """Export metadata for storage"""
        return {
            "sim_version": self.sim_version,
            "engine_build_id": self.engine_build_id,
            "odds_snapshot_id": self.odds_snapshot_id,
            "generated_at": self.generated_at.isoformat(),
            "is_current": self.is_current()
        }


def generate_odds_snapshot_id(
    home_team: str,
    away_team: str,
    home_spread: float,
    timestamp: datetime
) -> str:
    """
    Generate unique ID for odds snapshot.
    Used to track which odds data was used for simulation.
    
    Format: SHA256 hash of team names + spread + timestamp
    """
    snapshot_key = f"{home_team}|{away_team}|{home_spread}|{timestamp.isoformat()}"
    return hashlib.sha256(snapshot_key.encode()).hexdigest()[:16]


class IntegrityValidator:
    """
    RUNTIME INTEGRITY GUARDS
    ========================
    Blocks "EDGE DETECTED" classification when data/logic flags triggered.
    
    Guards:
    1. Spread favorite with high cover% but low win%
    2. Extreme cover% with high variance + low confidence
    3. Market vs model line implies one side, but cover probs imply opposite
    """
    
    @staticmethod
    def validate_spread_ml_consistency(
        is_favorite: bool,
        p_cover: float,
        p_win: float,
        confidence: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Guard: Spread favorite cover_prob > 80% AND win_prob < 65%
        
        This indicates data mapping error or bimodal distribution.
        """
        if is_favorite and p_cover > 0.80 and p_win < 0.65:
            return False, (
                f"DATA/LOGIC FLAG: Favorite shows {p_cover*100:.1f}% cover "
                f"but only {p_win*100:.1f}% win probability. "
                f"This suggests data mapping error or extreme bimodal outcome."
            )
        return True, None
    
    @staticmethod
    def validate_extreme_probabilities(
        p_cover: float,
        variance_label: str,
        confidence: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Guard: Extreme cover% with high variance and low confidence
        """
        if p_cover > 0.85 or p_cover < 0.15:
            if variance_label == "HIGH" and confidence < 60:
                return False, (
                    f"DATA/LOGIC FLAG: Extreme cover probability {p_cover*100:.1f}% "
                    f"with HIGH variance and low confidence ({confidence:.0f}%). "
                    f"Model output unstable."
                )
        return True, None
    
    @staticmethod
    def validate_sharp_side_consistency(
        market_spread: float,
        fair_spread: float,
        p_cover_home: float,
        p_cover_away: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Guard: Market vs model line implies one side, but cover probs imply opposite
        
        Example:
        - Market gives home +4.5, fair gives home +9.1 → should favor away
        - But if p_cover_home > p_cover_away → contradiction
        """
        delta = market_spread - fair_spread
        
        # If delta > 0, value should be on home (home getting more points)
        # So p_cover_home should be higher
        if delta > 2.0:  # Threshold for meaningful edge
            if p_cover_away > p_cover_home:
                return False, (
                    f"DATA/LOGIC FLAG: Market gives home {market_spread:+.1f} vs "
                    f"fair {fair_spread:+.1f} (home getting {delta:.1f} extra points), "
                    f"but away has higher cover probability "
                    f"({p_cover_away*100:.1f}% vs {p_cover_home*100:.1f}%). "
                    f"This indicates team/side mapping error."
                )
        
        # If delta < 0, value should be on away (home getting fewer points)
        # So p_cover_away should be higher
        elif delta < -2.0:
            if p_cover_home > p_cover_away:
                return False, (
                    f"DATA/LOGIC FLAG: Market gives home {market_spread:+.1f} vs "
                    f"fair {fair_spread:+.1f} (home getting {abs(delta):.1f} fewer points), "
                    f"but home has higher cover probability "
                    f"({p_cover_home*100:.1f}% vs {p_cover_away*100:.1f}%). "
                    f"This indicates team/side mapping error."
                )
        
        return True, None
    
    @classmethod
    def run_all_guards(
        cls,
        home_team: str,
        away_team: str,
        canonical_odds: CanonicalOdds,
        fair_spread_home: float,
        p_cover_home: float,
        p_cover_away: float,
        p_win_home: float,
        p_win_away: float,
        confidence: float,
        variance_label: str = "MODERATE"
    ) -> Tuple[bool, list]:
        """
        Run all integrity guards.
        
        Returns:
            (passed: bool, flags: list of error messages)
        """
        flags = []
        
        # Guard 1: Spread/ML consistency for favorite
        home_is_fav = canonical_odds.home_spread < 0
        passed, msg = cls.validate_spread_ml_consistency(
            home_is_fav, p_cover_home, p_win_home, confidence
        )
        if not passed:
            flags.append(msg)
        
        # Guard 2: Extreme probabilities with variance
        passed, msg = cls.validate_extreme_probabilities(
            p_cover_home, variance_label, confidence
        )
        if not passed:
            flags.append(msg)
        
        # Guard 3: Sharp side consistency
        passed, msg = cls.validate_sharp_side_consistency(
            canonical_odds.home_spread,
            fair_spread_home,
            p_cover_home,
            p_cover_away
        )
        if not passed:
            flags.append(msg)
        
        return len(flags) == 0, flags


# INTEGRITY TESTS (must pass in CI)
def test_cover_logic_home_favorite():
    """Test A: Home favorite -7.5"""
    # margin=+1 → no cover (won by 1, needed 8)
    result = calculate_cover_outcomes(20, 19, -7.5)
    assert result["home_covers"] == False
    assert result["away_covers"] == True
    
    # margin=+8 → cover (won by 8, needed 7.5)
    result = calculate_cover_outcomes(28, 20, -7.5)
    assert result["home_covers"] == True
    assert result["away_covers"] == False


def test_cover_logic_home_underdog():
    """Test B: Home dog +7.5"""
    # margin=-6 → cover (lost by 6, allowed 7.5)
    result = calculate_cover_outcomes(20, 26, 7.5)
    assert result["home_covers"] == True
    assert result["away_covers"] == False
    
    # margin=-8 → no cover (lost by 8, allowed 7.5)
    result = calculate_cover_outcomes(20, 28, 7.5)
    assert result["home_covers"] == False
    assert result["away_covers"] == True


def test_spread_symmetry():
    """Test C: Symmetry - cover probs must sum to 1 (excluding pushes)"""
    # This would be tested in monte_carlo_engine with full simulation
    # Here we just verify the formula is symmetric
    
    # Home fav -7.5
    result1 = calculate_cover_outcomes(28, 20, -7.5)  # Home +8
    result2 = calculate_cover_outcomes(27, 20, -7.5)  # Home +7
    
    # Exactly one should cover (no push at 7 vs 7.5)
    assert (result1["home_covers"] + result1["away_covers"]) == 1
    assert (result2["home_covers"] + result2["away_covers"]) == 1


if __name__ == "__main__":
    # Run integrity tests
    print("Running SIM INTEGRITY TESTS...\n")
    
    try:
        test_cover_logic_home_favorite()
        print("✅ Test A passed: Home favorite -7.5")
        
        test_cover_logic_home_underdog()
        print("✅ Test B passed: Home dog +7.5")
        
        test_spread_symmetry()
        print("✅ Test C passed: Symmetry check")
        
        print("\n✅ ALL INTEGRITY TESTS PASSED")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
