"""
Sharp Betting Analysis Module

Implements core logic for identifying mispricings between BeatVegas model and Vegas lines.
Sharp bettors exploit these mispricings by betting the Vegas line when it deviates from model.

CRITICAL CONCEPTS:
- Vegas Line: What the sportsbook offers (what we BET)
- Model Line: What our simulation says is fair (what we COMPARE against)
- Mispricing/Edge: The difference (what creates +EV)

We NEVER bet our model number. We ALWAYS bet the Vegas number when misaligned.
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SpreadAnalysis:
    """
    Spread mispricing analysis
    
    Example:
    - Vegas: Favorite -8, Dog +8
    - Model: Favorite should win by 4.5 points
    - Interpretation: Dog is undervalued (Vegas too harsh)
    - Sharp Side: Dog +8 (at the book)
    """
    vegas_spread: float          # e.g., -8 (favorite's perspective)
    model_spread: float          # e.g., -4.5 (our projection)
    edge_points: float           # abs difference
    edge_direction: str          # 'DOG' or 'FAVORITE'
    sharp_side: Optional[str]    # e.g., "Bulls +8" or "Lakers -8" (None if no edge)
    sharp_side_reason: str       # Explanation
    edge_grade: str              # S/A/B/C/D/F
    edge_strength: str           # HIGH/MEDIUM/LOW
    
    @property
    def has_edge(self) -> bool:
        return self.edge_direction in ['DOG', 'FAVORITE']


@dataclass
class TotalAnalysis:
    """
    Total mispricing analysis
    
    Example:
    - Vegas: 240
    - Model: 233
    - Interpretation: Vegas expects higher scoring, model expects lower
    - Sharp Side: UNDER 240 (at the book)
    """
    vegas_total: float
    model_total: float
    edge_points: float
    edge_direction: str          # 'OVER' or 'UNDER'
    sharp_side: Optional[str]    # e.g., "UNDER 240" (None if no edge)
    sharp_side_reason: str
    edge_grade: str              # S/A/B/C/D/F
    edge_strength: str           # HIGH/MEDIUM/LOW
    
    @property
    def has_edge(self) -> bool:
        return self.edge_direction in ['OVER', 'UNDER']


def calculate_spread_edge(
    vegas_spread: float,
    model_spread: float,
    favorite_team: str,
    underdog_team: str,
    threshold: float = 3.0,
    confidence_score: int = 0,
    variance: float = 999.0
) -> SpreadAnalysis:
    """
    Calculate spread mispricing and determine sharp side
    
    Args:
        vegas_spread: Spread offered by sportsbook (favorite's perspective, negative)
        model_spread: Model's projected margin (favorite's perspective, negative)
        favorite_team: Name of favorite
        underdog_team: Name of underdog
        threshold: Minimum edge to flag (default 3.0 points)
        confidence_score: Simulation confidence (0-100, default 0)
        variance: Simulation variance (default 999.0)
    
    Returns:
        SpreadAnalysis with sharp side recommendation
    
    Logic:
        - If model_spread is CLOSER than vegas_spread → Dog is undervalued
        - If model_spread is WIDER than vegas_spread → Favorite is undervalued
    
    STRICT EDGE DETECTION RULES:
        ALL 3 conditions must be true to flag sharp side:
        1. abs(edge_points) ≥ 3.0
        2. confidence_score ≥ 60
        3. variance < 300
        
        EXCEPTION: If edge ≥ 6 pts AND confidence ≥ 70, variance threshold relaxed to < 400
        (Extreme edges with strong consensus override volatility concerns)
    """
    # Calculate edge (positive = dog undervalued, negative = favorite undervalued)
    spread_mispricing = abs(vegas_spread) - abs(model_spread)
    edge_points = abs(spread_mispricing)
    
    # STRICT VALIDATION: Protect against fake edges from high volatility/low confidence
    # Rule: volatility > 300 OR confidence < 60 → NEUTRAL unless edge > 6 pts AND consensus strong
    has_exceptional_edge = edge_points >= 6.0 and confidence_score >= 70 and variance < 400
    has_standard_edge = (
        edge_points >= 3.0 and 
        confidence_score >= 60 and 
        variance < 300
    )
    has_valid_edge = has_standard_edge or has_exceptional_edge
    
    # Determine sharp side
    if spread_mispricing > threshold and has_valid_edge:
        # Dog is undervalued (Vegas too harsh on dog)
        edge_direction = 'DOG'
        vegas_dog_line = abs(vegas_spread)
        sharp_side = f"{underdog_team} +{vegas_dog_line}"
        sharp_side_reason = f"Model shows dog should get +{abs(model_spread):.1f} vs Vegas +{vegas_dog_line}. Dog undervalued by {edge_points:.1f} pts."
    elif spread_mispricing < -threshold and has_valid_edge:
        # Favorite is undervalued (Vegas not giving enough points)
        edge_direction = 'FAVORITE'
        sharp_side = f"{favorite_team} {vegas_spread}"
        sharp_side_reason = f"Model shows favorite should win by {abs(model_spread):.1f} vs Vegas {abs(vegas_spread)}. Favorite undervalued by {edge_points:.1f} pts."
    else:
        # No significant edge OR failed validation checks
        edge_direction = 'NO_EDGE'
        sharp_side = None
        if edge_points >= threshold:
            # Edge exists but failed quality checks
            if confidence_score < 60:
                sharp_side_reason = f"Model lean detected ({edge_points:.1f} pts) but confidence too low ({confidence_score}/100). No valid edge."
            elif variance >= 300:
                sharp_side_reason = f"Model lean detected ({edge_points:.1f} pts) but variance too high (σ={variance:.1f}). No valid edge."
            else:
                sharp_side_reason = f"Model lean detected ({edge_points:.1f} pts) but edge below threshold. No valid edge."
        else:
            sharp_side_reason = "No significant mispricing detected (< 3 pts)"
    
    # Grade the edge strength
    edge_grade, edge_strength = grade_edge(edge_points)
    
    return SpreadAnalysis(
        vegas_spread=vegas_spread,
        model_spread=model_spread,
        edge_points=edge_points,
        edge_direction=edge_direction,
        sharp_side=sharp_side,
        sharp_side_reason=sharp_side_reason,
        edge_grade=edge_grade,
        edge_strength=edge_strength
    )


def calculate_total_edge(
    vegas_total: float,
    model_total: float,
    threshold: float = 3.0,
    confidence_score: int = 0,
    variance: float = 999.0
) -> TotalAnalysis:
    """
    Calculate total mispricing and determine sharp side
    
    Args:
        vegas_total: Over/Under line offered by sportsbook
        model_total: Model's projected total score
        threshold: Minimum edge to flag (default 3.0 points)
        confidence_score: Simulation confidence (0-100, default 0)
        variance: Simulation variance (default 999.0)
    
    Returns:
        TotalAnalysis with sharp side recommendation
    
    Logic:
        - If model_total < vegas_total → Vegas too high → Bet UNDER
        - If model_total > vegas_total → Vegas too low → Bet OVER
    
    STRICT EDGE DETECTION RULES:
        ALL 3 conditions must be true to flag sharp side:
        1. abs(edge_points) ≥ 3.0
        2. confidence_score ≥ 60
        3. variance < 300
        
        EXCEPTION: If edge ≥ 6 pts AND confidence ≥ 70, variance threshold relaxed to < 400
        (Extreme edges with strong consensus override volatility concerns)
    """
    # Calculate edge (positive = bet under, negative = bet over)
    total_mispricing = vegas_total - model_total
    edge_points = abs(total_mispricing)
    
    # STRICT VALIDATION: Protect against fake edges from high volatility/low confidence
    # Rule: volatility > 300 OR confidence < 60 → NEUTRAL unless edge > 6 pts AND consensus strong
    has_exceptional_edge = edge_points >= 6.0 and confidence_score >= 70 and variance < 400
    has_standard_edge = (
        edge_points >= 3.0 and 
        confidence_score >= 60 and 
        variance < 300
    )
    has_valid_edge = has_standard_edge or has_exceptional_edge
    
    # Determine sharp side
    if total_mispricing > threshold and has_valid_edge:
        # Model expects lower scoring → Bet UNDER
        edge_direction = 'UNDER'
        sharp_side = f"UNDER {vegas_total}"
        sharp_side_reason = f"Model projects {model_total:.1f} vs Vegas {vegas_total}. Vegas line too high by {edge_points:.1f} pts."
    elif total_mispricing < -threshold and has_valid_edge:
        # Model expects higher scoring → Bet OVER
        edge_direction = 'OVER'
        sharp_side = f"OVER {vegas_total}"
        sharp_side_reason = f"Model projects {model_total:.1f} vs Vegas {vegas_total}. Vegas line too low by {edge_points:.1f} pts."
    else:
        # No significant edge OR failed validation checks
        edge_direction = 'NO_EDGE'
        sharp_side = None
        if edge_points >= threshold:
            # Edge exists but failed quality checks
            if confidence_score < 60:
                sharp_side_reason = f"Model lean detected ({edge_points:.1f} pts) but confidence too low ({confidence_score}/100). Market appears efficient."
            elif variance >= 300:
                sharp_side_reason = f"Model lean detected ({edge_points:.1f} pts) but variance too high (σ={variance:.1f}). Market appears efficient."
            else:
                sharp_side_reason = f"Model lean detected ({edge_points:.1f} pts) but edge below threshold. Market appears efficient."
        else:
            sharp_side_reason = "No significant mispricing detected (< 3 pts)"
    
    # Grade the edge strength
    edge_grade, edge_strength = grade_edge(edge_points)
    
    return TotalAnalysis(
        vegas_total=vegas_total,
        model_total=model_total,
        edge_points=edge_points,
        edge_direction=edge_direction,
        sharp_side=sharp_side,
        sharp_side_reason=sharp_side_reason,
        edge_grade=edge_grade,
        edge_strength=edge_strength
    )


def grade_edge(edge_points: float) -> Tuple[str, str]:
    """
    Map edge magnitude to S/A/B/C/D/F grade and strength label
    
    Grading scale (points):
    - S: 10+ points (institutional-grade mispricing)
    - A: 7-9.9 points (strong edge)
    - B: 5-6.9 points (solid edge)
    - C: 3-4.9 points (decent edge)
    - D: 2-2.9 points (marginal edge)
    - F: < 2 points (no actionable edge)
    
    Returns:
        Tuple of (grade, strength_label)
    """
    if edge_points >= 10:
        return ('S', 'INSTITUTIONAL')
    elif edge_points >= 7:
        return ('A', 'HIGH')
    elif edge_points >= 5:
        return ('B', 'HIGH')
    elif edge_points >= 3:
        return ('C', 'MEDIUM')
    elif edge_points >= 2:
        return ('D', 'LOW')
    else:
        return ('F', 'NO_EDGE')


def format_for_api(analysis) -> Dict:
    """
    Format sharp analysis for API response
    
    Returns ready-to-render fields for UI:
    - model_line_display
    - vegas_line_display
    - sharp_side_display
    - edge_points_display
    - edge_grade
    """
    if isinstance(analysis, SpreadAnalysis):
        return {
            "market_type": "spread",
            "model_line_display": f"BeatVegas Model: {analysis.model_spread}",
            "vegas_line_display": f"Vegas Line: {analysis.vegas_spread}",
            "sharp_side_display": analysis.sharp_side if analysis.has_edge and analysis.sharp_side else "No Edge",
            "edge_points_display": f"{analysis.edge_points:.1f}-point mispricing" if analysis.has_edge else "No significant edge",
            "edge_grade": analysis.edge_grade,
            "edge_strength": analysis.edge_strength,
            "sharp_side_reason": analysis.sharp_side_reason,
            "has_edge": analysis.has_edge
        }
    elif isinstance(analysis, TotalAnalysis):
        return {
            "market_type": "total",
            "model_line_display": f"BeatVegas Model: {analysis.model_total:.1f}",
            "vegas_line_display": f"Vegas Line: O/U {analysis.vegas_total}",
            "sharp_side_display": analysis.sharp_side if analysis.has_edge else "No Edge",
            "edge_points_display": f"{analysis.edge_points:.1f}-point mispricing" if analysis.has_edge else "No significant edge",
            "edge_grade": analysis.edge_grade,
            "edge_strength": analysis.edge_strength,
            "sharp_side_reason": analysis.sharp_side_reason,
            "has_edge": analysis.has_edge
        }
    else:
        raise ValueError(f"Unknown analysis type: {type(analysis)}")


# Standard disclaimer (MUST use this exact text everywhere)
STANDARD_DISCLAIMER = (
    "This is a MODEL MISPRICING — NOT a betting recommendation. "
    "BeatVegas identifies statistical deviations between our simulation output and sportsbook odds. "
    "No part of this output constitutes financial or betting advice."
)


def calculate_structured_reasoning(
    market_type: str,
    model_value: float,
    vegas_value: float,
    edge_points: float,
    simulation_context: Dict
) -> Dict:
    """
    STRUCTURED QUANTITATIVE REASONING ENGINE
    
    Returns structured data objects, NOT narrative text.
    All values COMPUTED from real simulation data, NOT manually written.
    
    Purpose: Enable backtesting, calibration (Brier/MAE/RMSE), and systematic debugging.
    
    Args:
        market_type: 'spread' or 'total'
        model_value: Model projection (computed from 100K simulations)
        vegas_value: Vegas consensus line
        edge_points: abs(model_value - vegas_value)
        simulation_context: {
            'injury_impact': float (from injury model),
            'pace_factor': float (from pace engine),
            'variance': float (from simulation),
            'confidence_score': int (simulation convergence),
            'team_a_projection': float,
            'team_b_projection': float
        }
    
    Returns:
        Structured object with ALL quantitative factors
    """
    # Extract simulation metrics
    injury_impact = simulation_context.get('injury_impact', 0.0)
    pace_factor = simulation_context.get('pace_factor', 1.0)
    variance = simulation_context.get('variance', 0.0)
    confidence_score = simulation_context.get('confidence_score', 50)
    
    # Calculate derived metrics
    delta_vs_vegas = model_value - vegas_value
    pace_adjustment_pct = (pace_factor - 1.0) * 100
    confidence_numeric = confidence_score / 100
    
    # FORMULA-BASED contrarian flag (not manually set)
    contrarian = abs(edge_points) >= 5.0
    
    # FORMULA-BASED confidence bucket
    if confidence_score >= 75 and variance < 300:
        confidence_bucket = "HIGH"
    elif confidence_score >= 60 or (confidence_score >= 50 and variance < 400):
        confidence_bucket = "MEDIUM"
    else:
        confidence_bucket = "LOW"
    
    # Identify primary factor (ranked by absolute impact)
    factor_impacts = []
    
    if abs(injury_impact) > 0.5:
        factor_impacts.append({
            "factor": "injury_impact",
            "impact_points": abs(injury_impact),
            "contribution_pct": (abs(injury_impact) / abs(delta_vs_vegas) * 100) if delta_vs_vegas != 0 else 0
        })
    
    if abs(pace_adjustment_pct) > 2.0:
        # Estimate pace impact: ~1% pace change = ~2.2 points in NBA (avg 220 total)
        pace_impact_pts = (pace_adjustment_pct / 100) * (model_value * 0.01) * 2.2
        factor_impacts.append({
            "factor": "pace_adjustment",
            "impact_points": abs(pace_impact_pts),
            "contribution_pct": (abs(pace_impact_pts) / abs(delta_vs_vegas) * 100) if delta_vs_vegas != 0 else 0
        })
    
    if variance > 300:
        # High variance doesn't directly shift mean but increases uncertainty
        factor_impacts.append({
            "factor": "high_variance",
            "impact_points": 0.0,  # Doesn't shift mean
            "contribution_pct": 0.0,
            "note": "Increases outcome uncertainty, not mean projection"
        })
    
    # Sort by impact
    factor_impacts.sort(key=lambda x: x['impact_points'], reverse=True)
    
    # Primary factor is highest impact, or baseline if none significant
    if factor_impacts and factor_impacts[0]['impact_points'] > 2.0:
        primary_factor = factor_impacts[0]['factor']
        primary_impact_pts = factor_impacts[0]['impact_points']
    else:
        primary_factor = "baseline_projection"
        primary_impact_pts = abs(delta_vs_vegas)
    
    # Calculate residual (unexplained variance)
    explained_impact = sum(f['impact_points'] for f in factor_impacts)
    residual_pts = abs(delta_vs_vegas) - explained_impact
    
    # Risk factors (quantified)
    risk_factors = []
    
    if confidence_score < 70:
        risk_factors.append({
            "risk": "low_convergence",
            "severity": "MEDIUM" if confidence_score < 60 else "LOW",
            "description": f"Only {confidence_score}% simulation convergence - less reliable projection"
        })
    
    if variance > 350:
        risk_factors.append({
            "risk": "high_variance",
            "severity": "HIGH" if variance > 450 else "MEDIUM",
            "description": f"High variance (σ={variance:.0f}) - wide outcome distribution"
        })
    
    if abs(injury_impact) < 0.1 and abs(pace_adjustment_pct) < 1.0:
        risk_factors.append({
            "risk": "missing_context",
            "severity": "MEDIUM",
            "description": "No injury/pace adjustments - model may be missing key information"
        })
    
    if residual_pts > 5.0:
        risk_factors.append({
            "risk": "unexplained_divergence",
            "severity": "HIGH",
            "description": f"{residual_pts:.1f} pts divergence unexplained by injury/pace factors"
        })
    
    # Build structured response
    return {
        # Core metrics (for backtesting)
        "injury_impact_points": round(injury_impact, 2),
        "pace_adjustment_percent": round(pace_adjustment_pct, 2),
        "variance_sigma": round(variance, 1),
        "convergence_score": round(confidence_score, 1),
        "median_sim_total": round(model_value, 1),
        "vegas_total": vegas_value,
        "delta_vs_vegas": round(delta_vs_vegas, 2),
        "contrarian": contrarian,
        "confidence_numeric": round(confidence_numeric, 2),
        "confidence_bucket": confidence_bucket,
        
        # Factor breakdown (for debugging)
        "primary_factor": primary_factor,
        "primary_factor_impact_pts": round(primary_impact_pts, 2),
        "factor_contributions": factor_impacts,
        "residual_unexplained_pts": round(residual_pts, 2),
        
        # Risk assessment (for decision quality)
        "risk_factors": risk_factors,
        "overall_risk_level": "HIGH" if len([r for r in risk_factors if r['severity'] == 'HIGH']) > 0 else "MEDIUM" if len(risk_factors) > 1 else "LOW",
        
        # Calibration metadata (for 1M engine)
        "backtest_ready": True,
        "calibration_bucket": _get_calibration_bucket(edge_points, confidence_score),
        "edge_grade_numeric": _map_grade_to_numeric(grade_edge(edge_points)[0])
    }


def _get_calibration_bucket(edge_points: float, confidence_score: int) -> str:
    """Map edge/confidence to calibration bucket for tracking accuracy"""
    if edge_points >= 10 and confidence_score >= 75:
        return "elite_high_conf"
    elif edge_points >= 7 and confidence_score >= 70:
        return "strong_high_conf"
    elif edge_points >= 5 and confidence_score >= 65:
        return "good_med_conf"
    elif edge_points >= 3:
        return "moderate_edge"
    else:
        return "marginal_edge"


def _map_grade_to_numeric(grade: str) -> int:
    """Convert S/A/B/C/D/F to numeric for quantitative analysis"""
    grade_map = {"S": 6, "A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    return grade_map.get(grade, 0)


def explain_edge_reasoning(
    market_type: str,
    model_value: float,
    vegas_value: float,
    edge_points: float,
    simulation_context: Dict
) -> Dict:
    """
    BACKWARD COMPATIBILITY WRAPPER
    
    Returns human-readable text for UI display.
    Internally calls calculate_structured_reasoning() for quant data.
    
    For NEW code: Use calculate_structured_reasoning() directly.
    This function exists only to support existing API contracts.
    """
    # Get structured data
    structured = calculate_structured_reasoning(
        market_type, model_value, vegas_value, edge_points, simulation_context
    )
    
    # Convert to narrative format for UI
    injury_impact = simulation_context.get('injury_impact', 0)
    pace_factor = simulation_context.get('pace_factor', 1.0)
    variance = simulation_context.get('variance', 0)
    confidence_score = simulation_context.get('confidence_score', 50)
    
    factors = []
    primary_factor_name = structured['primary_factor']
    
    # Build human-readable factors
    if primary_factor_name == "injury_impact":
        if injury_impact < 0:
            primary_factor = "Injury Impact"
            factors.append(f"Key injuries reducing offensive output by {abs(injury_impact):.1f} pts")
        else:
            primary_factor = "Injury Recovery"
            factors.append(f"Returning players boosting projection by {injury_impact:.1f} pts")
    elif primary_factor_name == "pace_adjustment":
        primary_factor = "Pace Factor"
        if pace_factor < 0.95:
            factors.append(f"Slower pace projection ({(1-pace_factor)*100:.1f}% below season average)")
        else:
            factors.append(f"Faster pace projection ({(pace_factor-1)*100:.1f}% above season average)")
    else:
        primary_factor = "Model Baseline Projection"
        factors.append(f"Model's team rating projections differ from market by {edge_points:.1f} pts")
    
    if variance > 300:
        factors.append(f"High variance game (σ={variance:.0f}) - wider outcome distribution")
    
    if confidence_score >= 75:
        factors.append(f"High model confidence ({confidence_score}/100) - tight simulation convergence")
    elif confidence_score < 60:
        factors.append(f"Medium confidence ({confidence_score}/100) - moderate convergence")
    
    # Build reasoning text
    divergence_direction = "UNDER" if model_value < vegas_value else "OVER"
    
    model_reasoning = (
        f"Our 100,000 Monte Carlo simulations project a median total of {model_value:.1f} points, "
        f"compared to Vegas consensus at {vegas_value:.0f}. "
        f"This {edge_points:.1f}-point divergence is driven primarily by {primary_factor.lower()}. "
    )
    
    if injury_impact < -3:
        model_reasoning += (
            "The model accounts for offensive efficiency decline from key injuries, "
            "which the market may be underweighting. "
        )
    elif abs(pace_factor - 1.0) > 0.05:
        model_reasoning += (
            "Pace projections differ from market expectations based on historical matchup data. "
        )
    elif structured['residual_unexplained_pts'] > 5:
        model_reasoning += (
            "Model's baseline team projections diverge significantly from market consensus. "
        )
    
    # Market positioning
    is_contrarian = structured['contrarian']
    market_positioning = (
        f"BeatVegas projection is {divergence_direction} Vegas consensus by {edge_points:.1f} pts. "
    )
    
    if is_contrarian:
        market_positioning += (
            "This is a significant contrarian position - our model sees value where the market doesn't."
        )
    else:
        market_positioning += (
            "This is a moderate divergence - model and market are in partial agreement."
        )
    
    return {
        "primary_factor": primary_factor,
        "contributing_factors": factors if factors else ["Statistical simulation convergence"],
        "model_reasoning": model_reasoning,
        "market_positioning": market_positioning,
        "contrarian_indicator": is_contrarian,
        "confidence_level": structured['confidence_bucket'],
        # CRITICAL: Include structured data for backend use
        "structured_data": structured
    }
