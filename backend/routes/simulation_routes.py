from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from bson import ObjectId
import logging

from core.monte_carlo_engine import MonteCarloEngine
from core.safety_engine import SafetyEngine, PublicCopyFormatter
from core.ncaaf_championship_regime import detect_ncaaf_context, NCAAFChampionshipRegimeController
from core.truth_mode import truth_mode_validator, BlockReason
from db.mongo import db
from middleware.auth import get_current_user_optional, get_user_tier
from services.post_game_grader import post_game_grader
from utils.mongo_helpers import sanitize_mongo_doc
from legacy_config import (
    SIMULATION_TIERS, 
    PRECISION_LABELS, 
    CONFIDENCE_INTERVALS,
    SIM_TIER_FREE
)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])
logger = logging.getLogger(__name__)


def _apply_truth_mode_to_simulation(
    simulation: Dict[str, Any],
    event: Dict[str, Any],
    event_id: str
) -> Dict[str, Any]:
    """
    Apply Truth Mode validation to simulation sharp_side picks
    Validates spread and total picks through zero-lies gates
    """
    # Validate spread pick if present
    if "spread_analysis" in simulation and simulation["spread_analysis"]:
        spread_data = simulation["spread_analysis"]
        sharp_side = spread_data.get("sharp_side")
        
        if sharp_side:
            # Validate spread pick
            validation = truth_mode_validator.validate_pick(
                event=event,
                simulation=simulation,
                bet_type="spread",
                rcl_decision=simulation.get("rcl_decision")
            )
            
            if not validation.is_valid:
                # Block spread pick
                spread_data["sharp_side"] = None
                spread_data["has_edge"] = False
                spread_data["truth_mode_blocked"] = True
                spread_data["block_reasons"] = [r.value for r in validation.block_reasons]
                spread_data["block_message"] = "Pick blocked by Truth Mode"
                print(f"🛡️ [Truth Mode] Spread pick blocked for {event_id}: {validation.block_reasons}")
            else:
                spread_data["truth_mode_validated"] = True
                spread_data["confidence_score"] = validation.confidence_score
    
    # Validate total pick if present
    if "total_analysis" in simulation and simulation["total_analysis"]:
        total_data = simulation["total_analysis"]
        sharp_side = total_data.get("sharp_side")
        
        if sharp_side:
            # Validate total pick
            validation = truth_mode_validator.validate_pick(
                event=event,
                simulation=simulation,
                bet_type="total",
                rcl_decision=simulation.get("rcl_decision")
            )
            
            if not validation.is_valid:
                # Block total pick
                total_data["sharp_side"] = None
                total_data["has_edge"] = False
                total_data["truth_mode_blocked"] = True
                total_data["block_reasons"] = [r.value for r in validation.block_reasons]
                total_data["block_message"] = "Pick blocked by Truth Mode"
                print(f"🛡️ [Truth Mode] Total pick blocked for {event_id}: {validation.block_reasons}")
            else:
                total_data["truth_mode_validated"] = True
                total_data["confidence_score"] = validation.confidence_score
    
    # Add Truth Mode metadata
    simulation["truth_mode_enforced"] = True
    simulation["truth_mode_version"] = "1.0"
    
    return simulation


def _get_user_tier_from_auth(authorization: Optional[str]) -> str:
    """
    Extract user tier from authorization token
    Returns tier name or 'free' if not authenticated
    """
    if not authorization:
        return "free"
    
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return "free"
        
        token = parts[1]
        if not token.startswith('user:'):
            return "free"
        
        user_id = token.split(':', 1)[1]
        
        # Fetch user from database
        try:
            oid = ObjectId(user_id)
            user = db["users"].find_one({"_id": oid})
            if not user:
                return "free"
            
            # Get subscription tier
            subscription = db["subscriptions"].find_one({"user_id": user_id})
            if subscription:
                tier = subscription.get("tier", "free")
                return tier.lower()
            
            # Check user document for tier
            user_tier = user.get("tier", "free")
            return user_tier.lower()
            
        except Exception:
            return "free"
    except Exception:
        return "free"


class SimulationRequest(BaseModel):
    event_id: str
    iterations: int = 10000  # FREE tier default
    mode: str = "full"  # "full" or "basic"


@router.get("/{event_id}")
async def get_simulation(
    event_id: str, 
    mode: str = "full",
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Get existing Monte Carlo simulation for an event, or auto-generate if missing
    
    🔥 TIERED COMPUTE: Simulation depth based on subscription tier
    - Free: 10,000 iterations (Standard precision) - 2 sims/day limit
    - Starter: 10,000 iterations (Standard precision)
    - Pro: 50,000 iterations (High precision)
    - Sharps Room: 100,000 iterations (Institutional precision)
    - Founder: 100,000 iterations (Institutional precision)
    
    Args:
        event_id: Event identifier
        mode: "full" for comprehensive analysis, "basic" for quick results
        current_user: Authenticated user (optional, defaults to Free tier)
    
    Returns:
        Simulation with metadata: iterations_run, precision_level, confidence_interval
    """
    try:
        # Determine user's tier and assigned iterations using centralized auth
        if current_user:
            user_tier = get_user_tier(current_user)
        else:
            user_tier = "free"
        
        assigned_iterations = SIMULATION_TIERS.get(user_tier, SIM_TIER_FREE)
        print(f"🎯 Simulation for {event_id}: tier={user_tier}, iterations={assigned_iterations}")
        precision_level = PRECISION_LABELS.get(assigned_iterations, "STANDARD")
        confidence_interval = CONFIDENCE_INTERVALS.get(assigned_iterations, 0.15)
        
        # Fetch event data (needed for Truth Mode validation)
        event = db.events.find_one({"event_id": event_id})
        if not event:
            raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
        
        # Find most recent FULL-GAME simulation for this event (exclude period simulations like 1H/2H)
        simulation = db.monte_carlo_simulations.find_one(
            {
                "event_id": event_id,
                "period": {"$exists": False}  # Exclude 1H, 2H, Q1, etc.
            },
            sort=[("created_at", -1)]
        )
        
        # CRITICAL: Apply ensure_pick_state to eliminate UNKNOWN states from legacy data
        if simulation:
            from core.monte_carlo_engine import ensure_pick_state
            simulation = ensure_pick_state(simulation)
        
        # 🔄 CACHE INVALIDATION: Check if simulation is stale
        should_regenerate = False
        is_fresh_generation = False
        if simulation:
            created_at = simulation.get("created_at")
            if created_at:
                # Convert to datetime if it's a string
                if isinstance(created_at, str):
                    try:
                        # Try ISO format first (most common)
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        # If parsing fails, treat as very old (force regeneration)
                        created_at = datetime.min.replace(tzinfo=timezone.utc)
                
                # Convert to timezone-aware datetime if needed
                if hasattr(created_at, 'tzinfo') and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                try:
                    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                except TypeError:
                    # If subtraction fails, force regeneration
                    age_hours = 999
                
                # Regenerate if:
                # 1. Simulation is older than 2 hours (market lines change)
                # 2. Cached tier doesn't match current user's tier (tier upgrade/downgrade)
                cached_tier = simulation.get("metadata", {}).get("user_tier", "free")
                cached_iterations = simulation.get("metadata", {}).get("iterations_run", 10000)
                
                if age_hours > 2:
                    print(f"♻️ Cache expired: {age_hours:.1f}h old (regenerating)")
                    should_regenerate = True
                elif cached_tier != user_tier:
                    print(f"🔄 Tier mismatch: cached={cached_tier}, current={user_tier} (regenerating)")
                    should_regenerate = True
                elif cached_iterations != assigned_iterations:
                    print(f"🔄 Iteration mismatch: cached={cached_iterations}, required={assigned_iterations} (regenerating)")
                    should_regenerate = True
                else:
                    print(f"✓ Using cached simulation: {age_hours:.1f}h old, tier={cached_tier}, iterations={cached_iterations}")
        
        if not simulation or should_regenerate:
            # Auto-generate simulation if it doesn't exist
            print(f"⚡ Auto-generating simulation for event {event_id} (Tier: {user_tier}, Iterations: {assigned_iterations})")
            
            # Initialize Monte Carlo engine
            from core.monte_carlo_engine import MonteCarloEngine
            from integrations.player_api import get_team_data_with_roster
            from integrations.odds_api import extract_market_lines
            engine = MonteCarloEngine(num_iterations=assigned_iterations)
            
            # Get team rosters with real player data
            sport_key = event.get("sport_key", "basketball_nba")
            team_a_data = get_team_data_with_roster(
                event.get("home_team", "Team A"),
                sport_key,
                is_home=True
            )
            team_b_data = get_team_data_with_roster(
                event.get("away_team", "Team B"),
                sport_key,
                is_home=False
            )
            
            # Extract real market lines from bookmakers
            market_context = extract_market_lines(event)
            
            # Detect championship/postseason context for NCAAF
            event_context = {}
            regime_adjustments = {}
            if "americanfootball_ncaaf" in sport_key or "americanfootball_college" in sport_key:
                event_context = detect_ncaaf_context(
                    event_name=f"{event.get('away_team', '')} @ {event.get('home_team', '')}",
                    **event
                )
                print(f"🏈 NCAAF Context: {event_context}")
                
                # Apply NCAAF championship regime if needed
                if event_context.get("is_championship") or event_context.get("is_postseason"):
                    regime_controller = NCAAFChampionshipRegimeController()
                    # Note: Full regime integration would require deeper engine changes
                    # For now, we flag the context for safety evaluation
                    print(f"⚠️ Championship/postseason regime detected")
            
            try:
                # Run simulation with real player rosters and real market lines
                simulation = engine.run_simulation(
                    event_id=event_id,
                    team_a=team_a_data,
                    team_b=team_b_data,
                    market_context=market_context,
                    iterations=assigned_iterations,  # TIERED COMPUTE
                    mode=mode
                )
                
                # ========== SAFETY ENGINE EVALUATION ==========
                safety_engine = SafetyEngine()
                
                # Extract key values for safety check
                model_total = simulation.get("avg_total_score") or simulation.get("avg_total") or 0
                market_total = market_context.get("total_line") or 220  # Default if missing
                variance = simulation.get("variance", 0)
                confidence = simulation.get("confidence_score", 0) / 100  # Convert to 0-1
                
                # Evaluate safety
                safety_result = safety_engine.evaluate_simulation(
                    sport_key=sport_key,
                    model_total=model_total,
                    market_total=market_total,
                    market_id=market_context.get("market_id"),
                    is_postseason=event_context.get("is_postseason", False),
                    is_championship=event_context.get("is_championship", False),
                    weather_data=event.get("weather"),
                    variance=variance,
                    confidence=confidence,
                    market_type="total"
                )
                
                print(f"🛡️ Safety Evaluation: output_mode={safety_result['output_mode']}, "
                      f"risk_score={safety_result['risk_score']:.2f}, "
                      f"divergence={safety_result['divergence_score']:.1f}pts")
                
                # Inject metadata (including safety results)
                simulation["metadata"] = {
                    "user_tier": user_tier,
                    "iterations_run": assigned_iterations,
                    "sim_count_used": assigned_iterations,  # Actual simulations executed
                    "precision_level": precision_level,
                    "confidence_interval_width": confidence_interval,
                    "variance": simulation.get("variance", 0),
                    "ci_95": simulation.get("confidence_intervals", {}).get("ci_95", [0, 0]),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "cached": False,
                    # Safety engine results
                    "output_mode": safety_result["output_mode"],
                    "risk_level": safety_result["risk_level"],
                    "risk_score": safety_result["risk_score"],
                    "eligible_for_official_pick": safety_result["eligible_for_official_pick"],
                    "divergence_score": safety_result["divergence_score"],
                    "environment_type": safety_result["environment_type"],
                }
                
                # Add safety warnings and badges to top-level
                simulation["safety_warnings"] = safety_result["warnings"]
                simulation["safety_badges"] = safety_result["badges"]
                simulation["suppression_reasons"] = safety_result["suppression_reasons"]
                
                # Mark as fresh generation
                is_fresh_generation = True
                
                print(f"✓ Simulation generated successfully for {event_id} ({assigned_iterations} iterations)")
                
            except Exception as e:
                print(f"✗ Simulation generation failed for {event_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Simulation generation failed: {str(e)}")
        
        # Convert ObjectId to string
        if "_id" in simulation:
            simulation["_id"] = str(simulation["_id"])
        
        # ========== TRUTH MODE ENFORCEMENT ==========
        # Validate sharp_side picks through Truth Mode gates
        simulation = _apply_truth_mode_to_simulation(simulation, event, event_id)
        
        # 🎯 Override metadata with current user's tier (only if not freshly generated)
        if not is_fresh_generation:
            created_at_iso = None
            if simulation.get("created_at"):
                try:
                    created_at_iso = simulation["created_at"].isoformat() if hasattr(simulation["created_at"], 'isoformat') else str(simulation["created_at"])
                except:
                    created_at_iso = None
            
            simulation["metadata"] = {
                "user_tier": user_tier,
                "iterations_run": simulation.get("iterations", assigned_iterations),
                "sim_count_used": simulation.get("iterations", assigned_iterations),
                "precision_level": precision_level,
                "confidence_interval_width": confidence_interval,
                "variance": simulation.get("variance", 0),
                "ci_95": simulation.get("confidence_intervals", {}).get("ci_95", [0, 0]),
                "cached": not should_regenerate,
                "simulation_created_at": created_at_iso
            }
        
        # Sanitize numpy types before returning
        simulation = sanitize_mongo_doc(simulation)
        
        return simulation
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Unexpected error in get_simulation for {event_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.post("/run")
async def run_simulation(
    request: SimulationRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Run a new Monte Carlo simulation for an event
    
    🔥 TIERED COMPUTE: Ignores requested iterations, enforces tier-based limits
    """
    # Fetch event data
    event = db.events.find_one({"event_id": request.event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Determine user's tier and enforce iteration limit
    user_tier = _get_user_tier_from_auth(authorization)
    assigned_iterations = SIMULATION_TIERS.get(user_tier, SIM_TIER_FREE)
    precision_level = PRECISION_LABELS.get(assigned_iterations, "STANDARD")
    
    # Initialize Monte Carlo engine
    from integrations.player_api import get_team_data_with_roster
    from integrations.odds_api import extract_market_lines
    engine = MonteCarloEngine()
    
    # Get team rosters with real player data
    sport_key = event.get("sport_key", "basketball_nba")
    team_a_data = get_team_data_with_roster(
        event.get("home_team", "Team A"),
        sport_key,
        is_home=True
    )
    team_b_data = get_team_data_with_roster(
        event.get("away_team", "Team B"),
        sport_key,
        is_home=False
    )
    
    # Extract real market lines from bookmakers
    market_context = extract_market_lines(event)
    
    try:
        # Run simulation with real player rosters and real market lines
        result = engine.run_simulation(
            event_id=request.event_id,
            team_a=team_a_data,
            team_b=team_b_data,
            market_context=market_context,
            iterations=assigned_iterations  # ENFORCED TIER LIMIT
        )
        
        # Inject metadata
        result["metadata"] = {
            "user_tier": user_tier,
            "iterations_run": assigned_iterations,
            "precision_level": precision_level,
            "requested_iterations": request.iterations,  # Show what was requested vs granted
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Log to audit trail (7-year retention, immutable)
        try:
            from db.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            audit_logger.log_simulation(
                game_id=request.event_id,
                sport=result.get('sport_key', 'unknown').replace('basketball_', '').replace('americanfootball_', ''),
                sim_count=assigned_iterations,
                vegas_line=result.get('vegas_total', 0) or result.get('vegas_spread', 0),
                model_total=result.get('median_total', 0) or result.get('predicted_spread', 0),
                stddev=result.get('std_dev', 0),
                rcl_passed=result.get('rcl_passed', True),
                edge_flagged=result.get('pick_state') in ['PICK', 'LEAN']
            )
        except Exception as e:
            # Non-blocking: audit logging failure doesn't break simulation
            logger.debug(f"Audit logging skipped: {e}")
        
        # Sanitize numpy types
        result = sanitize_mongo_doc(result)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/event/{event_id}/props")
async def get_prop_mispricings(event_id: str):
    """Get prop bet mispricings from simulations"""
    # Find prop mispricings
    mispricings = list(db.prop_mispricings.find(
        {"event_id": event_id},
        {"_id": 0}
    ).sort("edge", -1).limit(10))
    
    return {"event_id": event_id, "mispricings": mispricings}


@router.get("/{event_id}/period/{period}")
async def get_period_simulation(
    event_id: str,
    period: str,
    authorization: Optional[str] = Header(None)
):
    """
    PHASE 15: Get period-specific simulation (1H, 2H, Q1, etc.)
    
    Args:
        event_id: Event identifier
        period: Period identifier ("1H", "2H", "Q1", "Q2", "Q3", "Q4")
        authorization: Bearer token for user tier
    
    Returns:
        Period simulation results
    """
    # Validate period
    valid_periods = ["1H", "2H", "Q1", "Q2", "Q3", "Q4"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Must be one of: {', '.join(valid_periods)}"
        )
    
    # Check for cached simulation
    simulation = db.monte_carlo_simulations.find_one(
        {"event_id": event_id, "period": period},
        sort=[("created_at", -1)]
    )
    
    if simulation:
        # Convert ObjectId to string for JSON serialization
        if "_id" in simulation:
            simulation["_id"] = str(simulation["_id"])
        # Sanitize numpy types
        simulation = sanitize_mongo_doc(simulation)
        return simulation
    
    # Generate new period simulation
    try:
        # Fetch event data
        event = db.events.find_one({"event_id": event_id})
        if not event:
            raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
        
        # Initialize Monte Carlo engine
        from core.monte_carlo_engine import MonteCarloEngine
        from integrations.player_api import get_team_data_with_roster
        engine = MonteCarloEngine()
        
        # Get team rosters
        sport_key = event.get("sport_key", "basketball_nba")
        team_a_data = get_team_data_with_roster(
            event.get("home_team", "Team A"),
            sport_key,
            is_home=True
        )
        team_b_data = get_team_data_with_roster(
            event.get("away_team", "Team B"),
            sport_key,
            is_home=False
        )
        
        # Determine user's tier and assigned iterations
        user_tier = _get_user_tier_from_auth(authorization)
        assigned_iterations = SIMULATION_TIERS.get(user_tier, SIM_TIER_FREE)
        
        # Extract bookmaker 1H line if available
        from integrations.odds_api import extract_first_half_line, extract_market_lines
        bookmaker_1h_info = extract_first_half_line(event)
        market_context = extract_market_lines(event)
        market_context['sport_key'] = sport_key
        
        # Add 1H line to market context if available
        if bookmaker_1h_info.get('available'):
            market_context['bookmaker_1h_line'] = bookmaker_1h_info['first_half_total']
            market_context['bookmaker_1h_source'] = bookmaker_1h_info['book_source']
        
        # Run period-specific simulation
        simulation = engine.simulate_period(
            event_id=event_id,
            team_a=team_a_data,
            team_b=team_b_data,
            market_context=market_context,
            period=period,
            iterations=assigned_iterations  # TIERED COMPUTE
        )
        
        # Inject tier metadata
        simulation["metadata"] = {
            "user_tier": user_tier,
            "iterations_run": assigned_iterations,
            "precision_level": PRECISION_LABELS.get(assigned_iterations, "STANDARD"),
        }
        
        # Convert ObjectId to string if present
        if "_id" in simulation:
            simulation["_id"] = str(simulation["_id"])
        
        # Sanitize numpy types
        simulation = sanitize_mongo_doc(simulation)
        
        return simulation
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Period simulation failed: {str(e)}")


@router.get("/debug/{event_id}")
async def debug_simulation(event_id: str):
    """
    🔍 DEBUG ENDPOINT: Verify simulation data integrity and team perspective
    
    Use this to diagnose win probability vs spread edge mismatches
    """
    sim = db.monte_carlo_simulations.find_one({"event_id": event_id}, {"_id": 0})
    event = db.events.find_one({"event_id": event_id}, {"_id": 0})
    
    if not sim:
        raise HTTPException(404, "Simulation not found")
    if not event:
        raise HTTPException(404, "Event not found")
    
    # Extract key data
    bookmakers = event.get("bookmakers", [{}])
    first_book = bookmakers[0] if bookmakers else {}
    
    team_a_wins = sim.get("team_a_win_probability", 0)
    team_b_wins = sim.get("team_b_win_probability", 0)
    prob_sum = team_a_wins + team_b_wins
    
    # Calculate expected win prob from spread
    import math
    avg_margin = sim.get("avg_margin", 0)
    expected_win_from_spread = 1 / (1 + math.exp(-avg_margin / 12)) if avg_margin else 0.5
    
    return {
        "event_info": {
            "event_id": event_id,
            "home_team": event.get("home_team"),
            "away_team": event.get("away_team"),
            "sport": event.get("sport_key"),
            "commence_time": event.get("commence_time")
        },
        "market_odds": {
            "home_odds": first_book.get("home"),
            "away_odds": first_book.get("away"),
            "bookmaker": first_book.get("key")
        },
        "simulation_results": {
            "team_a": sim.get("team_a"),
            "team_b": sim.get("team_b"),
            "team_a_win_probability": team_a_wins,
            "team_b_win_probability": team_b_wins,
            "win_probability": sim.get("win_probability"),
            "iterations": sim.get("iterations"),
            "avg_margin": avg_margin,
            "median_total": sim.get("median_total")
        },
        "integrity_checks": {
            "prob_sum": round(prob_sum, 4),
            "expected_sum": 1.0,
            "prob_sum_valid": abs(prob_sum - 1.0) < 0.01,
            "expected_win_from_spread": round(expected_win_from_spread, 4),
            "actual_win_prob": team_a_wins,
            "spread_prob_deviation": abs(team_a_wins - expected_win_from_spread),
            "alignment_status": "GOOD" if abs(team_a_wins - expected_win_from_spread) < 0.15 else "⚠️ MISMATCH"
        },
        "diagnosis": {
            "team_a_is_home": sim.get("team_a") == event.get("home_team"),
            "home_win_prob": team_a_wins if sim.get("team_a") == event.get("home_team") else team_b_wins,
            "away_win_prob": team_b_wins if sim.get("team_a") == event.get("home_team") else team_a_wins,
            "spread_favors": "Home" if avg_margin > 0 else "Away",
            "win_prob_favors": "Team A" if team_a_wins > 0.5 else "Team B"
        }
    }


@router.get("/grading/stats")
async def get_grading_stats(
    days_back: int = 7,
    sport_key: Optional[str] = None
):
    """
    Get post-game grading statistics
    
    Returns:
        - Total games graded
        - Model fault breakdown (normal variance, medium miss, big miss, RCL blocked)
        - Average deltas
        - Calibration weight distribution
    """
    try:
        stats = post_game_grader.get_grading_stats(days_back=days_back, sport_key=sport_key)
        return {
            "success": True,
            "data": stats,
            "days_back": days_back,
            "sport_key": sport_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve grading stats: {str(e)}")


@router.post("/grading/run")
async def run_grading(hours_back: int = 48):
    """
    Manually trigger grading for finished games
    
    Args:
        hours_back: How many hours back to look for finished games (default: 48)
    """
    try:
        summary = post_game_grader.grade_all_finished_games(hours_back=hours_back)
        return {
            "success": True,
            "summary": summary,
            "message": f"Graded {summary['graded']} games, skipped {summary['skipped']}, errors: {summary['errors']}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run grading: {str(e)}")
