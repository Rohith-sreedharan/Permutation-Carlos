"""
NCAA Basketball (NCAAB) Edge Evaluation Service
Two-layer eligibility and grading system with college-specific calibration
"""
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timezone
from enum import Enum
from pymongo.database import Database
import uuid

from db.schemas.signal_schemas import VolatilityBucket


# ============================================================================
# ENUMS & TYPES
# ============================================================================

class NCAABState(str, Enum):
    """NCAAB game classification"""
    EDGE = "EDGE"           # Telegram-worthy
    LEAN = "LEAN"           # Informational / optional
    NO_PLAY = "NO_PLAY"     # Default


class PrimaryMarket(str, Enum):
    """Primary market for edge"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    NONE = "NONE"


class DistributionFlag(str, Enum):
    """Distribution stability assessment"""
    STABLE = "STABLE"
    TIGHT = "TIGHT"
    MEDIUM = "MEDIUM"
    UNSTABLE_EXTREME = "UNSTABLE_EXTREME"


class ReasonCode(str, Enum):
    """Classification reason codes (debugging & trust)"""
    EDGE_TOO_SMALL = "EDGE_TOO_SMALL"
    VOLATILITY_DOWNGRADED = "VOLATILITY_DOWNGRADED"
    PACE_ONLY_EDGE = "PACE_ONLY_EDGE"
    DISTRIBUTION_UNSTABLE = "DISTRIBUTION_UNSTABLE"
    SPREAD_TOO_LARGE = "SPREAD_TOO_LARGE"
    MARKET_ALIGNED = "MARKET_ALIGNED"
    VOLATILITY_EXTREME = "VOLATILITY_EXTREME"
    SPREAD_ELIGIBLE = "SPREAD_ELIGIBLE"
    TOTAL_ELIGIBLE = "TOTAL_ELIGIBLE"
    CONFIRMED_BY_MARKET = "CONFIRMED_BY_MARKET"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


# ============================================================================
# NCAAB EVALUATION THRESHOLDS (CONFIG-DRIVEN)
# ============================================================================

class NCAABThresholds:
    """Configuration-driven thresholds for NCAAB logic"""
    
    # Probability normalization
    COMPRESSION_FACTOR = 0.80
    
    # SPREAD MARKET ELIGIBILITY
    SPREAD_ELIGIBILITY_EDGE = 4.5  # pts
    
    # SPREAD MARKET GRADING
    SPREAD_EDGE_THRESHOLD = 6.0    # pts
    SPREAD_LEAN_MIN = 4.5           # pts
    SPREAD_LEAN_MAX = 5.9           # pts
    
    # SPREAD SIZE GUARDRAILS
    AUTO_ALLOWED_FAVORITE = -12.5   # pts
    AUTO_ALLOWED_UNDERDOG = 12.5    # pts
    LARGE_SPREAD_EDGE_REQUIREMENT = 7.5  # pts if beyond ±12.5
    
    # TOTALS MARKET ELIGIBILITY
    TOTAL_ELIGIBILITY_EDGE = 5.5    # pts
    
    # TOTALS MARKET GRADING
    TOTAL_EDGE_THRESHOLD = 7.0      # pts
    TOTAL_LEAN_MIN = 5.5            # pts
    TOTAL_LEAN_MAX = 6.9            # pts
    
    # MARKET CONFIRMATION (supportive, not required)
    MARKET_CONFIRMATION_CLV = 0.003  # +0.3%
    
    # VOLATILITY & DISTRIBUTION
    VOLATILITY_DOWNGRADE_THRESHOLD = "HIGH"
    VOLATILITY_BLOCK_THRESHOLD = "EXTREME"
    
    # DEFAULT STATE
    DEFAULT_STATE = NCAABState.NO_PLAY


# ============================================================================
# NCAAB EVALUATION RESULT
# ============================================================================

class NCAABEvaluationResult:
    """Complete evaluation output for a game"""
    
    def __init__(
        self,
        game_id: str,
        state: NCAABState,
        primary_market: PrimaryMarket,
        reason_codes: List[str],
        spread_edge: Optional[float] = None,
        total_edge: Optional[float] = None,
        compressed_prob_spread: Optional[float] = None,
        compressed_prob_total: Optional[float] = None,
        volatility_bucket: Optional[str] = None,
        distribution_flag: Optional[DistributionFlag] = None,
        market_confirmation: bool = False,
        evaluated_at: Optional[datetime] = None
    ):
        self.game_id = game_id
        self.state = state
        self.primary_market = primary_market
        self.reason_codes = reason_codes
        self.spread_edge = spread_edge
        self.total_edge = total_edge
        self.compressed_prob_spread = compressed_prob_spread
        self.compressed_prob_total = compressed_prob_total
        self.volatility_bucket = volatility_bucket
        self.distribution_flag = distribution_flag
        self.market_confirmation = market_confirmation
        self.evaluated_at = evaluated_at or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "state": self.state.value,
            "primary_market": self.primary_market.value,
            "reason_codes": self.reason_codes,
            "spread_edge": self.spread_edge,
            "total_edge": self.total_edge,
            "compressed_prob_spread": self.compressed_prob_spread,
            "compressed_prob_total": self.compressed_prob_total,
            "volatility_bucket": self.volatility_bucket,
            "distribution_flag": self.distribution_flag.value if self.distribution_flag else None,
            "market_confirmation": self.market_confirmation,
            "evaluated_at": self.evaluated_at.isoformat()
        }


# ============================================================================
# NCAAB EDGE EVALUATOR
# ============================================================================

class NCAABEdgeEvaluator:
    """
    Two-layer NCAAB edge evaluation system
    
    Layer A: Eligibility (can the game be considered?)
    Layer B: Grading (EDGE / LEAN / NO_PLAY)
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.thresholds = NCAABThresholds()
    
    # ========================================================================
    # PROBABILITY NORMALIZATION (MANDATORY)
    # ========================================================================
    
    def normalize_probability(self, raw_prob: float) -> float:
        """
        Compress raw simulation probability to remove false certainty
        
        Formula: compressed_prob = 0.5 + (raw_prob - 0.5) * 0.80
        
        Examples:
        - 0.50 → 0.50 (unchanged)
        - 0.55 → 0.54 (compressed)
        - 0.65 → 0.62 (compressed)
        - 0.70 → 0.66 (compressed)
        """
        if raw_prob is None or not (0 <= raw_prob <= 1):
            return 0.5
        
        compressed = 0.5 + (raw_prob - 0.5) * self.thresholds.COMPRESSION_FACTOR
        return max(0.5, min(1.0, compressed))  # Clamp to [0.5, 1.0]
    
    # ========================================================================
    # DISTRIBUTION ASSESSMENT
    # ========================================================================
    
    def assess_distribution(
        self,
        distribution_width: float,
        volatility_bucket: str
    ) -> DistributionFlag:
        """
        Assess distribution stability based on width and volatility
        
        Returns: STABLE, TIGHT, MEDIUM, or UNSTABLE_EXTREME
        """
        # If volatility extreme, distribution is unstable
        if volatility_bucket == "EXTREME":
            return DistributionFlag.UNSTABLE_EXTREME
        
        # Assess based on distribution width
        if distribution_width <= 5.0:
            return DistributionFlag.TIGHT
        elif distribution_width <= 8.5:
            return DistributionFlag.MEDIUM
        elif volatility_bucket == "HIGH":
            return DistributionFlag.UNSTABLE_EXTREME
        else:
            return DistributionFlag.STABLE
    
    # ========================================================================
    # LAYER A: ELIGIBILITY CHECKS
    # ========================================================================
    
    def check_spread_eligibility(
        self,
        spread_edge: float,
        distribution_flag: DistributionFlag
    ) -> bool:
        """
        Layer A: Can this game be considered for spread edge?
        
        Simple eligibility: just check edge and distribution
        """
        # Distribution check
        if distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
            return False
        
        # Edge check
        if spread_edge < self.thresholds.SPREAD_ELIGIBILITY_EDGE:
            return False
        
        return True
    
    def check_total_eligibility(
        self,
        total_edge: float,
        distribution_flag: DistributionFlag
    ) -> bool:
        """
        Layer A: Can this game be considered for totals edge?
        """
        # Distribution check
        if distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
            return False
        
        # Edge check
        if total_edge < self.thresholds.TOTAL_ELIGIBILITY_EDGE:
            return False
        
        return True
    
    # ========================================================================
    # LAYER B: GRADING (EDGE / LEAN / NO_PLAY)
    # ========================================================================
    
    def grade_spread_market(
        self,
        spread_edge: float,
        spread_line: float,
        volatility_bucket: str,
        distribution_flag: DistributionFlag,
        compressed_prob: float,
        reason_codes: List[str]
    ) -> tuple[NCAABState, PrimaryMarket, List[str]]:
        """
        Layer B: Grade spread market
        
        Returns: (state, primary_market, updated_reason_codes)
        """
        # Check eligibility first
        if not self.check_spread_eligibility(spread_edge, distribution_flag):
            reason_codes.append(ReasonCode.EDGE_TOO_SMALL.value)
            return NCAABState.NO_PLAY, PrimaryMarket.NONE, reason_codes
        
        # Eligibility passed, now grade
        reason_codes.append(ReasonCode.SPREAD_ELIGIBLE.value)
        
        # Check spread size guardrails
        if abs(spread_line) > 12.5:
            if spread_edge < self.thresholds.LARGE_SPREAD_EDGE_REQUIREMENT:
                reason_codes.append(ReasonCode.SPREAD_TOO_LARGE.value)
                return NCAABState.NO_PLAY, PrimaryMarket.SPREAD, reason_codes
        
        # Check volatility
        if volatility_bucket == "EXTREME":
            reason_codes.append(ReasonCode.VOLATILITY_EXTREME.value)
            return NCAABState.NO_PLAY, PrimaryMarket.SPREAD, reason_codes
        
        # Grade as EDGE or LEAN
        if spread_edge >= self.thresholds.SPREAD_EDGE_THRESHOLD:
            # Check if volatility downgrades to LEAN
            if volatility_bucket == "HIGH":
                reason_codes.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
                return NCAABState.LEAN, PrimaryMarket.SPREAD, reason_codes
            
            return NCAABState.EDGE, PrimaryMarket.SPREAD, reason_codes
        
        elif self.thresholds.SPREAD_LEAN_MIN <= spread_edge < self.thresholds.SPREAD_EDGE_THRESHOLD:
            return NCAABState.LEAN, PrimaryMarket.SPREAD, reason_codes
        
        else:
            reason_codes.append(ReasonCode.EDGE_TOO_SMALL.value)
            return NCAABState.NO_PLAY, PrimaryMarket.SPREAD, reason_codes
    
    def grade_total_market(
        self,
        total_edge: float,
        volatility_bucket: str,
        distribution_flag: DistributionFlag,
        pace_driven: bool,
        reason_codes: List[str]
    ) -> tuple[NCAABState, PrimaryMarket, List[str]]:
        """
        Layer B: Grade totals market
        
        Handles pace-driven edges by downgrading but not invalidating
        """
        # Check eligibility first
        if not self.check_total_eligibility(total_edge, distribution_flag):
            reason_codes.append(ReasonCode.EDGE_TOO_SMALL.value)
            return NCAABState.NO_PLAY, PrimaryMarket.NONE, reason_codes
        
        # Eligibility passed, now grade
        reason_codes.append(ReasonCode.TOTAL_ELIGIBLE.value)
        
        # Check volatility
        if volatility_bucket == "EXTREME":
            reason_codes.append(ReasonCode.VOLATILITY_EXTREME.value)
            return NCAABState.NO_PLAY, PrimaryMarket.TOTAL, reason_codes
        
        # Grade as EDGE or LEAN
        if total_edge >= self.thresholds.TOTAL_EDGE_THRESHOLD:
            # Check if pace-driven (downgrade but keep valid)
            if pace_driven:
                reason_codes.append(ReasonCode.PACE_ONLY_EDGE.value)
                return NCAABState.LEAN, PrimaryMarket.TOTAL, reason_codes
            
            # Check if high volatility downgrades to LEAN
            if volatility_bucket == "HIGH":
                reason_codes.append(ReasonCode.VOLATILITY_DOWNGRADED.value)
                return NCAABState.LEAN, PrimaryMarket.TOTAL, reason_codes
            
            return NCAABState.EDGE, PrimaryMarket.TOTAL, reason_codes
        
        elif self.thresholds.TOTAL_LEAN_MIN <= total_edge < self.thresholds.TOTAL_EDGE_THRESHOLD:
            if pace_driven:
                reason_codes.append(ReasonCode.PACE_ONLY_EDGE.value)
            return NCAABState.LEAN, PrimaryMarket.TOTAL, reason_codes
        
        else:
            reason_codes.append(ReasonCode.EDGE_TOO_SMALL.value)
            return NCAABState.NO_PLAY, PrimaryMarket.TOTAL, reason_codes
    
    # ========================================================================
    # MARKET CONFIRMATION (OPTIONAL, SUPPORTIVE)
    # ========================================================================
    
    def check_market_confirmation(
        self,
        clv_forecast: Optional[float],
        line_move_toward_model: bool
    ) -> bool:
        """
        Check if market confirms edge
        
        Supportive signal only (never required):
        - CLV forecast ≥ +0.3%
        - OR line moved toward model
        """
        if clv_forecast is not None and clv_forecast >= self.thresholds.MARKET_CONFIRMATION_CLV:
            return True
        
        if line_move_toward_model:
            return True
        
        return False
    
    def apply_market_confirmation(
        self,
        state: NCAABState,
        market_confirmation: bool,
        reason_codes: List[str]
    ) -> NCAABState:
        """
        Apply market confirmation
        
        Can upgrade high LEAN → EDGE (near threshold), never blocks
        """
        if market_confirmation and state == NCAABState.LEAN:
            # Supportive signal can upgrade LEAN
            reason_codes.append(ReasonCode.MARKET_ALIGNED.value)
            # Only upgrade if it's a "high LEAN" (close to EDGE threshold)
            # This is handled by the caller based on edge metrics
        
        return state
    
    # ========================================================================
    # MAIN EVALUATION FUNCTION
    # ========================================================================
    
    async def evaluate_game(
        self,
        game_id: str,
        simulation_output: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> NCAABEvaluationResult:
        """
        Complete NCAAB game evaluation
        
        Two-layer system:
        Layer A: Eligibility (edge + distribution)
        Layer B: Grading (EDGE / LEAN / NO_PLAY)
        """
        reason_codes: List[str] = []
        
        # Extract data
        raw_spread_prob = simulation_output.get("spread_win_probability", 0.5)
        raw_total_prob = simulation_output.get("total_win_probability", 0.5)
        
        spread_edge = simulation_output.get("spread_edge_pts", 0)
        total_edge = simulation_output.get("total_edge_pts", 0)
        
        volatility_bucket = simulation_output.get("volatility_bucket", "MEDIUM")
        distribution_width = simulation_output.get("distribution_width", 7.0)
        
        spread_line = market_data.get("spread_line", 0)
        clv_forecast = market_data.get("clv_forecast")
        line_move_toward_model = market_data.get("line_move_toward_model", False)
        pace_driven_total = simulation_output.get("pace_driven_total", False)
        
        # Normalize probabilities
        compressed_prob_spread = self.normalize_probability(raw_spread_prob)
        compressed_prob_total = self.normalize_probability(raw_total_prob)
        
        # Assess distribution
        distribution_flag = self.assess_distribution(distribution_width, volatility_bucket)
        
        if distribution_flag == DistributionFlag.UNSTABLE_EXTREME:
            reason_codes.append(ReasonCode.DISTRIBUTION_UNSTABLE.value)
        
        # Check market confirmation
        market_confirmation = self.check_market_confirmation(clv_forecast, line_move_toward_model)
        
        # Grade spread and total markets
        spread_state, spread_market, reason_codes = self.grade_spread_market(
            spread_edge=spread_edge,
            spread_line=spread_line,
            volatility_bucket=volatility_bucket,
            distribution_flag=distribution_flag,
            compressed_prob=compressed_prob_spread,
            reason_codes=reason_codes
        )
        
        total_state, total_market, reason_codes = self.grade_total_market(
            total_edge=total_edge,
            volatility_bucket=volatility_bucket,
            distribution_flag=distribution_flag,
            pace_driven=pace_driven_total,
            reason_codes=reason_codes
        )
        
        # Determine final state (prefer EDGE if available, then LEAN)
        if spread_state == NCAABState.EDGE or total_state == NCAABState.EDGE:
            final_state = NCAABState.EDGE
            primary_market = PrimaryMarket.SPREAD if spread_state == NCAABState.EDGE else PrimaryMarket.TOTAL
        elif spread_state == NCAABState.LEAN or total_state == NCAABState.LEAN:
            final_state = NCAABState.LEAN
            primary_market = PrimaryMarket.SPREAD if spread_state == NCAABState.LEAN else PrimaryMarket.TOTAL
        else:
            final_state = NCAABState.NO_PLAY
            primary_market = PrimaryMarket.NONE
        
        # Apply market confirmation (can upgrade high LEAN)
        if final_state == NCAABState.LEAN and market_confirmation:
            # Check if this is a high LEAN (close to EDGE threshold)
            spread_high_lean = (self.thresholds.SPREAD_LEAN_MAX - 0.5 <= spread_edge <= self.thresholds.SPREAD_LEAN_MAX)
            total_high_lean = (self.thresholds.TOTAL_LEAN_MAX - 0.5 <= total_edge <= self.thresholds.TOTAL_LEAN_MAX)
            
            if spread_high_lean or total_high_lean:
                final_state = self.apply_market_confirmation(final_state, market_confirmation, reason_codes)
                if ReasonCode.MARKET_ALIGNED.value in reason_codes:
                    final_state = NCAABState.EDGE
        
        # Create result
        result = NCAABEvaluationResult(
            game_id=game_id,
            state=final_state,
            primary_market=primary_market,
            reason_codes=reason_codes,
            spread_edge=spread_edge,
            total_edge=total_edge,
            compressed_prob_spread=compressed_prob_spread,
            compressed_prob_total=compressed_prob_total,
            volatility_bucket=volatility_bucket,
            distribution_flag=distribution_flag,
            market_confirmation=market_confirmation
        )
        
        # Store in database
        self.db["ncaab_evaluations"].insert_one({
            "game_id": game_id,
            "evaluation": result.to_dict(),
            "created_at": datetime.now(timezone.utc),
            "archived": False
        })
        
        return result
    
    # ========================================================================
    # BATCH EVALUATION (FOR DAILY SLATES)
    # ========================================================================
    
    async def evaluate_slate(
        self,
        games: List[Dict[str, Any]]
    ) -> List[NCAABEvaluationResult]:
        """
        Evaluate multiple games for a daily slate
        
        Returns list of evaluations
        """
        results = []
        
        for game in games:
            try:
                result = await self.evaluate_game(
                    game_id=game["game_id"],
                    simulation_output=game.get("simulation_output", {}),
                    market_data=game.get("market_data", {})
                )
                results.append(result)
            except Exception as e:
                # Log error but continue with other games
                print(f"Error evaluating game {game.get('game_id')}: {e}")
                continue
        
        return results
    
    # ========================================================================
    # SANITY CHECK (VALIDATION)
    # ========================================================================
    
    async def validate_system_behavior(
        self,
        evaluations: List[NCAABEvaluationResult]
    ) -> Dict[str, Any]:
        """
        Validate that system behavior matches expected patterns
        
        Expected:
        - Majority → NO_PLAY
        - Several LEANS
        - 1-3 EDGES max
        - Win probabilities mostly 54-60%
        """
        edge_count = sum(1 for e in evaluations if e.state == NCAABState.EDGE)
        lean_count = sum(1 for e in evaluations if e.state == NCAABState.LEAN)
        no_play_count = sum(1 for e in evaluations if e.state == NCAABState.NO_PLAY)
        
        total_count = len(evaluations)
        
        # Calculate probability distribution
        probs: List[float] = [
            p for p in [
                e.compressed_prob_spread or e.compressed_prob_total
                for e in evaluations
            ] if p is not None
        ]
        
        avg_prob = sum(probs) / len(probs) if probs else 0.5
        probs_54_60 = sum(1 for p in probs if 0.54 <= p <= 0.60)
        
        return {
            "total_games": total_count,
            "edge_count": edge_count,
            "lean_count": lean_count,
            "no_play_count": no_play_count,
            "edge_percentage": (edge_count / total_count * 100) if total_count else 0,
            "lean_percentage": (lean_count / total_count * 100) if total_count else 0,
            "no_play_percentage": (no_play_count / total_count * 100) if total_count else 0,
            "average_probability": avg_prob,
            "probs_54_60_count": probs_54_60,
            "probs_54_60_percentage": (probs_54_60 / len(probs) * 100) if probs else 0,
            "health_check": {
                "edges_reasonable": 0 <= edge_count <= 3,
                "leans_present": lean_count > 0,
                "mostly_no_play": no_play_count > (total_count * 0.7),
                "probs_in_range": ((probs_54_60 / len(probs) * 100) > 60) if probs else False
            }
        }
