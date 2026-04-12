"""
UNIFIED DECISIONS ENDPOINT
==========================

GET /games/{league}/{game_id}/decisions

Returns all three market decisions in ONE payload.
Prevents stale mixing across tabs.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from core.market_decision import (
    GameDecisions, MarketDecision, MarketType, Classification, ReleaseStatus,
    MarketSpread, MarketTotal, Risk, Debug, Edge, Probabilities
)
from core.compute_market_decision import MarketDecisionComputer
from datetime import datetime
from db.mongo import db
from db.decision_audit_logger import get_decision_audit_logger
from db.decision_record_store import get_decision_record_store
from services.observability_service import observability_service
import uuid

router = APIRouter()


def _market_type_display(market_type: MarketType) -> str:
    mapping = {
        MarketType.SPREAD: "Spread",
        MarketType.TOTAL: "Total",
        MarketType.MONEYLINE_2WAY: "Moneyline",
        MarketType.MONEYLINE_3WAY: "3-Way Moneyline",
    }
    return mapping.get(market_type, "Spread")


def _is_blocked_status(release_status: ReleaseStatus) -> bool:
    return release_status in {
        ReleaseStatus.BLOCKED_BY_RISK,
        ReleaseStatus.BLOCKED_BY_INTEGRITY,
        ReleaseStatus.BLOCKED_MISSING_CONTEXT,
    }


def _normalized_classification(decision: MarketDecision) -> Classification:
    if _is_blocked_status(decision.release_status):
        return Classification.BLOCKED
    if decision.classification == Classification.EDGE:
        return Classification.EDGE
    if decision.classification == Classification.LEAN:
        return Classification.LEAN
    return Classification.MARKET_ALIGNED


def _format_spread_line(line: Optional[float]) -> str:
    if line is None:
        return ""
    return f"{line:+g}"


def _selection_label(decision: MarketDecision) -> Optional[str]:
    if _is_blocked_status(decision.release_status):
        return None

    if decision.market_type == MarketType.TOTAL:
        side = decision.pick.side if decision.pick else None
        total_line = decision.market.line if decision.market else None
        if side and total_line is not None:
            return f"{side.title()} {total_line:g}"
        return None

    if decision.market_type in {MarketType.SPREAD, MarketType.MONEYLINE_2WAY, MarketType.MONEYLINE_3WAY}:
        team_name = decision.pick.team_name if decision.pick and hasattr(decision.pick, "team_name") else None
        if not team_name:
            return None
        if decision.market_type == MarketType.SPREAD:
            spread_line = decision.market.line if decision.market else None
            if spread_line is None:
                return team_name
            return f"{team_name} {_format_spread_line(spread_line)}"
        return team_name

    return None


def _normalize_decision_for_api(decision: Optional[MarketDecision]) -> Optional[MarketDecision]:
    if decision is None:
        return None

    decision.classification = _normalized_classification(decision)
    decision.market_type_display = _market_type_display(decision.market_type)
    decision.selection_label = _selection_label(decision)
    decision.edge_points = decision.edge.edge_points if decision.edge else None
    decision.model_probability = decision.probabilities.model_prob if decision.probabilities else None
    decision.market_implied_probability = decision.probabilities.market_implied_prob if decision.probabilities else None
    return decision


def _normalize_game_decisions_for_api(decisions: GameDecisions) -> GameDecisions:
    decisions.spread = _normalize_decision_for_api(decisions.spread)
    decisions.moneyline = _normalize_decision_for_api(decisions.moneyline)
    decisions.total = _normalize_decision_for_api(decisions.total)
    return decisions


def create_blocked_decision(
    league: str,
    game_id: str,
    odds_event_id: str,
    market_type: MarketType,
    blocked_reason: str,
    release_status: ReleaseStatus,
    market_line: float,
    market_odds: Optional[int] = None
) -> MarketDecision:
    """
    Create a BLOCKED decision per spec Section 1.4.
    
    When BLOCKED:
    - classification = BLOCKED
    - reasons = []
    - pick = null
    - edge = null
    - probabilities = null
    - model = null
    - fair_selection = null
    - risk.blocked_reason = explicit reason
    """
    return MarketDecision(
        league=league,
        game_id=game_id,
        odds_event_id=odds_event_id,
        market_type=market_type,
        decision_id=str(uuid.uuid4()),
        selection_id=f"{game_id}_{market_type.value}_blocked",
        preferred_selection_id=f"{game_id}_{market_type.value}_blocked",
        market_selections=[],
        pick=None,
        market=MarketSpread(line=market_line, odds=market_odds) if market_type == MarketType.SPREAD else MarketTotal(line=market_line, odds=market_odds),
        model=None,
        fair_selection=None,
        probabilities=None,
        edge=None,
        classification=Classification.BLOCKED,
        market_type_display=_market_type_display(market_type),
        selection_label=None,
        edge_points=None,
        model_probability=None,
        market_implied_probability=None,
        release_status=release_status,
        di_pass=False,
        mv_pass=False,
        reasons=[],
        risk=Risk(
            volatility_flag=None,
            injury_impact=None,
            clv_forecast=None,
            blocked_reason=blocked_reason
        ),
        debug=Debug(
            inputs_hash="blocked",
            odds_timestamp=datetime.utcnow().isoformat(),
            sim_run_id="blocked",
            trace_id=str(uuid.uuid4()),
            config_profile=None,
                decision_version="1.0.0",
            computed_at=datetime.utcnow().isoformat()
        ),
        validator_failures=[]
    )

# League-aware default totals to prevent cross-league data corruption
LEAGUE_DEFAULT_TOTALS = {
    "NBA": 220.0,
    "NCAAB": 145.0,
    "NFL": 45.0,
    "NCAAF": 50.0,
    "NHL": 5.5,
    "MLB": 8.5,
}

def get_default_total(league: str) -> float:
    """Return a sensible default total for the given league."""
    return LEAGUE_DEFAULT_TOTALS.get(league.upper(), 100.0)


@router.get("/games/{league}/{game_id}/decisions")
async def get_game_decisions(league: str, game_id: str) -> GameDecisions:
    """
    SINGLE ENDPOINT for all market decisions.
    
    Returns spread, moneyline, total in one atomic payload.
    UI must fetch this ONCE and render all tabs from it.
    
    NO separate endpoints for individual markets.
    """
    
    # Fetch event from MongoDB (try both 'id' and 'event_id' fields)
    event = db["events"].find_one({"$or": [{"id": game_id}, {"event_id": game_id}]})
    if not event:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    
    # Extract odds from event FIRST (needed for BLOCKED decisions)
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        raise HTTPException(status_code=404, detail=f"No odds available for {game_id}")
    
    # Use first bookmaker with markets
    primary_book = bookmakers[0]
    markets = {m["key"]: m for m in primary_book.get("markets", [])}
    
    # Build odds_snapshot
    spread_market = markets.get("spreads", {})
    total_market = markets.get("totals", {})
    
    home_team = event.get("home_team", "")
    away_team = event.get("away_team", "")
    home_id = event.get("home_team_normalized", home_team.replace(" ", "_").lower())
    away_id = event.get("away_team_normalized", away_team.replace(" ", "_").lower())
    
    spread_outcomes = spread_market.get("outcomes", [])
    total_outcomes = total_market.get("outcomes", [])
    
    # Helper function to convert European odds to American odds
    def european_to_american(euro_odds: float) -> int:
        if euro_odds >= 2.0:
            return int((euro_odds - 1) * 100)
        else:
            return int(-100 / (euro_odds - 1))
    
    # Parse spread lines
    spread_lines = {}
    for outcome in spread_outcomes:
        team_name = outcome.get("name", "")
        is_home = team_name == home_team
        team_id = home_id if is_home else away_id
        price = outcome.get("price", 1.91)
        # Convert European odds to American
        american_odds = european_to_american(price) if isinstance(price, float) and price < 10 else int(price)
        spread_lines[team_id] = {
            "line": outcome.get("point", 0),
            "odds": american_odds
        }
    
    # Parse total lines
    over_outcome = next((o for o in total_outcomes if o.get("name") == "Over"), None)
    under_outcome = next((o for o in total_outcomes if o.get("name") == "Under"), None)
    
    # Convert total odds to American
    over_price = over_outcome.get("price", 1.91) if over_outcome else 1.91
    over_odds = european_to_american(over_price) if isinstance(over_price, float) and over_price < 10 else int(over_price)
    
    # Get league-appropriate default total
    default_total = get_default_total(league)
    
    odds_snapshot = {
        'timestamp': event.get("updated_at", datetime.utcnow().isoformat()),
        'spread_lines': spread_lines,
        'total_lines': {
            'line': over_outcome.get("point", default_total) if over_outcome else default_total,
            'odds': over_odds
        }
    }
    
    # NOW fetch simulation data (after we have market lines for BLOCKED responses)
    sim_doc = db["monte_carlo_simulations"].find_one(
        {"$or": [{"game_id": game_id}, {"event_id": game_id}]},
        sort=[("created_at", -1)]  # Latest first
    )
    if not sim_doc:
        raise HTTPException(status_code=404, detail=f"Simulation not found for {game_id}")
    
    # Extract sharp_analysis structure
    sharp_analysis = sim_doc.get("sharp_analysis", {})
    spread_data = sharp_analysis.get("spread", {})
    total_data = sharp_analysis.get("total", {})
    
    # FAIL-CLOSED: Check for real spread data (per spec Section 1.4)
    has_real_spread = spread_data.get("model_spread") is not None
    
    # FAIL-CLOSED: Check for real total data
    rcl_total_value = sim_doc.get("rcl_total") or total_data.get("model_total")
    has_real_total = rcl_total_value is not None
    
    # If missing spread data, return HTTP 200 with BLOCKED decision (NOT HTTP 503)
    if not has_real_spread:
        # Get market spread line for BLOCKED response
        market_spread_line = spread_lines.get(home_id, {}).get('line', 0)
        market_spread_odds = spread_lines.get(home_id, {}).get('odds', -110)
        
        spread_decision = create_blocked_decision(
            league=league,
            game_id=game_id,
            odds_event_id=f'odds_event_{game_id}',
            market_type=MarketType.SPREAD,
            blocked_reason="sharp_analysis.spread.model_spread",
            release_status=ReleaseStatus.BLOCKED_MISSING_CONTEXT,
            market_line=market_spread_line,
            market_odds=market_spread_odds
        )
        
        # Build minimal response with BLOCKED spread
        decisions = GameDecisions(
            spread=spread_decision,
            moneyline=None,
            total=None,
            home_team_name=home_team,
            away_team_name=away_team,
            inputs_hash="blocked",
            decision_version="1.0.0",
            computed_at=datetime.utcnow().isoformat()
        )
        return _normalize_game_decisions_for_api(decisions)
    
    # Build sim_result from MongoDB (using actual monte_carlo_simulations structure)
    # Field mappings based on actual document structure:
    # - sharp_analysis.spread.model_spread -> model spread
    # - rcl_total (top-level) or sharp_analysis.total.model_total -> fair total
    # - team_a_win_probability (top-level) -> home win prob (team_a = home)
    # - over_probability (top-level) -> over prob
    
    # Extract injury_impact - handle both numeric and list format
    injury_impact_raw = sim_doc.get("injury_impact")
    if isinstance(injury_impact_raw, (int, float)):
        injury_impact = float(injury_impact_raw)
    elif isinstance(injury_impact_raw, list):
        injury_impact = 0.0  # If it's a list, use the injury_impact_weighted field instead
    else:
        injury_impact = sim_doc.get("injury_impact_weighted") or 0.0
    
    sim_result = {
        'simulation_id': sim_doc.get("simulation_id", f"sim_{game_id}"),
        # Spread: model_spread is from sharp_analysis.spread.model_spread
        'model_spread_home_perspective': spread_data.get("model_spread", 0),
        # Market spread at simulation time (for odds alignment gate)
        'simulation_market_spread_home': spread_data.get("market_spread") or sim_doc.get("market_spread"),
        # Cover probability: team_a_win_probability (team_a = home team)
        # This is a critical field for classifications
        'home_cover_probability': sim_doc.get("team_a_win_probability") or sim_doc.get("win_probability") or 0.5,
        # Total: use rcl_total_value computed earlier (fail-closed if None)
        'rcl_total': rcl_total_value if rcl_total_value is not None else default_total,
        # Market total at simulation time
        'simulation_market_total': total_data.get("market_total") or sim_doc.get("market_total"),
        # Over probability from top-level
        'over_probability': sim_doc.get("over_probability") or 0.5,
        'volatility': sim_doc.get("volatility_label") or sim_doc.get("mode") or "MODERATE",
        'total_injury_impact': injury_impact,
        # Timestamp for freshness check
        'computed_at': sim_doc.get("created_at") or sim_doc.get("computed_at")
    }
    
    config = {
        'profile': 'balanced',
        'edge_threshold': 2.0,
        'lean_threshold': 0.5,
        'prob_threshold': 0.55,
        'min_prob_gap_for_lean': 0.01,
    }

    data_availability_state = (
        'PLAYER_DATA_UNAVAILABLE'
        if sim_doc.get('simulation_mode') == 'BASELINE'
        else 'PLAYER_DATA_AVAILABLE'
    )
    
    game_competitors = {
        home_id: home_team,
        away_id: away_team
    }
    
    # Compute all markets
    computer = MarketDecisionComputer(league, game_id, f'odds_event_{game_id}')
    
    spread_decision = computer.compute_spread(odds_snapshot, sim_result, config, game_competitors)
    
    # FAIL-CLOSED for totals: only compute if we have real fair_total data
    total_decision = None
    if has_real_total:
        total_decision = computer.compute_total(odds_snapshot, sim_result, config, game_competitors)
    # If no real total data, total_decision stays None (blocked)
    
    # Build unified response
    decisions = GameDecisions(
        spread=spread_decision,
        moneyline=None,  # TODO: implement ML compute
        total=total_decision,
        home_team_name=home_team,
        away_team_name=away_team,
        inputs_hash=spread_decision.debug.inputs_hash,
        decision_version=spread_decision.debug.decision_version,
        computed_at=datetime.utcnow().isoformat()
    )
    decisions = _normalize_game_decisions_for_api(decisions)
    
    # ═══════════════════════════════════════════════════════════════════
    # PERSIST-FIRST IDENTITY LAW (Phase 1)
    # ═══════════════════════════════════════════════════════════════════
    # Persist canonical bundle first and render response from persisted payload.
    record_store = get_decision_record_store()
    try:
        decision_record_id = record_store.persist_game_decisions(
            league=league,
            game_id=game_id,
            odds_event_id=f'odds_event_{game_id}',
            decisions=decisions,
        )
        persisted_payload = record_store.get_record_payload(decision_record_id)
        if not persisted_payload:
            raise HTTPException(
                status_code=500,
                detail="Decision record payload unavailable after persist"
            )
        decisions = GameDecisions(**persisted_payload)
        decisions.decision_record_id = decision_record_id
        decisions = _normalize_game_decisions_for_api(decisions)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Decision record persistence failed: {str(exc)}"
        )

    # ═══════════════════════════════════════════════════════════════════
    # AUDIT LOGGING (Section 14 - ENGINE LOCK Specification)
    # ═══════════════════════════════════════════════════════════════════
    # CRITICAL: Audit write MUST succeed - HTTP 500 if fails
    # This is infrastructure hardening, not engine patching
    
    audit_logger = get_decision_audit_logger()
    
    # Log spread decision
    if spread_decision:
        spread_audit_success = audit_logger.log_decision(
            event_id=game_id,
            inputs_hash=spread_decision.debug.inputs_hash,
            decision_version=str(spread_decision.debug.decision_version),
            classification=spread_decision.classification.value if spread_decision.classification else None,
            release_status=spread_decision.release_status.value,
            edge_points=spread_decision.edge.edge_points if spread_decision.edge else None,
            model_prob=spread_decision.probabilities.model_prob if spread_decision.probabilities else None,
            trace_id=spread_decision.debug.trace_id,
            engine_version="2.0.0",
            market_type="spread",
            league=league,
            git_commit_sha=spread_decision.debug.git_commit_sha,  # Section 15: Version traceability
            additional_metadata={
                "home_team": home_team,
                "away_team": away_team,
                "market_line": spread_decision.market.line if spread_decision.market else None,
                "market_odds": spread_decision.market.odds if spread_decision.market else None,
                "data_availability_state": data_availability_state,
                "simulation_mode": sim_doc.get('simulation_mode'),
            }
        )
        
        if not spread_audit_success:
            # Per Section 14: HTTP 500 if audit log write fails
            raise HTTPException(
                status_code=500,
                detail="Decision audit log write failed - institutional compliance violation"
            )

        observability_service.log_decision_audit(
            event_id=game_id,
            decision_id=spread_decision.decision_id,
            market_type="spread",
            release_status=spread_decision.release_status.value,
            classification=spread_decision.classification.value if spread_decision.classification else None,
            model_prob=spread_decision.probabilities.model_prob if spread_decision.probabilities else None,
            edge_points=spread_decision.edge.edge_points if spread_decision.edge else None,
            trace_id=spread_decision.debug.trace_id,
            snapshot_hash=spread_decision.debug.inputs_hash,
            metadata={
                "league": league,
                "decision_record_id": decisions.decision_record_id,
            },
        )
        observability_service.log_prediction_lifecycle(
            stage="DECISION_COMPUTED",
            decision_id=spread_decision.decision_id,
            event_id=game_id,
            trace_id=spread_decision.debug.trace_id,
            snapshot_hash=spread_decision.debug.inputs_hash,
            metadata={
                "market_type": "spread",
                "release_status": spread_decision.release_status.value,
                "classification": spread_decision.classification.value if spread_decision.classification else None,
            },
        )
    
    # Log total decision (if computed)
    if total_decision:
        total_audit_success = audit_logger.log_decision(
            event_id=game_id,
            inputs_hash=total_decision.debug.inputs_hash,
            decision_version=str(total_decision.debug.decision_version),
            classification=total_decision.classification.value if total_decision.classification else None,
            release_status=total_decision.release_status.value,
            edge_points=total_decision.edge.edge_points if total_decision.edge else None,
            model_prob=total_decision.probabilities.model_prob if total_decision.probabilities else None,
            trace_id=total_decision.debug.trace_id,
            engine_version="2.0.0",
            market_type="total",
            league=league,
            git_commit_sha=total_decision.debug.git_commit_sha,  # Section 15: Version traceability,
            additional_metadata={
                "home_team": home_team,
                "away_team": away_team,
                "market_line": total_decision.market.line if total_decision.market else None,
                "market_odds": total_decision.market.odds if total_decision.market else None,
                "data_availability_state": data_availability_state,
                "simulation_mode": sim_doc.get('simulation_mode'),
            }
        )
        
        if not total_audit_success:
            # Per Section 14: HTTP 500 if audit log write fails
            raise HTTPException(
                status_code=500,
                detail="Decision audit log write failed - institutional compliance violation"
            )

        observability_service.log_decision_audit(
            event_id=game_id,
            decision_id=total_decision.decision_id,
            market_type="total",
            release_status=total_decision.release_status.value,
            classification=total_decision.classification.value if total_decision.classification else None,
            model_prob=total_decision.probabilities.model_prob if total_decision.probabilities else None,
            edge_points=total_decision.edge.edge_points if total_decision.edge else None,
            trace_id=total_decision.debug.trace_id,
            snapshot_hash=total_decision.debug.inputs_hash,
            metadata={
                "league": league,
                "decision_record_id": decisions.decision_record_id,
            },
        )
        observability_service.log_prediction_lifecycle(
            stage="DECISION_COMPUTED",
            decision_id=total_decision.decision_id,
            event_id=game_id,
            trace_id=total_decision.debug.trace_id,
            snapshot_hash=total_decision.debug.inputs_hash,
            metadata={
                "market_type": "total",
                "release_status": total_decision.release_status.value,
                "classification": total_decision.classification.value if total_decision.classification else None,
            },
        )
    
    # Audit logging complete - return persisted decision bundle
    return decisions
