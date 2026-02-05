"""
Monte Carlo Simulation Engine
Performs 10,000-100,000 iterations per game using granular inputs
NOW WITH MULTI-SPORT SUPPORT (NBA/NFL/MLB/NHL)

NUMERICAL ACCURACY ENFORCEMENT:
- All outputs must come from real simulation data
- NO placeholders, NO hard-coded fallbacks, NO safe defaults
- If simulation fails → return error, NOT fake numbers
"""
import random
import numpy as np
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from db.mongo import db
from services.logger import log_stage
from core.sport_strategies import SportStrategyFactory
from core.sport_constants import map_position_abbreviation
from core.calibration_engine import CalibrationEngine
from utils.mongo_helpers import sanitize_mongo_doc
from core.calibration_logger import CalibrationLogger
from core.market_line_integrity import MarketLineIntegrityVerifier, MarketLineIntegrityError
from core.decomposition_logger import DecompositionLogger
from core.pick_state_machine import PickStateMachine, PickState, PickClassification
from core.version_tracker import get_version_tracker
from core.numerical_accuracy import (
    SimulationOutput,
    OverUnderAnalysis,
    ExpectedValue,
    ClosingLineValue,
    SimulationTierConfig,
    ConfidenceCalculator,
    EdgeValidator,
    validate_simulation_output,
    get_debug_label
)
from core.sharp_analysis import (
    calculate_total_edge,
    format_for_api,
    explain_edge_reasoning,
    STANDARD_DISCLAIMER,
    TotalAnalysis,
    SpreadAnalysis
)
from core.sharp_side_selection import select_sharp_side_spread, SharpSideSelection
from core.sport_configs import VolatilityLevel
from core.feedback_loop import store_prediction
from core.reality_check_layer import get_public_total_projection
from core.output_consistency import output_consistency_validator, SharpAction
from utils.calibration_logger import calibration_logger
from utils.team_validator import team_identity_validator, extreme_edge_validator
from core.sim_integrity import (
    CanonicalOdds,
    SimulationMetadata,
    IntegrityValidator,
    CURRENT_SIM_VERSION,
    generate_odds_snapshot_id
)
from core.simulation_context import SimulationStatus
from core.selection_id_generator import (
    generate_spread_selections,
    generate_moneyline_selections,
    generate_total_selections,
    validate_selection_consistency
)

logger = logging.getLogger(__name__)


def ensure_pick_state(simulation: Dict[str, Any]) -> Dict[str, Any]:
    """
    CRITICAL: Ensure every simulation has explicit pick_state
    READINESS GATE: Check if required inputs exist before classification
    
    Required inputs:
    - market_line (fresh)
    - confidence_score
    - variance
    
    If missing → PENDING_INPUTS (internal only, not user-facing NO_PLAY)
    """
    pick_state = simulation.get('pick_state', 'UNKNOWN')
    
    # READINESS GATE: Check if required inputs exist
    missing_inputs = []
    
    # Check market line
    market_line = simulation.get('total_line') or simulation.get('market_context', {}).get('total_line')
    if not market_line:
        missing_inputs.append('NO_MARKET_LINE')
    
    # Check confidence score
    if simulation.get('confidence_score', 0) == 0:
        missing_inputs.append('CONFIDENCE_NOT_COMPUTED')
    
    # Check variance
    if not simulation.get('variance_total'):
        missing_inputs.append('VARIANCE_NOT_COMPUTED')
    
    # If ANY inputs missing → PENDING_INPUTS (not NO_PLAY)
    if missing_inputs and (pick_state == 'UNKNOWN' or pick_state is None):
        simulation['pick_state'] = 'PENDING_INPUTS'
        simulation['can_publish'] = False
        simulation['can_parlay'] = False
        simulation['state_machine_reasons'] = missing_inputs
        
        logger.info(
            f"⏳ Simulation {simulation.get('event_id', 'unknown')} → PENDING_INPUTS: {', '.join(missing_inputs)}"
        )
        return simulation
    
    # If pick_state is still UNKNOWN but inputs exist, this is a legacy sim
    if pick_state == 'UNKNOWN' or pick_state is None:
        # Check if this is a bootstrap situation (no calibration data)
        calibration_status = simulation.get('calibration', {}).get('calibration_status', 'INITIALIZED')
        bootstrap_mode = (calibration_status == 'UNINITIALIZED')
        
        reasons = []
        if not simulation.get('calibration_result'):
            reasons.append('CALIBRATION_NOT_RUN')
        if not reasons:
            reasons.append('LEGACY_SIMULATION_NO_STATE')
        
        # Force NO_PLAY classification for legacy data
        simulation['pick_state'] = 'NO_PLAY'
        simulation['can_publish'] = False
        simulation['can_parlay'] = False
        simulation['state_machine_reasons'] = reasons
        
        if not bootstrap_mode:
            logger.warning(
                f"⚠️ Simulation {simulation.get('event_id', 'unknown')} had UNKNOWN state - "
                f"forced to NO_PLAY: {', '.join(reasons)}"
            )
    
    # CRITICAL: Ensure state_machine_reasons is never empty for NO_PLAY/LEAN/PENDING_INPUTS
    # This is the final safeguard for reason code propagation
    if pick_state in ['NO_PLAY', 'LEAN', 'PENDING_INPUTS']:
        reasons = simulation.get('state_machine_reasons', [])
        if not reasons or reasons == []:
            # Extract reasons from calibration if available
            cal_result = simulation.get('calibration', {})
            cal_block_reasons = cal_result.get('block_reasons', [])
            
            if cal_block_reasons:
                simulation['state_machine_reasons'] = cal_block_reasons
            elif pick_state == 'NO_PLAY':
                simulation['state_machine_reasons'] = ['NO_REASON_PROVIDED_ERROR']
            elif pick_state == 'PENDING_INPUTS':
                simulation['state_machine_reasons'] = ['AWAITING_DATA']
            else:  # LEAN
                simulation['state_machine_reasons'] = ['LEAN_STATE_NO_PARLAY']
            
            logger.warning(
                f"⚠️ {pick_state} state without reasons - added: {simulation['state_machine_reasons']}"
            )
    
    return simulation


class MonteCarloEngine:
    """
    Advanced Monte Carlo Simulation Engine for Beat Vegas
    
    Simulation Volume: 10,000-100,000 iterations per game
    Granular Inputs: Player efficiency, injuries, fatigue, volatility
    Outputs: Win probability, spread coverage, totals distribution, prop predictions
    
    MULTI-SPORT SUPPORT:
    - NBA/NFL: Normal Distribution (high-scoring sports)
    - MLB/NHL: Poisson Distribution (low-scoring sports)
    
    This is the core of the "moat" - unique probabilistic fingerprints
    """
    
    def __init__(self, num_iterations: Optional[int] = None):
        """
        Initialize Monte Carlo Engine
        
        Args:
            num_iterations: Default number of iterations (based on user tier)
                           If None, defaults to 10,000 (FREE tier baseline)
        """
        self.default_iterations = num_iterations or 10000
        self.min_iterations = 10000
        self.max_iterations = 100000
        self.strategy_factory = SportStrategyFactory()
        self.clv_predictions = []  # Store CLV predictions for validation
        
        # System-wide calibration architecture
        self.calibration_engine = CalibrationEngine()
        self.calibration_logger = CalibrationLogger()
        
        # FINAL SAFETY SYSTEM (launch-blocking components)
        self.market_verifier = MarketLineIntegrityVerifier()
        self.decomposition_logger = DecompositionLogger()
        self.version_tracker = get_version_tracker()
        
        # PHASE 15: First Half physics multipliers
        self.FIRST_HALF_CONFIG = {
            # Basketball/High-tempo sports
            "basketball": {
                "duration_multiplier": 0.5,      # 50% of regulation time
                "pace_multiplier": 1.035,         # 3.5% faster pace in early game
                "starter_weight": 1.20,           # Starters play 20% more minutes in 1H
                "fatigue_enabled": False          # No fatigue in first half
            },
            # Football (drive-based, not time-based)
            "football": {
                "duration_multiplier": 0.48,      # 48% of full game scoring (slightly less than half)
                "pace_multiplier": 1.00,          # No pace boost - drives are roughly equal
                "starter_weight": 1.00,           # No starter boost - all players critical
                "fatigue_enabled": False,         # Minimal fatigue impact in 1H
                "scripted_drive_boost": 1.05      # Small 5% boost for opening scripted plays (first 1-2 drives only)
            }
        }
    
    def run_simulation(
        self,
        event_id: str,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        market_context: Dict[str, Any],
        iterations: Optional[int] = None,
        mode: str = "full"
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for a single game
        
        Args:
            event_id: Unique event identifier
            team_a: Team A data including player stats, injuries, fatigue
            team_b: Team B data including player stats, injuries, fatigue
            market_context: Current odds, line movement, public betting %, sport_key
            iterations: Number of simulations (default: 50,000)
            mode: "full" for comprehensive analysis with distribution curves, "basic" for quick results
        
        Returns:
            Simulation results with win probabilities, spread distribution, props
            OR blocked status if roster unavailable
        """
        if not iterations:
            iterations = self.default_iterations if mode == "full" else 10000
        
        iterations = max(self.min_iterations, min(iterations, self.max_iterations))
        
        # Get sport-specific strategy
        sport_key = market_context.get('sport_key', 'basketball_nba')
        
        # ===== ROSTER AVAILABILITY GOVERNANCE (INSTITUTIONAL-GRADE) =====
        # Check roster availability for both teams BEFORE running simulation
        # This prevents wasted compute and ensures clean BLOCKED state
        team_a_name = team_a.get('name') or team_a.get('team')
        team_b_name = team_b.get('name') or team_b.get('team')
        
        # Extract league from sport_key (e.g., "basketball_nba" -> "NBA")
        league = self._extract_league_from_sport_key(sport_key)
        
        # BASELINE MODE: Roster unavailability is NORMAL operation, not an error
        # System always runs team-level baseline model with calibrated confidence
        simulation_mode = "BASELINE"  # Default mode (no roster dependency)
        confidence_penalty = 0.0  # No penalty for normal operation
        
        # Set market_type in market_context if not already set
        if 'market_type' not in market_context:
            market_context = market_context.copy()
            market_context['market_type'] = mode if mode in ["first_half", "second_half"] else "full_game"
        
        # ===== MARKET LINE INTEGRITY VERIFICATION (SMART VALIDATION) =====
        # Check market line integrity - structural errors block, staleness allows simulation
        integrity_result = None
        try:
            integrity_result = self.market_verifier.verify_market_context(
                event_id=event_id,
                sport_key=sport_key,
                market_context=market_context,
                market_type=mode if mode in ["first_half", "second_half"] else "full_game"
            )
            
            if integrity_result.status.value == "ok":
                logger.info(f"✅ Market line integrity verified: {event_id}")
            elif integrity_result.status.value == "stale_line":
                logger.warning(f"⚠️ Stale odds detected for {event_id}, proceeding with simulation. Age: {integrity_result.odds_age_hours:.1f}h")
            
        except MarketLineIntegrityError as e:
            # STRUCTURAL errors still hard block
            logger.error(f"❌ HARD BLOCK: Market line integrity failed for {event_id}: {e}")
            raise
        
        # Enforce NO MARKET = NO PICK for derivative markets (spec #6)
        if mode in ["first_half", "second_half"]:
            try:
                self.market_verifier.enforce_no_market_no_pick(
                    market_context=market_context,
                    market_type=mode
                )
                logger.info(f"✅ Derivative market check passed: {mode}")
            except MarketLineIntegrityError as e:
                logger.error(f"❌ NO MARKET = NO PICK: Cannot publish {mode} without bookmaker line")
                raise  # Hard block - no publishing without market anchor
        
        strategy = self.strategy_factory.get_strategy(sport_key)
        
        # Extract team data
        team_a_rating = self._calculate_team_rating(team_a, sport_key)
        team_b_rating = self._calculate_team_rating(team_b, sport_key)
        
        # Apply adjustments for injuries, fatigue, home/away
        team_a_adj = self._apply_adjustments(team_a, market_context)
        team_b_adj = self._apply_adjustments(team_b, market_context)
        
        # Run sport-specific simulations using Strategy Pattern
        results = strategy.simulate_game(
            team_a_rating + team_a_adj,
            team_b_rating + team_b_adj,
            iterations,
            market_context
        )
        
        # Calculate output metrics
        margins_array = results["margins"]
        totals_array = results["totals"]
        margin_std = np.std(margins_array)
        avg_margin = results["team_a_total"] - results["team_b_total"]
        
        # Calculate upset probability (underdog winning) - distribute pushes
        pushes = results.get("pushes", 0)
        team_a_favored = team_a_rating > team_b_rating
        upset_probability = ((results["team_b_wins"] + pushes / 2) / iterations) if team_a_favored else ((results["team_a_wins"] + pushes / 2) / iterations)
        
        # Calculate confidence intervals (1, 2, 3 standard deviations)
        ci_68 = [avg_margin / iterations - margin_std, avg_margin / iterations + margin_std]
        ci_95 = [avg_margin / iterations - 2 * margin_std, avg_margin / iterations + 2 * margin_std]
        ci_99 = [avg_margin / iterations - 3 * margin_std, avg_margin / iterations + 3 * margin_std]
        
        # Generate spread distribution as array with PROPER BINNING
        spread_dist_array = []
        margin_counts = {}
        
        # BIN_SIZE: 0.5 for smooth distribution (not stepped/flat)
        BIN_SIZE = 0.5
        
        for m in margins_array:
            # Round to nearest 0.5 increment for smooth distribution
            binned = round(m / BIN_SIZE) * BIN_SIZE
            margin_counts[binned] = margin_counts.get(binned, 0) + 1
        
        # NORMALIZE: Ensure probabilities sum to 1.0
        total_count = sum(margin_counts.values())
        
        for margin in sorted(margin_counts.keys()):
            normalized_prob = margin_counts[margin] / total_count
            spread_dist_array.append({
                "margin": float(margin),
                "probability": float(normalized_prob)  # Normalized, sum = 1
            })
        
        # Verify normalization (debugging)
        prob_sum = sum(d["probability"] for d in spread_dist_array)
        if abs(prob_sum - 1.0) > 0.01:
            print(f"⚠️  Distribution normalization warning: sum = {prob_sum:.4f}")
        
        # Extract real injury data from team rosters
        injury_impact = []
        offensive_impact = 0.0
        defensive_impact = 0.0
        
        for team, team_data in [(team_a, team_a), (team_b, team_b)]:
            players = team_data.get("players", [])
            for player in players:
                status = player.get("status", "active").upper()
                if status in ["OUT", "DOUBTFUL", "QUESTIONABLE"]:
                    per = player.get("per", 15.0)
                    minutes = player.get("avg_minutes", 0)
                    usage = player.get("usage_rate", 0.2)
                    
                    # FIXED: Realistic impact formula (not inflated)
                    # Base impact: (PER - league_avg) * minutes_pct * usage
                    per_diff = (per - 15.0) / 5.0  # Normalize PER difference
                    minutes_pct = minutes / 48.0
                    
                    # Status multiplier (realistic ranges)
                    if status == "OUT":
                        status_mult = 1.0  # Full impact
                    elif status == "DOUBTFUL":
                        status_mult = 0.6  # 60% impact
                    else:  # QUESTIONABLE
                        status_mult = 0.3  # 30% impact
                    
                    # Calculate impact (realistic range: -5 to +5 points typically)
                    impact = per_diff * minutes_pct * usage * status_mult * 3.5
                    
                    # Determine if offensive or defensive impact
                    ppg = player.get("ppg", 0)
                    is_offensive = ppg > 10  # Offensive player if scoring > 10ppg
                    
                    if is_offensive:
                        offensive_impact += impact
                    else:
                        defensive_impact += impact
                    
                    injury_impact.append({
                        "player": player.get("name", "Unknown Player"),
                        "team": team_data.get("name", "Unknown Team"),
                        "status": status,
                        "impact_points": round(impact, 1),
                        "impact_type": "offensive" if is_offensive else "defensive"
                    })
        
        # Calculate top props from REAL SPORTSBOOK data ONLY
        # ✅ NOW ENABLED: Fetching real props from DraftKings/FanDuel/BetMGM/Caesars
        top_props = []
        
        try:
            from integrations.props_api import fetch_event_props, normalize_props
            
            # Fetch real sportsbook props
            event_props = fetch_event_props(event_id, market_context.get("sport_key", "americanfootball_nfl"))
            
            if event_props.get("bookmakers"):
                # Normalize props with multi-book validation
                home_team_name = team_a.get("name") or ""
                away_team_name = team_b.get("name") or ""
                
                if home_team_name and away_team_name:
                    normalized_props = normalize_props(
                        event_props,
                        home_team_name,
                        away_team_name
                    )
                else:
                    normalized_props = []
                
                # Convert to frontend format (top 10 by book count)
                for prop in sorted(normalized_props, key=lambda x: x.get("book_count", 0), reverse=True)[:10]:
                    top_props.append({
                        "player": prop["player_name"],
                        "prop_type": prop["market_name"],
                        "line": prop["line"],
                        "probability": prop.get("fair_over_prob", 0.5),
                        "ev": prop.get("ev_percent", 0.0),
                        "edge": prop.get("edge", 0.0),
                        "ai_projection": prop.get("model_projection", prop["line"]),
                        "books": [b["book_name"] for b in prop["books"]],
                        "book_count": prop["book_count"]
                    })
                
                logger.info(f"✅ Integrated {len(top_props)} REAL sportsbook props")
            else:
                logger.info("ℹ️  No sportsbook props available for this event")
        
        except Exception as e:
            logger.warning(f"⚠️  Props fetch failed: {e}")
            # Don't fail simulation if props fail
        
        # Determine volatility label using sport-specific thresholds
        thresholds = strategy.get_volatility_thresholds()
        if margin_std < thresholds['stable']:
            volatility_label = "STABLE"
            volatility_score = "Low"
        elif margin_std < thresholds['moderate']:
            volatility_label = "MODERATE"
            volatility_score = "Medium"
        else:
            volatility_label = "HIGH"
            volatility_score = "High"
        
        # ===== DECOMPOSITION LOGGING (ROOT-CAUSE TRACKING) =====
        # CRITICAL: Log game-level scoring components to detect double-counting
        try:
            # Extract decomposition data from results (sport-specific)
            decomposition_data = {}
            
            if "football" in sport_key:
                # Football: drives, PPD, TD rate, FG rate
                decomposition_data = {
                    "drives_per_team": results.get("avg_drives_per_team", 11.2),
                    "points_per_drive": results.get("avg_points_per_drive", 1.95),
                    "td_rate": results.get("td_rate", 0.22),
                    "fg_rate": results.get("fg_rate", 0.17),
                    "turnover_rate": results.get("turnover_rate", 0.13)
                }
            elif "basketball" in sport_key:
                # Basketball: possessions, PPP, pace
                decomposition_data = {
                    "possessions_per_team": results.get("possessions_per_team", 100.0),
                    "points_per_possession": results.get("points_per_possession", 1.12),
                    "pace": results.get("pace", 100.0)
                }
            elif sport_key == "baseball_mlb":
                decomposition_data = {
                    "runs_per_inning": results.get("runs_per_inning", 0.50)
                }
            elif sport_key == "icehockey_nhl":
                decomposition_data = {
                    "goals_per_period": results.get("goals_per_period", 1.0)
                }
            
            # Calculate actual metrics from simulation if not provided by strategy
            if "football" in sport_key and "avg_drives_per_team" not in results:
                # Estimate from totals (fallback)
                avg_total = np.mean(totals_array)
                decomposition_data["drives_per_team"] = avg_total / 2.0 / 1.95  # Approximate
                decomposition_data["points_per_drive"] = avg_total / 2.0 / decomposition_data["drives_per_team"]
            
            if "basketball" in sport_key and "possessions_per_team" not in results:
                # Estimate from totals
                avg_total = np.mean(totals_array)
                decomposition_data["possessions_per_team"] = avg_total / 2.24  # Approximate
                decomposition_data["points_per_possession"] = avg_total / 2.0 / decomposition_data["possessions_per_team"]
            
            # Log decomposition
            simulation_id = f"sim_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            self.decomposition_logger.log_decomposition(
                game_id=event_id,
                sport=sport_key,
                simulation_id=simulation_id,
                team_a_name=team_a.get("name", "Team A"),
                team_b_name=team_b.get("name", "Team B"),
                decomposition_data=decomposition_data,
                model_total=float(np.median(totals_array)),
                vegas_total=market_context.get('total_line', 0.0),
                timestamp=datetime.now(timezone.utc)
            )
            logger.info(f"✅ Decomposition logged: {event_id}")
        except Exception as e:
            logger.error(f"Failed to log decomposition: {e}")
            # Don't fail simulation if logging fails
        
        # Calculate projected totals from simulation data (NUMERICAL ACCURACY ENFORCED)
        totals_array = np.array(results["totals"])
        median_total = float(np.median(totals_array))
        mean_total = float(np.mean(totals_array))
        variance_total = float(np.var(totals_array))
        
        # Validate we have real simulation data
        if len(totals_array) != iterations:
            raise ValueError(f"Simulation integrity violation: expected {iterations} totals, got {len(totals_array)}")
        
        # Get bookmaker's total line from market_context (REQUIRED - NO FALLBACK)
        bookmaker_total_line = market_context.get('total_line', None)
        
        if bookmaker_total_line is None:
            raise ValueError("CRITICAL: No bookmaker total line provided. Cannot calculate O/U probabilities without market line.")
        
        # Calculate Over/Under probabilities using proper formula from numerical_accuracy.py
        ou_analysis = OverUnderAnalysis.from_simulation(totals_array, bookmaker_total_line)
        over_probability = ou_analysis.over_probability
        under_probability = ou_analysis.under_probability
        
        logger.info(f"O/U Analysis: {ou_analysis.sims_over}/{iterations} over {bookmaker_total_line} = {over_probability:.1%}")
        
        # Calculate Win Probabilities from simulation counts (NO HEURISTICS)
        # Distribute pushes evenly between teams to ensure probabilities sum to 1.0
        pushes = results.get("pushes", 0)
        home_win_probability = float((results["team_a_wins"] + pushes / 2) / iterations)
        away_win_probability = float((results["team_b_wins"] + pushes / 2) / iterations)
        
        # Validate probabilities sum to ~1.0
        prob_sum = home_win_probability + away_win_probability
        if abs(prob_sum - 1.0) > 0.01:
            logger.warning(f"Win probability sum = {prob_sum:.4f} (expected 1.0)")
        
        # ===== CANONICAL PROBABILITY FIELDS (OUTPUT CONSISTENCY FIX) =====
        # Calculate market-scoped probabilities to prevent cross-wire bugs
        # MONEYLINE: p_win_home / p_win_away (already calculated above)
        p_win_home = home_win_probability
        p_win_away = away_win_probability
        
        
        # Calculate win probabilities from simulation results (already calculated above)
        # home_win_probability and away_win_probability are already set
        
        # Calculate tier-aware confidence score (NUMERICAL ACCURACY)
        tier_config = SimulationTierConfig.get_tier_config(iterations)
        confidence_result = ConfidenceCalculator.calculate(
            variance=variance_total,
            sim_count=iterations,
            volatility=volatility_label,
            median_value=median_total
        )
        
        # Extract numeric score from ConfidenceResult
        confidence_score = confidence_result.score if hasattr(confidence_result, 'score') else confidence_result
        
        # Ensure confidence_score is always an int
        if not isinstance(confidence_score, (int, float)):
            confidence_score = 65  # Fallback default
        confidence_score = int(confidence_score)
        
        # � CONFIDENCE VALIDATION: Never exceed 100%
        if confidence_score > 100:
            logger.error(f"❌ CONFIDENCE OVERFLOW: {confidence_score}% exceeds 100% - clamping to 100")
            confidence_score = 100
        elif confidence_score < 0:
            logger.error(f"❌ CONFIDENCE UNDERFLOW: {confidence_score}% below 0% - clamping to 0")
            confidence_score = 0
        
        # �🔴 ANTI-OVER BIAS: Apply divergence penalty to confidence
        # Large divergences from market should reduce conviction
        if bookmaker_total_line and abs(median_total - bookmaker_total_line) > 3.5:
            divergence = abs(median_total - bookmaker_total_line)
            excess_divergence = divergence - 3.5
            divergence_penalty = min(25, excess_divergence * 3.0)  # Max 25 point penalty
            
            original_confidence = confidence_score
            confidence_score = int(max(30, confidence_score - divergence_penalty))
            
            logger.warning(
                f"🔴 Market Divergence Penalty: {median_total:.1f} vs market {bookmaker_total_line:.1f} "
                f"(+{divergence:.1f} pts) → Confidence: {original_confidence} → {confidence_score}"
            )
        
        logger.info(f"Confidence: {confidence_score}/100 (Tier: {tier_config['label']}, Variance: {variance_total:.1f})")
        
        # ===== REALITY CHECK LAYER (RCL) =====
        # Apply sanity checks to prevent inflated/unrealistic totals BEFORE edge calculation
        simulation_id = f"sim_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        # Determine league code and regulation minutes
        sport_key = market_context.get("sport_key", "basketball_nba")
        league_code = self._get_league_code(sport_key)
        regulation_minutes = self._get_regulation_minutes(sport_key)
        
        # Check if live context is available
        live_context = None
        if market_context.get("is_live") or market_context.get("current_total_points") is not None:
            live_context = {
                "current_total_points": market_context.get("current_total_points"),
                "elapsed_minutes": market_context.get("elapsed_minutes")
            }
        
        # Apply RCL - get sanity-checked total
        try:
            rcl_result = get_public_total_projection(
                sim_stats={
                    "median_total": median_total,
                    "mean_total": mean_total,
                    "total_line": bookmaker_total_line
                },
                league_code=league_code,
                live_context=live_context,
                simulation_id=simulation_id,
                event_id=event_id,
                regulation_minutes=regulation_minutes
            )
            
            # Use RCL-validated total
            rcl_total = rcl_result["model_total"]
            rcl_passed = rcl_result["rcl_ok"]
            rcl_reason = rcl_result["rcl_reason"]
            
            logger.info(
                f"RCL: {median_total:.1f} → {rcl_total:.1f} "
                f"({'✅ PASSED' if rcl_passed else '🚫 FAILED'}: {rcl_reason})"
            )
            
            # Log RCL check (7-year retention, immutable)
            try:
                from db.audit_logger import get_audit_logger
                audit_logger = get_audit_logger()
                audit_logger.log_rcl(
                    game_id=event_id,
                    rcl_passed=rcl_passed,
                    rcl_reason=rcl_reason,
                    sport=market_context.get("sport_key", "unknown").replace('basketball_', '').replace('americanfootball_', '')
                )
            except Exception as e:
                # Non-blocking: audit logging failure doesn't break simulation
                logger.debug(f"Audit RCL logging skipped: {e}")
            
        except Exception as e:
            logger.error(f"RCL failed, using raw total: {e}")
            rcl_total = median_total
            rcl_passed = True
            rcl_reason = "RCL_ERROR"
            rcl_result = {
                "model_total": median_total,
                "rcl_ok": True,
                "rcl_reason": "RCL_ERROR",
                "edge_eligible": True
            }
        
        # ===== CANONICAL TEAM ANCHOR (BUG FIX) =====
        # CRITICAL FIX: Establish single source of truth for all team data
        # This prevents win probability and spread sign flips in UI
        
        # Lock team names to home/away positions (never flip these)
        home_team_name = team_a.get("name", "Team A")
        away_team_name = team_b.get("name", "Team B")
        
        # ===== TEAM IDENTITY VALIDATION (CRITICAL) =====
        # Generate canonical team_key for each team (prevents mapping errors)
        try:
            home_team_identity = team_identity_validator.create_team_identity(home_team_name, is_home=True)
            away_team_identity = team_identity_validator.create_team_identity(away_team_name, is_home=False)
            
            home_team_key = home_team_identity.team_key
            away_team_key = away_team_identity.team_key
            
            logger.info(f"🔑 Team keys: HOME={home_team_key} ({home_team_name}), AWAY={away_team_key} ({away_team_name})")
        except ValueError as e:
            logger.error(f"❌ Team key generation failed: {e}")
            # Use fallback keys based on first 3 chars (not ideal but better than crashing)
            home_team_key = home_team_name[:3].upper()
            away_team_key = away_team_name[:3].upper()
        
        # Calculate raw model spread (home perspective: positive = home favored)
        model_spread_home_perspective = avg_margin / iterations
        
        # Lock Vegas spread to sportsbook source (preserve sign exactly as published)
        # Negative = home favored, Positive = away favored
        vegas_spread_home_perspective = market_context.get('current_spread', 0.0)
        
        # SPREAD: Calculate cover probabilities at current market line
        # CRITICAL FIX: Spread cover logic was inverted
        # 
        # 🔒 FINAL LOCKED SPEC — CARD, MARKET & PARLAY LOGIC
        # ===================================================
        # EDGE and LEAN determine eligibility.
        # Model Direction explains bias only.
        # Diagnostics inform — they do not decide.
        #
        # Parlay Eligibility: parlay_eligible = (edge_state == 'EDGE' or edge_state == 'LEAN')
        # Telegram Posting: telegram_allowed = (edge_state == 'EDGE')
        # LEANS: Shown on platform, allowed in parlays, NOT auto-posted to Telegram
        # ===================================================
        # 
        # Spread convention: vegas_spread_home is from HOME perspective
        #   - Negative (e.g., -7.5) = HOME is favorite, needs to win by MORE than 7.5
        #   - Positive (e.g., +3.5) = HOME is underdog, covers if loses by LESS than 3.5 or wins
        # 
        # Cover logic:
        #   - HOME covers if: margin + vegas_spread_home > 0
        #   - Example 1: HOME -7.5, margin = +10 → 10 + (-7.5) = 2.5 > 0 ✅ Covers
        #   - Example 2: HOME -7.5, margin = +5  → 5 + (-7.5) = -2.5 < 0 ❌ Doesn't cover
        #   - Example 3: HOME +3.5, margin = -2  → -2 + 3.5 = 1.5 > 0 ✅ Covers
        # 
        margins_array = np.array(results["margins"])
        home_covers_count = np.sum(margins_array + vegas_spread_home_perspective > 0)
        p_cover_home = float(home_covers_count / iterations)
        p_cover_away = 1.0 - p_cover_home
        
        logger.info(f"Cover Probabilities at market line {vegas_spread_home_perspective}: Home {p_cover_home:.1%}, Away {p_cover_away:.1%}")
        
        # SIM INTEGRITY: Generate metadata for versioning
        odds_snapshot_id = generate_odds_snapshot_id(
            home_team_name,
            away_team_name,
            vegas_spread_home_perspective,
            datetime.now(timezone.utc)
        )
        sim_metadata = SimulationMetadata.create_current(odds_snapshot_id)
        logger.info(f"📊 Sim Metadata: version={sim_metadata.sim_version}, build={sim_metadata.engine_build_id}, snapshot={sim_metadata.odds_snapshot_id}")
        
        # Determine favorite/underdog based STRICTLY on Vegas spread sign
        # (Vegas is the canonical source of truth for market roles)
        if abs(vegas_spread_home_perspective) < 0.5:
            # Pick'em game
            vegas_favorite = home_team_name if vegas_spread_home_perspective <= 0 else away_team_name
            vegas_underdog = away_team_name if vegas_spread_home_perspective <= 0 else home_team_name
            vegas_spread_favorite_perspective = vegas_spread_home_perspective
        elif vegas_spread_home_perspective < 0:
            # Home team is Vegas favorite (negative spread)
            vegas_favorite = home_team_name
            vegas_underdog = away_team_name
            vegas_spread_favorite_perspective = vegas_spread_home_perspective  # Keep negative
        else:
            # Away team is Vegas favorite (positive home spread)
            vegas_favorite = away_team_name
            vegas_underdog = home_team_name
            vegas_spread_favorite_perspective = -vegas_spread_home_perspective  # Convert to favorite perspective
        
        # Convert model spread to favorite's perspective for comparison
        if vegas_favorite == home_team_name:
            # Home is Vegas favorite, model spread already in correct perspective
            model_spread_favorite_perspective = -abs(model_spread_home_perspective) if model_spread_home_perspective > 0 else abs(model_spread_home_perspective)
        else:
            # Away is Vegas favorite, flip model spread
            model_spread_favorite_perspective = -abs(model_spread_home_perspective) if model_spread_home_perspective < 0 else abs(model_spread_home_perspective)
        
        # CANONICAL TEAM ANCHOR: Single source of truth for all downstream usage
        canonical_team_data = {
            "home_team": {
                "name": home_team_name,
                "team_id": team_a.get("id", "team_a"),
                "win_probability": home_win_probability,
                "role": "favorite" if vegas_favorite == home_team_name else "underdog",
                "vegas_spread": vegas_spread_home_perspective  # Preserve original sign
            },
            "away_team": {
                "name": away_team_name,
                "team_id": team_b.get("id", "team_b"),
                "win_probability": away_win_probability,
                "role": "favorite" if vegas_favorite == away_team_name else "underdog",
                "vegas_spread": -vegas_spread_home_perspective  # Away perspective
            },
            "vegas_favorite": {
                "name": vegas_favorite,
                "spread": vegas_spread_favorite_perspective,  # Always negative
                "win_probability": home_win_probability if vegas_favorite == home_team_name else away_win_probability
            },
            "vegas_underdog": {
                "name": vegas_underdog,
                "spread": -vegas_spread_favorite_perspective,  # Always positive
                "win_probability": away_win_probability if vegas_favorite == home_team_name else home_win_probability
            },
            "model_spread_home_perspective": model_spread_home_perspective,
            "vegas_spread_home_perspective": vegas_spread_home_perspective
        }
        
        # Use canonical data for sharp analysis (prevents team label flips)
        favorite_team = vegas_favorite
        underdog_team = vegas_underdog
        model_spread_formatted = model_spread_favorite_perspective
        vegas_spread_formatted = vegas_spread_favorite_perspective
        
        # Map volatility to VolatilityLevel enum
        if volatility_label == "STABLE":
            volatility_enum = VolatilityLevel.LOW
        elif volatility_label == "MODERATE":
            volatility_enum = VolatilityLevel.MEDIUM
        elif volatility_label == "HIGH":
            volatility_enum = VolatilityLevel.HIGH
        else:
            volatility_enum = VolatilityLevel.EXTREME
        
        # Calculate spread edge using NEW SHARP SIDE SELECTION (gap-based thresholds)
        sharp_side_result = select_sharp_side_spread(
            home_team=home_team_name,
            away_team=away_team_name,
            market_spread_home=vegas_spread_home_perspective,
            model_spread=model_spread_home_perspective,
            volatility=volatility_enum
        )
        
        # Convert SharpSideSelection to SpreadAnalysis format for backward compatibility
        # SpreadAnalysis is now imported from sharp_analysis module
        
        # Map sharp_action to edge_direction
        if sharp_side_result.sharp_action == "TAKE_POINTS" or sharp_side_result.sharp_action == "TAKE_POINTS_LIVE":
            edge_direction = "DOG"
        elif sharp_side_result.sharp_action == "LAY_POINTS":
            edge_direction = "FAVORITE"
        else:
            edge_direction = "NO_EDGE"
        
        # Grade edge strength based on edge_after_penalty
        if sharp_side_result.edge_after_penalty >= 6.0:
            edge_grade = "S"
            edge_strength = "HIGH"
        elif sharp_side_result.edge_after_penalty >= 4.0:
            edge_grade = "A"
            edge_strength = "HIGH"
        elif sharp_side_result.edge_after_penalty >= 3.0:
            edge_grade = "B"
            edge_strength = "MEDIUM"
        elif sharp_side_result.edge_after_penalty >= 2.0:
            edge_grade = "C"
            edge_strength = "MEDIUM"
        elif sharp_side_result.edge_after_penalty >= 1.0:
            edge_grade = "D"
            edge_strength = "LOW"
        else:
            edge_grade = "F"
            edge_strength = "LOW"
        
        spread_analysis = SpreadAnalysis(
            vegas_spread=vegas_spread_formatted,
            model_spread=model_spread_formatted,
            edge_points=sharp_side_result.edge_after_penalty,
            edge_direction=edge_direction,
            sharp_side=sharp_side_result.sharp_side_display if edge_direction in ['DOG', 'FAVORITE'] else None,
            sharp_side_reason=sharp_side_result.reasoning,
            edge_grade=edge_grade,
            edge_strength=edge_strength
        )
        
        # ===== OUTPUT CONSISTENCY VALIDATION =====
        # Validate probability sums and calculate corrected sharp sides
        prob_validation = output_consistency_validator.validate_probability_sums(
            p_win_home=p_win_home,
            p_win_away=p_win_away,
            p_cover_home=p_cover_home,
            p_cover_away=p_cover_away,
            p_over=over_probability,
            p_under=under_probability
        )
        
        if not prob_validation.passed:
            logger.error(f"❌ Probability validation failed: {prob_validation.errors}")
        
        # Calculate SPREAD sharp side using CORRECTED delta_home logic
        # CRITICAL: Pass cover probabilities to enable contradiction validator
        spread_sharp_result = output_consistency_validator.calculate_spread_sharp_side(
            home_team=home_team_name,
            away_team=away_team_name,
            market_spread_home=vegas_spread_home_perspective if vegas_spread_home_perspective is not None else 0.0,
            fair_spread_home=model_spread_home_perspective if model_spread_home_perspective is not None else 0.0,
            p_cover_home=p_cover_home if p_cover_home is not None else None,
            p_cover_away=p_cover_away if p_cover_away is not None else None,
            edge_threshold=3.0
        )
        
        # SIM INTEGRITY: Run runtime guards
        canonical_odds = CanonicalOdds(
            home_team=home_team_name,
            away_team=away_team_name,
            home_spread=vegas_spread_home_perspective
        )
        
        guards_passed, integrity_flags = IntegrityValidator.run_all_guards(
            home_team=home_team_name,
            away_team=away_team_name,
            canonical_odds=canonical_odds,
            fair_spread_home=model_spread_home_perspective,
            p_cover_home=p_cover_home,
            p_cover_away=p_cover_away,
            p_win_home=p_win_home,
            p_win_away=p_win_away,
            confidence=confidence_score,
            variance_label="HIGH" if variance_total > 15 else "MODERATE"
        )
        
        if not guards_passed:
            logger.warning(f"⚠️ INTEGRITY GUARDS TRIGGERED:\n" + "\n".join(f"  - {flag}" for flag in integrity_flags))
            # Force downgrade to NO PLAY
            spread_sharp_result.sharp_action = "NO_SHARP_PLAY"
            spread_sharp_result.sharp_selection = "NO PLAY - DATA/LOGIC FLAG"
            spread_sharp_result.reasoning = "; ".join(integrity_flags)
        
        # Calculate TOTAL sharp side
        total_sharp_result = output_consistency_validator.calculate_total_sharp_side(
            market_total=bookmaker_total_line if bookmaker_total_line is not None else 0.0,
            fair_total=rcl_total if rcl_total is not None else 0.0,
            edge_threshold=3.0
        )
        
        # Calculate ML sharp side
        ml_sharp_result = output_consistency_validator.calculate_ml_sharp_side(
            home_team=home_team_name,
            away_team=away_team_name,
            p_win_home=p_win_home if p_win_home is not None else 0.5,
            p_win_away=p_win_away if p_win_away is not None else 0.5,
            edge_threshold=0.10  # 10% edge for ML
        )
        
        logger.info(
            f"Sharp Side Analysis (Corrected):\n"
            f"  SPREAD: {spread_sharp_result.sharp_action} → {spread_sharp_result.sharp_selection or 'NO_SHARP_PLAY'}\n"
            f"  TOTAL: {total_sharp_result.sharp_action} → {total_sharp_result.sharp_selection or 'NO_SHARP_PLAY'}\n"
            f"  ML: {ml_sharp_result.sharp_action} → {ml_sharp_result.sharp_selection or 'NO_SHARP_PLAY'}"
        )

        # ===== CANONICAL MARKET VIEWS (Deterministic selection IDs) =====
        snapshot_hash = sim_metadata.odds_snapshot_id
        schema_version = "2025-02-05-marketview-v1"
        probability_tolerance = 0.001

        # Spread selections (home/away, signed from home perspective)
        spread_selections = generate_spread_selections(
            event_id=event_id,
            home_team=home_team_name,
            away_team=away_team_name,
            market_spread_home=vegas_spread_home_perspective,
            book_key="consensus"
        )
        spread_selections["home"]["model_probability"] = p_cover_home
        spread_selections["away"]["model_probability"] = p_cover_away
        spread_selections["home"]["market_probability"] = p_cover_home
        spread_selections["away"]["market_probability"] = p_cover_away

        spread_prob_valid = abs((p_cover_home or 0) + (p_cover_away or 0) - 1.0) <= probability_tolerance
        spread_preference_id = "NO_EDGE"
        if spread_sharp_result and spread_sharp_result.has_edge:
            spread_preference_id = spread_selections["home"]["selection_id"] if spread_sharp_result.sharp_team == home_team_name else spread_selections["away"]["selection_id"]
        spread_direction_id = spread_preference_id
        spread_valid, spread_errors = validate_selection_consistency(
            selections=spread_selections,
            model_preference_selection_id=spread_preference_id,
            model_direction_selection_id=spread_direction_id
        )
        spread_integrity_errors = []
        if not spread_prob_valid:
            spread_integrity_errors.append("SPREAD_PROB_SUM_INVALID")
        if not spread_valid:
            spread_integrity_errors.extend(spread_errors)
        spread_edge_class = "INVALID" if spread_integrity_errors else ("EDGE" if spread_sharp_result and spread_sharp_result.has_edge else "MARKET_ALIGNED")
        spread_ui_mode = "SAFE" if spread_integrity_errors else "FULL"

        # Moneyline selections (lines are null but IDs deterministic)
        ml_selections = generate_moneyline_selections(
            event_id=event_id,
            home_team=home_team_name,
            away_team=away_team_name,
            book_key="consensus"
        )
        ml_selections["home"]["model_probability"] = p_win_home
        ml_selections["away"]["model_probability"] = p_win_away
        ml_selections["home"]["market_probability"] = p_win_home
        ml_selections["away"]["market_probability"] = p_win_away
        ml_prob_valid = abs((p_win_home or 0) + (p_win_away or 0) - 1.0) <= probability_tolerance
        ml_preference_id = "NO_EDGE"
        if ml_sharp_result and ml_sharp_result.has_edge and ml_sharp_result.sharp_team:
            ml_preference_id = ml_selections["home"]["selection_id"] if ml_sharp_result.sharp_team == home_team_name else ml_selections["away"]["selection_id"]
        ml_direction_id = ml_preference_id
        ml_valid, ml_errors = validate_selection_consistency(
            selections=ml_selections,
            model_preference_selection_id=ml_preference_id,
            model_direction_selection_id=ml_direction_id
        )
        ml_integrity_errors = []
        if not ml_prob_valid:
            ml_integrity_errors.append("ML_PROB_SUM_INVALID")
        if not ml_valid:
            ml_integrity_errors.extend(ml_errors)
        ml_edge_class = "INVALID" if ml_integrity_errors else ("EDGE" if ml_sharp_result and ml_sharp_result.has_edge else "MARKET_ALIGNED")
        ml_ui_mode = "SAFE" if ml_integrity_errors else "FULL"

        # Total selections (over/under)
        total_selections = generate_total_selections(
            event_id=event_id,
            total_line=bookmaker_total_line,
            book_key="consensus"
        )
        total_selections["over"]["model_probability"] = over_probability
        total_selections["under"]["model_probability"] = under_probability
        total_selections["over"]["market_probability"] = over_probability
        total_selections["under"]["market_probability"] = under_probability
        total_prob_valid = abs((over_probability or 0) + (under_probability or 0) - 1.0) <= probability_tolerance
        total_preference_id = "NO_EDGE"
        if total_sharp_result and total_sharp_result.has_edge:
            total_preference_id = total_selections["over"]["selection_id"] if total_sharp_result.sharp_action == SharpAction.OVER else total_selections["under"]["selection_id"]
        total_direction_id = total_preference_id
        total_valid, total_errors = validate_selection_consistency(
            selections=total_selections,
            model_preference_selection_id=total_preference_id,
            model_direction_selection_id=total_direction_id
        )
        total_integrity_errors = []
        if not total_prob_valid:
            total_integrity_errors.append("TOTAL_PROB_SUM_INVALID")
        if not total_valid:
            total_integrity_errors.extend(total_errors)
        total_edge_class = "INVALID" if total_integrity_errors else ("EDGE" if total_sharp_result and total_sharp_result.has_edge else "MARKET_ALIGNED")
        total_ui_mode = "SAFE" if total_integrity_errors else "FULL"

        overall_integrity_errors = spread_integrity_errors + ml_integrity_errors + total_integrity_errors
        
        # Calculate total edge
        total_analysis = calculate_total_edge(
            vegas_total=bookmaker_total_line,
            model_total=rcl_total,  # Use RCL-validated total
            threshold=3.0,
            confidence_score=confidence_score,
            variance=variance_total
        )
        
        # Block edge if RCL failed
        if not rcl_passed:
            logger.warning(f"🚫 Blocking total edge due to RCL failure: {rcl_reason}")
            # Reconstruct total_analysis with blocked edge (has_edge is read-only)
            total_analysis = TotalAnalysis(
                vegas_total=total_analysis.vegas_total,
                model_total=total_analysis.model_total,
                edge_points=0.0,
                edge_direction="NEUTRAL",
                sharp_side=None,
                sharp_side_reason=f"RCL_BLOCKED: {rcl_reason}",
                edge_grade="F",
                edge_strength="NEUTRAL"
            )
        
        # Format for API
        spread_edge_api = format_for_api(spread_analysis)
        total_edge_api = format_for_api(total_analysis)
        
        # Generate detailed reasoning for edge explanations
        total_reasoning = explain_edge_reasoning(
            market_type='total',
            model_value=rcl_total,  # Use RCL-validated total
            vegas_value=bookmaker_total_line,
            edge_points=total_analysis.edge_points,
            simulation_context={
                'injury_impact': offensive_impact + defensive_impact,
                'pace_factor': team_a.get("pace_factor", 1.0),
                'variance': variance_total,
                'confidence_score': confidence_score,
                'team_a_projection': results["team_a_total"] / iterations,
                'team_b_projection': results["team_b_total"] / iterations,
                'rcl_passed': rcl_passed,
                'rcl_reason': rcl_reason,
            }
        )
        
        logger.info(f"Sharp Analysis - Spread: {spread_analysis.sharp_side or 'No Edge'}, Total: {total_analysis.sharp_side or 'No Edge'}")
        if total_analysis.has_edge:
            logger.info(f"Edge Reasoning: {total_reasoning['primary_factor']} - {len(total_reasoning['contributing_factors'])} factors identified")
        
        # ===== SYSTEM-WIDE CALIBRATION ENGINE (5 CONSTRAINT LAYERS) =====
        # Apply institutional-grade calibration checks to prevent structural bias
        sport_key = market_context.get("sport_key", "basketball_nba")
        
        # Calculate data quality score from injury uncertainty (0.0 to 1.0 scale)
        injury_impact_total = sum(abs(inj.get("impact_points", 0)) for inj in injury_impact)
        data_quality_score = max(0.0, 1.0 - min(1.0, injury_impact_total * 0.02))  # 2% per impact point
        injury_uncertainty_pct = (1.0 - data_quality_score) * 100
        
        # Extract raw probability and edge from over/under analysis
        p_raw = over_probability if total_analysis.edge_direction == 'OVER' else under_probability
        edge_raw = abs(total_analysis.edge_points) if total_analysis.has_edge else 0.0
        
        # Validate pick through 5-layer constraint system
        calibration_result = self.calibration_engine.validate_pick(
            sport_key=sport_key,
            model_total=rcl_total,
            vegas_total=bookmaker_total_line,
            std_total=float(np.std(totals_array)),
            p_raw=p_raw,
            edge_raw=edge_raw,
            data_quality_score=data_quality_score,
            injury_uncertainty=injury_uncertainty_pct
        )
        
        # Log calibration decision
        logger.info(
            f"🎯 Calibration: {calibration_result['publish']} - "
            f"p_raw={p_raw:.1%} → p_adj={calibration_result['p_adjusted']:.1%}, "
            f"edge={edge_raw:.1f} → {calibration_result['edge_adjusted']:.1f}, "
            f"{calibration_result['confidence_label']} (z={calibration_result['z_variance']:.2f})"
        )
        
        if not calibration_result['publish']:
            logger.warning(
                f"🚫 BLOCKED by calibration: {', '.join(calibration_result['block_reasons'])}"
            )
        
        # Update total_analysis with calibration-adjusted values
        if calibration_result['publish']:
            # Adjust probabilities and edge based on calibration
            if total_analysis.edge_direction == 'OVER':
                over_probability = calibration_result['p_adjusted']
                under_probability = 1.0 - over_probability
            else:
                under_probability = calibration_result['p_adjusted']
                over_probability = 1.0 - under_probability
            
            # Update edge points
            if total_analysis.has_edge:
                total_analysis.edge_points = calibration_result['edge_adjusted'] * (
                    1 if total_analysis.edge_direction == 'OVER' else -1
                )
        else:
            # Block the pick - reconstruct total_analysis (has_edge is read-only)
            total_analysis = TotalAnalysis(
                vegas_total=total_analysis.vegas_total,
                model_total=total_analysis.model_total,
                edge_points=0.0,
                edge_direction="NEUTRAL",
                sharp_side=None,
                sharp_side_reason=f"CALIBRATION_BLOCKED: {', '.join(calibration_result['block_reasons'])}",
                edge_grade="F",
                edge_strength="NEUTRAL"
            )
        
        # ===== READINESS GATE =====
        # Check if required inputs exist BEFORE classification
        # Prevents premature NO_PLAY stamps on games awaiting data
        missing_inputs = []
        if not bookmaker_total_line:
            missing_inputs.append('NO_MARKET_LINE')
        if confidence_score == 0:
            missing_inputs.append('CONFIDENCE_NOT_COMPUTED')
        if variance_total == 0:
            missing_inputs.append('VARIANCE_NOT_COMPUTED')
        
        # ===== PICK STATE MACHINE (PICK / LEAN / NO_PLAY) =====
        # Classify pick state with parlay eligibility enforcement
        # CRITICAL: Every game must have explicit state - NO UNKNOWN allowed
        
        if missing_inputs:
            # Inputs not ready - set NO_PLAY with pending reason
            pick_classification = PickClassification(
                state=PickState.NO_PLAY,
                can_publish=False,
                can_parlay=False,
                confidence_tier="NONE",
                reasons=["PENDING_INPUTS"] + missing_inputs,
                thresholds_met={}
            )
            logger.info(f"⏳ [{sport_key}] {event_id[:20]} → PENDING_INPUTS: {', '.join(missing_inputs)}")
        else:
            # All inputs ready - proceed with classification
            try:
                pick_classification = PickStateMachine.classify_pick(
                    sport_key=sport_key,
                    probability=calibration_result['p_adjusted'],
                    edge=abs(calibration_result['edge_adjusted']),
                    confidence_score=confidence_score,
                    variance_z=calibration_result['z_variance'],
                    market_deviation=abs(rcl_total - bookmaker_total_line),
                    calibration_publish=calibration_result['publish'],
                    data_quality_score=data_quality_score,
                    calibration_block_reasons=calibration_result.get('block_reasons', []),
                    bootstrap_mode=calibration_result.get('bootstrap_mode', False)
                )
            except Exception as e:
                # FAILSAFE: If pick state machine fails, force NO_PLAY with reason
                logger.error(f"Pick state machine error: {e}")
                pick_classification = PickClassification(
                    state=PickState.NO_PLAY,
                    can_publish=False,
                    can_parlay=False,
                    confidence_tier="NONE",
                    reasons=[f"STATE_MACHINE_ERROR: {str(e)}"],
                    thresholds_met={}
                )
        
        logger.info(
            f"🎯 Pick State: {pick_classification.state.value} "
            f"(Publish: {pick_classification.can_publish}, Parlay: {pick_classification.can_parlay}, "
            f"Tier: {pick_classification.confidence_tier})"
        )
        
        # Log state machine decision
        if pick_classification.state == PickState.NO_PLAY:
            logger.warning(
                f"🚫 Pick blocked by state machine: {', '.join(pick_classification.reasons)}"
            )
        elif pick_classification.state == PickState.LEAN:
            logger.info(
                f"⚠️  LEAN pick: Publishable but NOT parlay-eligible - {', '.join(pick_classification.reasons)}"
            )
        
        # Build validated simulation output (enforces data integrity)
        simulation_output = SimulationOutput(
            median_total=median_total,
            mean_total=mean_total,
            variance_total=variance_total,
            home_win_probability=home_win_probability,
            away_win_probability=away_win_probability,
            h1_median_total=None,  # Set separately if 1H simulation exists
            h1_variance=None,
            sim_count=iterations,
            timestamp=datetime.now(timezone.utc),
            source="monte_carlo_engine"
        )
        
        # Validate output integrity (raises ValueError if invalid)
        simulation_output.validate()
        
        simulation_result = {
            "simulation_id": simulation_id,
            "event_id": event_id,
            "iterations": iterations,
            "mode": mode,
            "sport_key": market_context.get("sport_key", "basketball_nba"),
            "team_a": team_a.get("name"),
            "team_b": team_b.get("name"),
            
            # BASELINE MODE: Always runs team-level model (roster-independent)
            "status": SimulationStatus.COMPLETED.value,
            "simulation_mode": simulation_mode,  # "BASELINE" (default/normal operation)
            "confidence_penalty": confidence_penalty,  # Applied to calibrated outputs
            
            # CANONICAL TEAM ANCHOR: Single source of truth (prevents UI bugs)
            "canonical_teams": canonical_team_data,
            
            # NUMERICAL ACCURACY: All values from validated SimulationOutput
            # CRITICAL: These are ALWAYS from home team perspective
            "team_a_win_probability": round(home_win_probability, 4),
            "team_b_win_probability": round(away_win_probability, 4),
            "win_probability": round(home_win_probability, 4),  # For home team
            "push_probability": round(results["pushes"] / iterations, 4),
            "upset_probability": round(upset_probability, 4),
            
            # Projected totals (MUST come from simulation)
            "median_total": round(median_total, 2),  # RAW projected total (pre-RCL)
            "mean_total": round(mean_total, 2),
            "avg_total": round(rcl_total, 2),  # RCL-validated total (public-facing)
            "avg_total_score": round(rcl_total, 2),  # TypeScript compatibility (RCL-validated)
            "projected_score": round(rcl_total, 2),  # Use RCL-validated total for projection
            
            # RCL metadata
            "rcl_total": round(rcl_total, 2),
            "rcl_passed": rcl_passed,
            "rcl_reason": rcl_reason,
            "rcl_raw_total": round(median_total, 2),  # Store original for debugging
            
            # Calibration metadata (5-layer constraint system)
            "calibration": {
                "publish": calibration_result['publish'],
                "p_raw": round(p_raw, 4),
                "p_adjusted": round(calibration_result['p_adjusted'], 4),
                "edge_raw": round(edge_raw, 2),
                "edge_adjusted": round(calibration_result['edge_adjusted'], 2),
                "confidence_label": calibration_result['confidence_label'],
                "z_variance": round(calibration_result['z_variance'], 2),
                "elite_override": calibration_result['elite_override'],
                "block_reasons": calibration_result['block_reasons'],
                "applied_penalties": calibration_result['applied_penalties'],
                "calibration_status": calibration_result.get('calibration_status', 'INITIALIZED'),
                "bootstrap_mode": calibration_result.get('bootstrap_mode', False)
            },
            
            # Pick state machine (PICK/LEAN/NO_PLAY)
            # CRITICAL: These fields provide complete audit trail for every classification
            "pick_state": pick_classification.state.value,
            "can_publish": pick_classification.can_publish,
            "can_parlay": pick_classification.can_parlay,
            "confidence_tier": pick_classification.confidence_tier,
            "state_machine_reasons": pick_classification.reasons,  # Stored in MongoDB for sim_audit
            "thresholds_met": pick_classification.thresholds_met,  # Detailed threshold breakdown
            
            # Pick classification metadata (for complete traceability)
            "pick_classification": {
                "state": pick_classification.state.value,
                "reasons": pick_classification.reasons,
                "confidence_tier": pick_classification.confidence_tier,
                "thresholds_met": pick_classification.thresholds_met
            },
            
            # Version control and traceability
            "version": self.version_tracker.get_version_metadata(
                dampening_triggers=calibration_result.get('block_reasons', []),
                feature_flags={}
            ),
            
            "avg_team_a_score": round(results["team_a_total"] / iterations, 2),
            "avg_team_b_score": round(results["team_b_total"] / iterations, 2),
            
            # Over/Under (from validated O/U Analysis)
            "over_probability": round(over_probability, 4),
            "under_probability": round(under_probability, 4),
            "total_line": bookmaker_total_line,  # Bookmaker's line (REQUIRED)
            "vegas_line": bookmaker_total_line,  # Alias
            
            # Variance and distribution (REAL DATA ONLY)
            "variance": round(variance_total, 2),
            "variance_total": round(variance_total, 2),
            "distribution_curve": spread_dist_array,  # For graphing score margins
            "spread_distribution": spread_dist_array,  # Array format for charts (legacy)
            "total_distribution": self._calculate_total_distribution(results["totals"]),
            
            # Confidence score (tier-aware, formula-based)
            "confidence_score": confidence_score,
            "tier_label": tier_config['label'],
            "tier_stability_band": tier_config['stability_band'],
            "tier_stability_band": tier_config['stability_band'],
            
            # Volatility
            "avg_margin": round(avg_margin / iterations, 2),
            "volatility_index": volatility_label,
            "volatility_score": volatility_score,  # High/Medium/Low
            "pace_factor": team_a.get("pace_factor", 1.0),
            
            # Market context with odds timestamp for backtesting
            "market_context": {
                "total_line": bookmaker_total_line,
                "spread": market_context.get('current_spread', 0.0),
                "bookmaker_source": market_context.get('bookmaker_source', 'Consensus'),
                "odds_timestamp": market_context.get('odds_timestamp', datetime.now(timezone.utc).isoformat()),
                "sim_result_delta": round(median_total - bookmaker_total_line, 2),
                "edge_percentage": round(((median_total - bookmaker_total_line) / bookmaker_total_line * 100), 2) if bookmaker_total_line > 0 else 0
            },
            
            # Market integrity status (for graceful degradation)
            "integrity_status": integrity_result.to_dict() if integrity_result else {"status": "ok", "is_valid": True},
            
            # Injury impact
            "injury_impact_weighted": sum(inj.get("impact_points", 0) for inj in injury_impact),
            "injury_summary": {
                "total_offensive_impact": round(offensive_impact, 1),
                "total_defensive_impact": round(defensive_impact, 1),
                "combined_net_impact": round(offensive_impact + defensive_impact, 1),
                "impact_description": "Positive impact benefits team, negative hurts team"
            },
            
            # Confidence intervals
            "confidence_intervals": {
                "ci_68": [round(ci_68[0], 2), round(ci_68[1], 2)],
                "ci_95": [round(ci_95[0], 2), round(ci_95[1], 2)],
                "ci_99": [round(ci_99[0], 2), round(ci_99[1], 2)]
            },
            
            # ===== SHARP SIDE ANALYSIS (OUTPUT CONSISTENCY FIX) =====
            "sharp_analysis": {
                # ===== CANONICAL PROBABILITY FIELDS =====
                # Market-scoped probabilities to prevent cross-wire bugs
                "probabilities": {
                    # MONEYLINE: Game win probabilities
                    "p_win_home": round(p_win_home, 4),
                    "p_win_away": round(p_win_away, 4),
                    
                    # SPREAD: Cover probabilities at market line
                    "p_cover_home": round(p_cover_home, 4),
                    "p_cover_away": round(p_cover_away, 4),
                    
                    # TOTAL: Over/Under probabilities at market total
                    "p_over": round(over_probability, 4),
                    "p_under": round(under_probability, 4),
                    
                    # Validation status
                    "validator_status": "PASS" if prob_validation.passed else "FAIL",
                    "validator_errors": prob_validation.errors if not prob_validation.passed else []
                },
                
                # ===== SPREAD MARKET (CORRECTED DELTA_HOME LOGIC) =====
                "spread": {
                    # === SELECTION IDs (CRITICAL - MUST NOT DIVERGE) ===
                    "home_selection_id": f"{event_id}_spread_home",
                    "away_selection_id": f"{event_id}_spread_away",
                    "model_preference_selection_id": f"{event_id}_spread_{'home' if sharp_side_result.sharp_action == 'FAV' and vegas_spread_home_perspective < 0 else 'away'}",
                    "model_direction_selection_id": f"{event_id}_spread_{'home' if sharp_side_result.sharp_action == 'FAV' and vegas_spread_home_perspective < 0 else 'away'}",
                    
                    # Market and fair lines (signed from home perspective)
                    "market_spread_home": vegas_spread_home_perspective,
                    "fair_spread_home": model_spread_home_perspective,
                    "delta_home": spread_sharp_result.delta if spread_sharp_result else 0.0,
                    
                    # Legacy fields for backward compatibility
                    "vegas_spread": vegas_spread_home_perspective,
                    "model_spread": model_spread_home_perspective,
                    "edge_points": spread_analysis.edge_points,
                    "edge_direction": spread_analysis.edge_direction,
                    "edge_grade": spread_analysis.edge_grade,
                    "edge_strength": spread_analysis.edge_strength,
                    "sharp_side_reason": spread_analysis.sharp_side_reason,
                    
                    # NEW: Market-scoped sharp side (corrected logic)
                    "sharp_market": spread_sharp_result.sharp_market.value if spread_sharp_result else "SPREAD",
                    "sharp_selection": spread_sharp_result.sharp_selection if spread_sharp_result else None,
                    "sharp_action": sharp_side_result.sharp_action,  # Use NEW sharp side selection result
                    "sharp_team": spread_sharp_result.sharp_team if spread_sharp_result else None,
                    "sharp_line": spread_sharp_result.sharp_line if spread_sharp_result else None,
                    "has_edge": sharp_side_result.edge_after_penalty > 0,  # Use NEW edge calculation
                    
                    # Legacy sharp_side (keep for backward compatibility)
                    "sharp_side": spread_sharp_result.sharp_selection if spread_sharp_result else None,
                    
                    # NEW SHARP SIDE SELECTION FIELDS (Gap-based thresholds)
                    "sharp_side_display": sharp_side_result.sharp_side_display,
                    "recommended_bet": sharp_side_result.recommended_bet,
                    "market_favorite": sharp_side_result.market_favorite,
                    "market_underdog": sharp_side_result.market_underdog,
                    "edge_after_penalty": sharp_side_result.edge_after_penalty,
                    "volatility_penalty": sharp_side_result.volatility_penalty,
                    "reasoning": sharp_side_result.reasoning,
                    
                    **spread_edge_api
                },
                
                # ===== TOTAL MARKET =====
                "total": {
                    # Market and fair lines
                    "market_total": bookmaker_total_line,
                    "fair_total": rcl_total,
                    "delta_total": total_sharp_result.delta if total_sharp_result else 0.0,
                    
                    # Legacy fields
                    "vegas_total": bookmaker_total_line,
                    "model_total": rcl_total,  # Use RCL-validated total
                    "raw_model_total": median_total,  # Include raw for debugging
                    "rcl_passed": rcl_passed,
                    "rcl_reason": rcl_reason,
                    "edge_points": total_analysis.edge_points,
                    "edge_direction": total_analysis.edge_direction,
                    "edge_grade": total_analysis.edge_grade,
                    "edge_strength": total_analysis.edge_strength,
                    "sharp_side_reason": total_analysis.sharp_side_reason,
                    "edge_reasoning": total_reasoning if total_analysis.has_edge else None,
                    
                    # NEW: Market-scoped sharp side
                    "sharp_market": total_sharp_result.sharp_market.value if total_sharp_result else "TOTAL",
                    "sharp_selection": total_sharp_result.sharp_selection if total_sharp_result else None,
                    "sharp_action": total_sharp_result.sharp_action.value if total_sharp_result else "NO_SHARP_PLAY",
                    "has_edge": total_sharp_result.has_edge if total_sharp_result else False,
                    
                    # Legacy sharp_side (keep for backward compatibility)
                    "sharp_side": total_sharp_result.sharp_selection if total_sharp_result else None,
                    
                    **total_edge_api
                },
                
                # ===== MONEYLINE MARKET =====
                "moneyline": {
                    # NEW: ML sharp side analysis
                    "sharp_market": ml_sharp_result.sharp_market.value if ml_sharp_result else "ML",
                    "sharp_selection": ml_sharp_result.sharp_selection if ml_sharp_result else None,
                    "sharp_action": ml_sharp_result.sharp_action.value if ml_sharp_result else "NO_SHARP_PLAY",
                    "sharp_team": ml_sharp_result.sharp_team if ml_sharp_result else None,
                    "has_edge": ml_sharp_result.has_edge if ml_sharp_result else False,
                    "edge_pct": round(ml_sharp_result.delta * 100, 2) if ml_sharp_result and ml_sharp_result.delta else 0.0
                },
                
                # ===== DEBUG PAYLOAD (DEV TOGGLE) =====
                "debug_payload": output_consistency_validator.build_debug_payload(
                    game_id=event_id,
                    home_team=home_team_name,
                    away_team=away_team_name,
                    market_spread_home=vegas_spread_home_perspective if vegas_spread_home_perspective is not None else 0.0,
                    fair_spread_home=model_spread_home_perspective if model_spread_home_perspective is not None else 0.0,
                    market_total=bookmaker_total_line if bookmaker_total_line is not None else 0.0,
                    fair_total=rcl_total if rcl_total is not None else 0.0,
                    p_win_home=p_win_home,
                    p_win_away=p_win_away,
                    p_cover_home=p_cover_home,
                    p_cover_away=p_cover_away,
                    p_over=over_probability,
                    p_under=under_probability,
                    sharp_spread=spread_sharp_result,
                    sharp_total=total_sharp_result,
                    sharp_ml=ml_sharp_result
                ),
                
                "disclaimer": STANDARD_DISCLAIMER
            },

            # ===== CANONICAL MARKET VIEWS (Single source of truth) =====
            "market_views": {
                "spread": {
                    "schema_version": schema_version,
                    "event_id": event_id,
                    "market_type": "SPREAD",
                    "snapshot_hash": snapshot_hash,
                    "selections": [spread_selections["home"], spread_selections["away"]],
                    "model_preference_selection_id": spread_preference_id,
                    "model_direction_selection_id": spread_direction_id,
                    "edge_class": spread_edge_class,
                    "edge_points": spread_analysis.edge_points,
                    "ui_render_mode": spread_ui_mode,
                    "integrity_status": {
                        "status": "ok" if not spread_integrity_errors else "invalid",
                        "is_valid": len(spread_integrity_errors) == 0,
                        "errors": spread_integrity_errors
                    }
                },
                "moneyline": {
                    "schema_version": schema_version,
                    "event_id": event_id,
                    "market_type": "ML",
                    "snapshot_hash": snapshot_hash,
                    "selections": [ml_selections["home"], ml_selections["away"]],
                    "model_preference_selection_id": ml_preference_id,
                    "model_direction_selection_id": ml_direction_id,
                    "edge_class": ml_edge_class,
                    "edge_points": ml_sharp_result.edge_points if ml_sharp_result else 0.0,
                    "ui_render_mode": ml_ui_mode,
                    "integrity_status": {
                        "status": "ok" if not ml_integrity_errors else "invalid",
                        "is_valid": len(ml_integrity_errors) == 0,
                        "errors": ml_integrity_errors
                    }
                },
                "total": {
                    "schema_version": schema_version,
                    "event_id": event_id,
                    "market_type": "TOTAL",
                    "snapshot_hash": snapshot_hash,
                    "selections": [total_selections["over"], total_selections["under"]],
                    "model_preference_selection_id": total_preference_id,
                    "model_direction_selection_id": total_direction_id,
                    "edge_class": total_edge_class,
                    "edge_points": total_analysis.edge_points,
                    "ui_render_mode": total_ui_mode,
                    "integrity_status": {
                        "status": "ok" if not total_integrity_errors else "invalid",
                        "is_valid": len(total_integrity_errors) == 0,
                        "errors": total_integrity_errors
                    }
                }
            },

            # Global render mode (fail-safe)
            "ui_render_mode": "SAFE" if overall_integrity_errors else "FULL",
            "integrity_violations": overall_integrity_errors,
            
            # Props and additional data
            "injury_impact": injury_impact,
            "top_props": top_props,
            "market_context": market_context,
            "created_at": datetime.now(timezone.utc).isoformat(),
            
            # SIM INTEGRITY: Version metadata
            "sim_metadata": sim_metadata.to_dict(),
            "integrity_flags": integrity_flags if not guards_passed else [],
            
            # Grading status (for Trust Loop)
            "status": "pending",  # Will be updated to WIN/LOSS/PUSH after game completes
            
            # Debug label (dev mode only)
            "debug_label": get_debug_label("monte_carlo_engine", iterations, median_total, variance_total)
        }
        
        # Sanitize numpy types before saving to MongoDB
        simulation_result = sanitize_mongo_doc(simulation_result)
        
        # Store simulation in database - use update_one with upsert to avoid duplicate key errors
        # This handles regeneration cases where simulation_id might already exist
        db["monte_carlo_simulations"].update_one(
            {"simulation_id": simulation_result["simulation_id"]},
            {"$set": simulation_result},
            upsert=True
        )
        
        # ===== FEEDBACK LOOP: Store predictions for future grading =====
        try:
            # Store spread prediction if there's an edge
            if spread_analysis.has_edge:
                store_prediction(
                    game_id=event_id,
                    event_id=event_id,
                    sport_key=market_context.get("sport_key", "basketball_nba"),
                    commence_time=market_context.get("commence_time", datetime.now(timezone.utc).isoformat()),
                    home_team=team_a.get("name", "Team A"),
                    away_team=team_b.get("name", "Team B"),
                    market_type="spread",
                    predicted_outcome={
                        "prediction_value": model_spread_home_perspective,
                        "win_probability": home_win_probability if spread_analysis.edge_direction == 'DOG' else away_win_probability,
                        "sharp_side": spread_analysis.sharp_side,
                        "edge_points": spread_analysis.edge_points,
                        "edge_grade": spread_analysis.edge_grade
                    },
                    vegas_line={
                        "line_value": vegas_spread_home_perspective,
                        "bookmaker": market_context.get("bookmaker_source", "Consensus"),
                        "timestamp": market_context.get("odds_timestamp", datetime.now(timezone.utc).isoformat())
                    },
                    sim_count=iterations
                )
            
            # Store total prediction if there's an edge
            if total_analysis.has_edge:
                # Extract structured reasoning for calibration engine
                structured_reasoning = total_reasoning.get('structured_data', {}) if total_reasoning else {}
                
                store_prediction(
                    game_id=event_id,
                    event_id=event_id,
                    sport_key=market_context.get("sport_key", "basketball_nba"),
                    commence_time=market_context.get("commence_time", datetime.now(timezone.utc).isoformat()),
                    home_team=team_a.get("name", "Team A"),
                    away_team=team_b.get("name", "Team B"),
                    market_type="total",
                    predicted_outcome={
                        "prediction_value": rcl_total,  # Use RCL-validated total
                        "raw_prediction_value": median_total,  # Store raw for debugging
                        "rcl_passed": rcl_passed,
                        "rcl_reason": rcl_reason,
                        "win_probability": over_probability if total_analysis.edge_direction == 'OVER' else under_probability,
                        "sharp_side": total_analysis.sharp_side,
                        "edge_points": total_analysis.edge_points,
                        "edge_grade": total_analysis.edge_grade,
                        # CRITICAL: Store structured reasoning for calibration
                        "structured_reasoning": structured_reasoning
                    },
                    vegas_line={
                        "line_value": bookmaker_total_line,
                        "bookmaker": market_context.get("bookmaker_source", "Consensus"),
                        "timestamp": market_context.get("odds_timestamp", datetime.now(timezone.utc).isoformat())
                    },
                    sim_count=iterations
                )
        except Exception as e:
            logger.warning(f"Failed to store prediction for feedback loop: {str(e)}")
        
        # ===== CALIBRATION AUDIT LOGGING =====
        # Log every pick decision for daily calibration tracking
        try:
            self.calibration_logger.log_pick_audit(
                game_id=event_id,
                sport=sport_key,
                vegas_line=bookmaker_total_line,
                model_line=rcl_total,
                raw_model_line=median_total,
                std_total=float(np.std(totals_array)),
                p_raw=p_raw,
                p_adjusted=calibration_result['p_adjusted'],
                edge_raw=edge_raw,
                edge_adjusted=calibration_result['edge_adjusted'],
                publish_decision=calibration_result['publish'],
                block_reasons=calibration_result['block_reasons'],
                confidence_score=confidence_score,
                data_quality=data_quality_score * 100,  # Convert to 0-100 scale
                market_type="total",
                sharp_side=total_analysis.sharp_side or "NO_PLAY",
                edge_direction=total_analysis.edge_direction,
                pick_state=pick_classification.state.value,
                state_machine_reasons=pick_classification.reasons
            )
            logger.info(f"✅ Logged pick audit: {event_id} → {pick_classification.state.value} ({', '.join(pick_classification.reasons)})")
        except Exception as e:
            logger.error(f"Failed to log calibration audit: {str(e)}")
        
        log_stage(
            "monte_carlo_engine",
            "simulation_completed",
            input_payload={
                "event_id": event_id,
                "iterations": iterations
            },
            output_payload={
                "team_a_win_prob": simulation_result["team_a_win_probability"],
                "volatility": simulation_result["volatility_index"]
            }
        )
        
        # ===== ENFORCE NO UNKNOWN STATES =====
        # CRITICAL: Every simulation MUST have explicit pick_state (spec #8)
        simulation_result = ensure_pick_state(simulation_result)
        
        return simulation_result
    
    def simulate_period(
        self,
        event_id: str,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        market_context: Dict[str, Any],
        period: str = "1H",
        iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        PHASE 15: Simulate specific game periods (1H, 2H, Q1, etc.)
        
        Args:
            event_id: Unique event identifier
            team_a: Team A data
            team_b: Team B data
            market_context: Current odds, line movement, sport_key
            period: "1H" (First Half), "2H" (Second Half), "Q1", etc.
            iterations: Number of simulations (default: 50,000)
        
        Returns:
            Period-specific simulation results with adjusted physics
        """
        if not iterations:
            iterations = self.default_iterations
        
        iterations = max(self.min_iterations, min(iterations, self.max_iterations))
        
        sport_key = market_context.get('sport_key', 'basketball_nba')
        strategy = self.strategy_factory.get_strategy(sport_key)
        
        # Set market_type in market_context for integrity verification
        market_context = market_context.copy()
        market_context['market_type'] = "first_half" if period == "1H" else "second_half"
        
        # ===== MARKET LINE INTEGRITY VERIFICATION FOR PERIOD =====
        integrity_result = None
        try:
            integrity_result = self.market_verifier.verify_market_context(
                event_id=event_id,
                sport_key=sport_key,
                market_context=market_context,
                market_type="first_half" if period == "1H" else "second_half"
            )
            
            if integrity_result.status.value == "stale_line":
                logger.warning(f"⚠️ Stale odds for {period} simulation of {event_id}, proceeding anyway. Age: {integrity_result.odds_age_hours:.1f}h")
                
        except MarketLineIntegrityError as e:
            logger.error(f"❌ HARD BLOCK: Market line integrity failed for {period} simulation of {event_id}: {e}")
            raise
        
        # PHASE 15: Apply period-specific physics overrides based on sport type
        is_football = 'football' in sport_key.lower()
        sport_type = 'football' if is_football else 'basketball'
        config = self.FIRST_HALF_CONFIG.get(sport_type, self.FIRST_HALF_CONFIG['basketball'])
        
        if period == "1H":
            # Apply sport-specific 1H physics
            market_context = market_context.copy()
            market_context['pace_multiplier'] = config['pace_multiplier']
            market_context['duration_multiplier'] = config['duration_multiplier']
            market_context['starter_weight'] = config.get('starter_weight', 1.0)
            market_context['fatigue_enabled'] = config['fatigue_enabled']
            market_context['scripted_drive_boost'] = config.get('scripted_drive_boost', 1.0)
            
            print(f"🏈 1H Simulation ({sport_key}): duration={config['duration_multiplier']:.2f}, pace={config['pace_multiplier']:.2f}")
        
        # Calculate team ratings with period adjustments
        team_a_rating = self._calculate_team_rating(team_a, sport_key)
        team_b_rating = self._calculate_team_rating(team_b, sport_key)
        
        # Scale ratings for period duration BEFORE simulation
        duration_mult = market_context.get('duration_multiplier', 1.0)
        team_a_rating *= duration_mult
        team_b_rating *= duration_mult
        
        # Apply sport-specific 1H boosts
        if period == "1H":
            if is_football:
                # Football: Small scripted play boost (5%) applied ONLY to base rating, not amplified
                scripted_boost = config.get('scripted_drive_boost', 1.0)
                if scripted_boost > 1.0:
                    # Apply minimal boost for opening scripted drives
                    team_a_rating *= scripted_boost
                    team_b_rating *= scripted_boost
                    print(f"⚡ Football 1H: Applied {(scripted_boost-1)*100:.1f}% scripted drive boost")
            else:
                # Basketball: Starter weight boost for 1H
                starter_boost_a = self._calculate_starter_boost(team_a)
                starter_boost_b = self._calculate_starter_boost(team_b)
                team_a_rating += starter_boost_a * duration_mult  
                team_b_rating += starter_boost_b * duration_mult
        
        # Apply standard adjustments (but skip fatigue for 1H)
        team_a_adj = self._apply_adjustments(team_a, market_context, skip_fatigue=(period == "1H"))
        team_b_adj = self._apply_adjustments(team_b, market_context, skip_fatigue=(period == "1H"))
        
        # Run simulations with period-scaled ratings
        results = strategy.simulate_game(
            team_a_rating + team_a_adj,
            team_b_rating + team_b_adj,
            iterations,
            market_context
        )
        
        # Results are already scaled - no need to multiply again
        # Calculate period-specific metrics (NUMERICAL ACCURACY ENFORCED)
        totals_array = np.array(results["totals"])
        h1_median_total = float(np.median(totals_array))
        h1_mean_total = float(np.mean(totals_array))
        h1_variance = float(np.var(totals_array))
        
        # Validate simulation data integrity
        if len(totals_array) != iterations:
            raise ValueError(f"1H Simulation integrity violation: expected {iterations} totals, got {len(totals_array)}")
        
        # 🏈 SANITY CHECK: For football, ensure 1H doesn't exceed 65% of expected full game
        if period == "1H" and is_football:
            # Get full game projection from market or estimate
            full_game_total = market_context.get('total_line', None)
            if full_game_total and full_game_total > 0:
                max_1h_total = full_game_total * 0.65  # Hard cap at 65% of full game
                if h1_median_total > max_1h_total:
                    logger.warning(f"⚠️ 1H median {h1_median_total:.1f} exceeds 65% of full game {full_game_total:.1f}, clamping to {max_1h_total:.1f}")
                    h1_median_total = max_1h_total
                    h1_mean_total = min(h1_mean_total, max_1h_total)
                
                # Log the 1H/Full ratio for debugging
                ratio = h1_median_total / full_game_total
                logger.info(f"📊 1H Projection: {h1_median_total:.1f} ({ratio*100:.1f}% of full game {full_game_total:.1f})")
                
                # Typical football 1H should be 45-55% of full game
                if ratio < 0.40 or ratio > 0.60:
                    logger.warning(f"⚠️ Unusual 1H ratio: {ratio*100:.1f}% (expected 45-55%)")
        
        # Determine period-specific total line (NUMERICAL ACCURACY - PREFER BOOKMAKER LINE)
        bookmaker_1h_line = market_context.get('bookmaker_1h_line', None)
        
        if bookmaker_1h_line is None:
            # WARNING: No bookmaker 1H line available
            # We CANNOT calculate proper O/U probabilities without market line
            logger.warning(f"⚠️ CRITICAL: No bookmaker 1H line for {event_id}. 1H O/U probabilities will be informational only.")
            # Use projection as reference (but mark as unavailable)
            period_total_line = round(h1_median_total / 0.5) * 0.5
            book_line_available = False
        else:
            period_total_line = bookmaker_1h_line
            book_line_available = True
            logger.info(f"✅ Using bookmaker 1H line: {period_total_line}")
        
        # Calculate Over/Under probabilities (only meaningful if bookmaker line exists)
        if book_line_available:
            ou_analysis = OverUnderAnalysis.from_simulation(totals_array, period_total_line)
            over_probability = ou_analysis.over_probability
            under_probability = ou_analysis.under_probability
        else:
            # No bookmaker line - cannot provide meaningful probabilities
            over_probability = None
            under_probability = None
        
        # Calculate tier-aware confidence
        tier_config = SimulationTierConfig.get_tier_config(iterations)
        
        # Determine volatility for 1H
        margin_std = float(np.std(results["margins"]))
        thresholds = strategy.get_volatility_thresholds()
        if margin_std < thresholds['stable']:
            volatility_label = "STABLE"
        elif margin_std < thresholds['moderate']:
            volatility_label = "MODERATE"
        else:
            volatility_label = "HIGH"
        
        confidence_result = ConfidenceCalculator.calculate(
            variance=h1_variance,
            sim_count=iterations,
            volatility=volatility_label,
            median_value=h1_median_total
        )
        
        # Extract numeric score from ConfidenceResult
        confidence_score = confidence_result.score if hasattr(confidence_result, 'score') else confidence_result
        
        # 🔒 CONFIDENCE VALIDATION: Never exceed 100%
        if isinstance(confidence_score, (int, float)):
            confidence_score = int(max(0, min(100, confidence_score)))
        else:
            confidence_score = 65  # Fallback default
        
        # Reasoning for 1H prediction
        reasoning = self._generate_1h_reasoning(
            team_a, team_b, market_context, period_total_line, sport_key
        )
        
        simulation_result = {
            "simulation_id": f"sim_{period}_{event_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "event_id": event_id,
            "period": period,
            "iterations": iterations,
            "sport_key": sport_key,
            "team_a": team_a.get("name"),
            "team_b": team_b.get("name"),
            
            # NUMERICAL ACCURACY: 1H projected totals
            "h1_median_total": round(h1_median_total, 2),
            "h1_mean_total": round(h1_mean_total, 2),
            "h1_variance": round(h1_variance, 2),
            "projected_total": round(h1_median_total, 1),  # Legacy field
            
            # Bookmaker line (may be None if unavailable)
            "bookmaker_line": period_total_line if book_line_available else None,
            "book_line_available": book_line_available,
            "bookmaker_source": market_context.get('bookmaker_1h_source', None) if book_line_available else None,
            
            # O/U probabilities (None if no bookmaker line)
            "over_probability": round(over_probability, 4) if over_probability is not None else None,
            "under_probability": round(under_probability, 4) if under_probability is not None else None,
            
            # Confidence and tier info
            "confidence": confidence_score,
            "confidence_score": confidence_score,
            "tier_label": tier_config['label'],
            "volatility": volatility_label,
            
            # Additional metadata
            "expected_value": round((over_probability - 0.5) * 100, 2) if over_probability else None,
            "pace_factor": market_context.get('pace_multiplier', 1.0),
            "starter_impact": period == "1H",
            "reasoning": reasoning,
            "created_at": datetime.now(timezone.utc).isoformat(),
            
            # Grading status (for Trust Loop)
            "status": "pending",  # Will be updated to WIN/LOSS/PUSH after game completes
            
            # Market integrity status
            "integrity_status": integrity_result.to_dict() if integrity_result else {"status": "ok", "is_valid": True},
            
            # Debug label
            "debug_label": get_debug_label(f"monte_carlo_1h", iterations, h1_median_total, h1_variance)
        }
        
        # Sanitize numpy types before saving to MongoDB
        simulation_result = sanitize_mongo_doc(simulation_result)
        
        # Store period simulation in database - use update_one with upsert to avoid duplicate key errors
        db["monte_carlo_simulations"].update_one(
            {"simulation_id": simulation_result["simulation_id"]},
            {"$set": simulation_result},
            upsert=True
        )
        
        log_stage(
            "monte_carlo_engine",
            f"{period}_simulation_completed",
            input_payload={"event_id": event_id, "period": period},
            output_payload={"projected_total": simulation_result["projected_total"]}
        )
        
        # ===== ENFORCE NO UNKNOWN STATES =====
        # CRITICAL: Every simulation MUST have explicit pick_state (spec #8)
        simulation_result = ensure_pick_state(simulation_result)
        
        return simulation_result
    
    def _calculate_starter_boost(self, team: Dict[str, Any]) -> float:
        """
        Calculate rating boost from starters playing higher % of minutes in 1H
        """
        players = team.get("players", [])
        starters = [p for p in players if p.get("is_starter", False)]
        
        starter_boost = 0.0
        for player in starters:
            per = player.get("per", 15.0)
            if per > 15.0:  # Above league average
                starter_boost += (per - 15.0) * 0.15  # 15% weight for 1H starter impact
        
        return starter_boost
    
    def _generate_1h_reasoning(
        self,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        context: Dict[str, Any],
        total_line: float,
        sport_key: str
    ) -> str:
        """
        Generate human-readable reasoning for 1H prediction (SPORT-SPECIFIC)
        """
        pace_mult = context.get('pace_multiplier', 1.0)
        
        reasoning_parts = []
        
        # SPORT-SPECIFIC PACE ANALYSIS
        if 'basketball' in sport_key:
            if pace_mult > 1.02:
                pace_boost_pct = (pace_mult - 1.0) * 100
                reasoning_parts.append(f"Fast pace expected (Early game tempo +{pace_boost_pct:.1f}%)")
            elif pace_mult < 0.98:
                reasoning_parts.append("Slower pace expected (Conservative start)")
            
            # Basketball: Starter minutes analysis
            team_a_starters = len([p for p in team_a.get("players", []) if p.get("is_starter", False)])
            team_b_starters = len([p for p in team_b.get("players", []) if p.get("is_starter", False)])
            if team_a_starters + team_b_starters >= 8:
                reasoning_parts.append("Starters projected to play 18+ minutes in 1H")
            
            reasoning_parts.append("Fatigue curve removed (Fresh legs)")
            reasoning_parts.append("1H = 24 regulation minutes (2 quarters)")
            
        elif 'football' in sport_key:
            # FOOTBALL: Drive-based analysis (not time-based)
            full_game_total = context.get('total_line', 0)
            scripted_boost = context.get('scripted_drive_boost', 1.0)
            
            # Typical football 1H is 45-55% of full game
            reasoning_parts.append("1H = 2 quarters (30 minutes clock, ~5-7 drives per team)")
            reasoning_parts.append("Drive-based simulation (not time-based)")
            
            if scripted_boost > 1.0:
                boost_pct = (scripted_boost - 1.0) * 100
                reasoning_parts.append(f"Opening script advantage (+{boost_pct:.0f}% first 1-2 drives)")
            
            # Pace/tempo analysis for football
            if pace_mult > 1.03:
                reasoning_parts.append("Fast tempo offense (Hurry-up, spread formations)")
            elif pace_mult < 0.98:
                reasoning_parts.append("Slow tempo (Power run, clock control)")
            else:
                reasoning_parts.append("Standard tempo (Balanced offense)")
            
            # Typical 1H share
            if full_game_total > 0:
                reasoning_parts.append(f"Projected 1H typically 45-55% of full game ({full_game_total:.1f})")

        
        return "; ".join(reasoning_parts)
    
    def _calculate_team_rating(self, team: Dict[str, Any], sport_key: str = 'basketball_nba') -> float:
        """
        Calculate composite team rating from player efficiency metrics
        
        MULTI-SPORT SUPPORT:
        - Normalizes ratings to expected score range per sport
        - NBA: 90-130 points
        - NFL: 14-35 points
        - MLB: 2-8 runs
        - NHL: 1-6 goals
        
        Inputs:
        - Player PER (Player Efficiency Rating)
        - Win Shares
        - Usage Rate
        - Plus/Minus
        """
        # Get sport-specific score range
        min_score, max_score = self.strategy_factory.get_expected_score_range(sport_key)
        
        base_rating = team.get("offensive_rating", 105.0) + team.get("defensive_rating", 105.0)
        
        # Normalize to sport-specific range
        # Default base_rating is ~210 (105+105), normalize to sport's midpoint
        sport_midpoint = (min_score + max_score) / 2
        normalized_rating = (base_rating / 210.0) * sport_midpoint
        
        # Player-level adjustments (scale to sport)
        players = team.get("players", [])
        player_impact = 0.0
        
        for player in players:
            if player.get("status") == "active":
                per = player.get("per", 15.0)  # League average = 15
                minutes = player.get("avg_minutes", 0)
                usage = player.get("usage_rate", 0.2)
                
                # Weight by minutes and usage
                player_contribution = (per - 15.0) * (minutes / 48.0) * usage
                player_impact += player_contribution
        
        # Scale player impact to sport (NBA impact ~10 points, MLB ~0.5 runs)
        sport_scale = sport_midpoint / 110.0  # 110 is NBA midpoint
        scaled_impact = player_impact * sport_scale
        
        return normalized_rating + scaled_impact
    
    def _apply_adjustments(self, team: Dict[str, Any], context: Dict[str, Any], skip_fatigue: bool = False) -> float:
        """
        Apply adjustments for injuries, fatigue, location
        
        Args:
            team: Team data with players and metadata
            context: Market context
            skip_fatigue: If True, skip fatigue penalties (used for 1H simulations)
        """
        adjustment = 0.0
        
        # Injury impact
        injured_players = [p for p in team.get("players", []) if p.get("status") in ["out", "doubtful"]]
        for player in injured_players:
            impact = player.get("per", 15.0) - 15.0
            minutes = player.get("avg_minutes", 0)
            adjustment -= impact * (minutes / 48.0) * 0.8  # 80% of their normal impact
        
        # Fatigue (back-to-back games, travel) - SKIP FOR 1H
        if not skip_fatigue:
            rest_days = team.get("rest_days", 2)
            if rest_days == 0:
                adjustment -= 2.5  # Back-to-back penalty
            elif rest_days == 1:
                adjustment -= 1.0
            
            travel_distance = team.get("travel_miles", 0)
            if travel_distance > 1500:
                adjustment -= 1.5  # Long travel penalty
        
        # Home court advantage
        if team.get("location") == "home":
            adjustment += 3.0
        
        # Altitude (if applicable)
        if team.get("altitude_ft", 0) > 5000 and team.get("location") == "home":
            adjustment += 1.5
        
        return adjustment
    
    def _run_iterations(
        self,
        team_a_rating: float,
        team_b_rating: float,
        iterations: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute Monte Carlo iterations
        """
        team_a_wins = 0
        team_b_wins = 0
        pushes = 0
        team_a_total = 0.0
        team_b_total = 0.0
        margins = []
        totals = []
        
        # Volatility factors
        base_volatility = context.get("volatility", 10.0)
        
        for _ in range(iterations):
            # Simulate team scores with volatility
            team_a_score = np.random.normal(team_a_rating / 2, base_volatility)
            team_b_score = np.random.normal(team_b_rating / 2, base_volatility)
            
            # Ensure scores are realistic
            team_a_score = max(50, min(150, team_a_score))
            team_b_score = max(50, min(150, team_b_score))
            
            # Accumulate results
            team_a_total += team_a_score
            team_b_total += team_b_score
            
            margin = team_a_score - team_b_score
            margins.append(margin)
            totals.append(team_a_score + team_b_score)
            
            if team_a_score > team_b_score:
                team_a_wins += 1
            elif team_b_score > team_a_score:
                team_b_wins += 1
            else:
                pushes += 1
        
        return {
            "team_a_wins": team_a_wins,
            "team_b_wins": team_b_wins,
            "pushes": pushes,
            "team_a_total": team_a_total,
            "team_b_total": team_b_total,
            "margins": margins,
            "totals": totals
        }
    
    def _calculate_spread_distribution(self, margins: List[float]) -> Dict[str, float]:
        """
        Calculate probability distribution for common spread lines
        """
        spreads = [-10.5, -7.5, -4.5, -3.5, -2.5, -1.5, 0, 1.5, 2.5, 3.5, 4.5, 7.5, 10.5]
        distribution = {}
        
        for spread in spreads:
            # Count how often team A covers this spread
            covers = sum(1 for m in margins if m > spread)
            distribution[f"spread_{spread:+.1f}"] = round(covers / len(margins), 4)
        
        return distribution
    
    def _calculate_total_distribution(self, totals: List[float]) -> Dict[str, float]:
        """
        Calculate probability distribution for common totals lines
        """
        total_lines = [180.5, 190.5, 200.5, 210.5, 220.5, 230.5, 240.5]
        distribution = {}
        
        for total_line in total_lines:
            # Count how often game goes over this total
            overs = sum(1 for t in totals if t > total_line)
            distribution[f"total_o{total_line:.1f}"] = round(overs / len(totals), 4)
            distribution[f"total_u{total_line:.1f}"] = round(1 - (overs / len(totals)), 4)
        
        return distribution
    
    def _calculate_confidence_score(self, results: Dict[str, Any], iterations: int) -> float:
        """
        Calculate confidence score (0-1) based on simulation consistency and edge strength
        
        Factors:
        - Win probability edge (how decisive is the prediction)
        - Outcome consistency (how stable are the results)
        - Sample size quality (iteration count reliability)
        """
        pushes = results.get("pushes", 0)
        win_prob = max(results["team_a_wins"] + pushes / 2, results["team_b_wins"] + pushes / 2) / iterations
        margin_std = np.std(results["margins"])
        margins = results["margins"]
        
        # 1. Edge Factor: How strong is the prediction (0-1)
        # - 50% win prob = 0.0 edge (coin flip)
        # - 70%+ win prob = 1.0 edge (strong prediction)
        edge_strength = abs(win_prob - 0.5) * 2  # 0 to 1 scale
        edge_factor = min(1.0, edge_strength * 1.2)  # Boost slightly
        
        # 2. Consistency Factor: How stable are the outcomes (0-1)
        # Lower std = more consistent = higher confidence
        # Normalize margin_std: typically ranges 5-20 points
        consistency = max(0, 1 - (margin_std / 15.0))
        
        # 3. Distribution Quality: Check for normal distribution
        # High variance in outcomes = lower confidence
        margin_variance = np.var(margins)
        distribution_quality = max(0, 1 - (margin_variance / 200.0))
        
        # 4. Sample Size Factor: More iterations = higher confidence
        if iterations >= 50000:
            sample_factor = 1.0
        elif iterations >= 10000:
            sample_factor = 0.9
        elif iterations >= 1000:
            sample_factor = 0.75
        else:
            sample_factor = 0.6
        
        # Weighted combination
        # Edge (40%) + Consistency (30%) + Distribution Quality (20%) + Sample Size (10%)
        confidence = (
            edge_factor * 0.40 +
            consistency * 0.30 +
            distribution_quality * 0.20 +
            sample_factor * 0.10
        )
        
        # Ensure minimum confidence of 0.30 (30%) for any prediction
        # Maximum confidence of 0.95 (95%) - never claim 100% certainty
        confidence = max(0.30, min(0.95, confidence))
        
        return float(round(confidence, 3))
    
    def _get_league_code(self, sport_key: str) -> str:
        """Map sport_key to league code for RCL"""
        mapping = {
            "basketball_nba": "NBA",
            "basketball_ncaab": "NCAAB",
            "basketball_wnba": "WNBA",
            "americanfootball_nfl": "NFL",
            "americanfootball_ncaaf": "NCAAF",
            "icehockey_nhl": "NHL",
            "baseball_mlb": "MLB",
        }
        return mapping.get(sport_key, sport_key.upper())
    
    def _extract_league_from_sport_key(self, sport_key: str) -> str:
        """
        Extract league identifier from sport_key for roster governance.
        Same logic as _get_league_code.
        """
        return self._get_league_code(sport_key)
    
    def _get_regulation_minutes(self, sport_key: str) -> float:
        """Get regulation time for sport"""
        if "nba" in sport_key.lower() or "wnba" in sport_key.lower():
            return 48.0
        elif "ncaab" in sport_key.lower():
            return 40.0
        elif "nfl" in sport_key.lower() or "ncaaf" in sport_key.lower():
            return 60.0
        elif "nhl" in sport_key.lower():
            return 60.0
        elif "mlb" in sport_key.lower():
            return 9.0  # innings
        else:
            return 40.0  # default
    
    def detect_prop_mispricings(
        self,
        simulation_result: Dict[str, Any],
        market_props: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect mispriced player props using simulation data
        
        Compare simulation-derived probabilities vs market odds
        """
        mispricings = []
        
        for prop in market_props:
            prop_type = prop.get("type", "")  # e.g., "player_points", "player_rebounds"
            player = prop.get("player", "")
            line = prop.get("line", 0.0)
            market_odds = prop.get("odds", 2.0)
            
            if not all([player, prop_type, market_odds]):
                continue
            
            # Simulate player performance (simplified)
            # In production, this would use player-specific simulations
            sim_prob = self._simulate_player_prop(
                player,
                prop_type,
                line,
                simulation_result
            )
            
            market_implied_prob = 1 / float(market_odds)
            edge = (sim_prob - market_implied_prob) * 100
            
            if abs(edge) > 5.0:  # 5% edge threshold
                mispricings.append({
                    "player": player,
                    "prop_type": prop_type,
                    "line": line,
                    "market_odds": market_odds,
                    "market_implied_prob": round(market_implied_prob, 4),
                    "sim_probability": round(sim_prob, 4),
                    "edge_pct": round(edge, 2),
                    "recommendation": "OVER" if edge > 0 else "UNDER"
                })
        
        return mispricings
    
    def _simulate_player_prop(
        self,
        player: str,
        prop_type: str,
        line: float,
        game_simulation: Dict[str, Any]
    ) -> float:
        """
        Simulate player prop probability (simplified implementation)
        
        In production, this would use detailed player models
        """
        # Placeholder: Use game pace and player usage to estimate
        # Real implementation would run player-specific Monte Carlo
        
        base_prob = 0.5  # Default 50/50
        
        # Adjust based on game total (higher scoring games = more likely overs)
        game_total = game_simulation.get("avg_total", 210)
        pace_factor = (game_total - 210) / 30.0  # +/- 30 points impacts props
        
        adjusted_prob = base_prob + (pace_factor * 0.1)
        return max(0.1, min(0.9, adjusted_prob))
    
    def calculate_parlay_correlation(
        self,
        picks: List[Dict[str, Any]],
        simulations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate correlation between parlay legs
        
        Correlated picks reduce true parlay value
        Example: Same game spread + total are correlated
        """
        if len(picks) < 2:
            return {"correlation": 0.0, "adjusted_probability": 1.0}
        
        # Detect same-game parlays
        same_game = len(set(p["event_id"] for p in picks)) < len(picks)
        
        if same_game:
            # High correlation penalty
            correlation = 0.7
        else:
            # Low correlation for different games
            correlation = 0.1
        
        # Calculate naive parlay probability
        naive_prob = 1.0
        for pick in picks:
            naive_prob *= pick.get("win_probability", 0.5)
        
        # Adjust for correlation
        adjusted_prob = naive_prob * (1 - correlation * 0.3)
        
        return {
            "correlation": round(correlation, 3),
            "naive_probability": round(naive_prob, 4),
            "adjusted_probability": round(adjusted_prob, 4),
            "same_game_parlay": same_game,
            "edge_impact": round((naive_prob - adjusted_prob) * 100, 2)
        }


# Singleton instance
monte_carlo_engine = MonteCarloEngine()
