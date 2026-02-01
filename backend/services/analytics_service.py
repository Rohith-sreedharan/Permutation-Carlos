"""
Analytics Service - Strict Mathematical EV & Edge Calculations
===============================================================

ZERO TOLERANCE for heuristics. All calculations must use proper formulas
from numerical_accuracy.py and monte_carlo_engine.py outputs.

Reference: BEATVEGAS – NUMERICAL ACCURACY & SIMULATION SPEC Section 3
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
from core.numerical_accuracy import (
    ExpectedValue,
    ClosingLineValue,
    EdgeValidator,
    SimulationTierConfig
)
from core.universal_tier_classifier import (
    SelectionInput,
    classify,
    build_classification_result,
    Tier,
    market_prob_fair as calc_market_prob_fair
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Strict analytics calculations - no shortcuts, no heuristics
    
    All EV, edge, and confidence metrics must be mathematically derived
    from Monte Carlo simulation outputs.
    """
    
    @staticmethod
    def calculate_expected_value(
        model_probability: float,
        american_odds: int,
        sim_count: int = 10000
    ) -> Dict[str, Any]:
        """
        Calculate Expected Value using PROPER formula (not heuristics)
        
        Formula from Spec Section 3:
        1. Convert American odds to implied probability
        2. Use simulation probability p_model
        3. EV = p_model * (decimal_odds - 1) - (1 - p_model)
        4. Edge = p_model - implied_p
        
        Args:
            model_probability: From Monte Carlo (e.g., 0.58 = 58%)
            american_odds: Bookmaker odds (e.g., -110, +150)
            sim_count: Number of simulations run (for EV+ validation)
            
        Returns:
            {
                'ev_per_dollar': 0.074,
                'edge_percentage': 0.056,  # 5.6%
                'model_probability': 0.58,
                'implied_probability': 0.524,
                'decimal_odds': 1.909,
                'is_ev_plus': True,  # Only if edge >= 3% AND tier >= 25K
                'display_edge': '+5.6%',
                'recommendation': 'EDGE' | 'LEAN' | 'NEUTRAL'
            }
        """
        # Use strict ExpectedValue calculator
        ev = ExpectedValue.calculate(
            model_prob=model_probability,
            american_odds=american_odds
        )
        
        # EV+ classification (strict requirements)
        is_ev_plus = ev.is_ev_plus(
            min_edge=0.03,  # 3 percentage points
            min_sim_tier=25000,
            current_tier=sim_count
        )
        
        # Format display
        edge_display = f"+{ev.edge_percentage * 100:.1f}%" if ev.edge_percentage > 0 else f"{ev.edge_percentage * 100:.1f}%"
        
        return {
            'ev_per_dollar': ev.ev_per_dollar,
            'edge_percentage': ev.edge_percentage,
            'model_probability': ev.model_probability,
            'implied_probability': ev.implied_probability,
            'decimal_odds': ev.decimal_odds,
            'is_ev_plus': is_ev_plus,
            'display_edge': edge_display,
            'american_odds': american_odds
        }
    
    @staticmethod
    def classify_bet_strength(
        model_prob: float,
        implied_prob: float,
        confidence: int,
        volatility: str,
        sim_count: int,
        injury_impact: float = 0.0,
        american_odds: int = -110,
        opp_american_odds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Classify bet as EDGE / LEAN / MARKET_ALIGNED / BLOCKED using Universal Tier Classifier.
        
        Uses ONLY probability edge + EV + data integrity (per Universal EDGE/LEAN spec).
        CLV, volatility, line movement, market efficiency CANNOT affect tier.
        
        Thresholds (hard-coded):
        - EDGE: prob_edge >= 5.0% AND ev >= 0.0%
        - LEAN: prob_edge >= 2.5% AND ev >= -0.5%
        - MARKET_ALIGNED: does not meet LEAN/EDGE thresholds
        - BLOCKED: fails data integrity (sims < 20K, invalid prob, stale data)
        
        Returns:
            {
                'classification': 'EDGE' | 'LEAN' | 'MARKET_ALIGNED' | 'BLOCKED',
                'prob_edge': 0.056,
                'ev': 0.045,
                'p_model': 0.58,
                'p_market_fair': 0.524,
                'recommendation': 'Strong Edge - 5.6% probability advantage',
                'badge_color': 'green' | 'yellow' | 'gray' | 'red',
                
                # Legacy conditions (for backward compatibility display only)
                'conditions_met': {
                    'edge_threshold': True,
                    'ev_threshold': True,
                    'data_integrity': True
                }
            }
        """
        # Build SelectionInput for universal classifier
        now_unix = int(datetime.now(timezone.utc).timestamp())
        
        selection = SelectionInput(
            sport="GENERIC",  # Sport-agnostic
            market_type="GENERIC",
            selection_id="analytics_request",
            selection_text="Analysis",
            timestamp_unix=now_unix,
            sims_n=sim_count,
            p_model=model_prob,
            price_american=american_odds,
            opp_price_american=opp_american_odds
        )
        
        # Classify using universal system
        result = build_classification_result(selection, now_unix)
        
        # Calculate metrics
        if result.tier == Tier.BLOCKED:
            # Data integrity failure
            return {
                'classification': 'BLOCKED',
                'prob_edge': None,
                'ev': None,
                'p_model': model_prob,
                'p_market_fair': None,
                'recommendation': 'Blocked - Data integrity failure (insufficient sims or invalid data)',
                'badge_color': 'red',
                'conditions_met': {
                    'edge_threshold': False,
                    'ev_threshold': False,
                    'data_integrity': False
                }
            }
        
        # Calculate for display (with None checks)
        edge_pct = result.prob_edge if result.prob_edge is not None else 0.0
        ev_val = result.ev if result.ev is not None else 0.0
        
        # Map tier to response
        tier_map = {
            Tier.EDGE: {
                'classification': 'EDGE',
                'recommendation': f"Strong Edge - {edge_pct*100:.1f}% probability advantage with {ev_val*100:+.1f}% EV",
                'badge_color': 'green'
            },
            Tier.LEAN: {
                'classification': 'LEAN',
                'recommendation': f"Lean - {edge_pct*100:.1f}% probability advantage with {ev_val*100:+.1f}% EV",
                'badge_color': 'yellow'
            },
            Tier.MARKET_ALIGNED: {
                'classification': 'MARKET_ALIGNED',
                'recommendation': f"Market Aligned - Edge ({edge_pct*100:.1f}%) below threshold",
                'badge_color': 'gray'
            }
        }
        
        tier_info = tier_map.get(result.tier, tier_map[Tier.MARKET_ALIGNED])
        
        # Legacy conditions for backward compatibility
        conditions_met = {
            'edge_threshold': edge_pct >= 0.05 if result.tier == Tier.EDGE else edge_pct >= 0.025,
            'ev_threshold': ev_val >= 0.0 if result.tier == Tier.EDGE else ev_val >= -0.005,
            'data_integrity': True
        }
        
        return {
            'classification': tier_info['classification'],
            'prob_edge': edge_pct,
            'ev': ev_val,
            'p_model': result.p_model,
            'p_market_fair': result.p_market_fair,
            'recommendation': tier_info['recommendation'],
            'badge_color': tier_info['badge_color'],
            'conditions_met': conditions_met,
            
            # Additional context (volatility/confidence tracked separately, NOT affecting tier)
            'metadata': {
                'confidence': confidence,
                'volatility': volatility,
                'injury_impact': injury_impact,
                'note': 'Volatility/confidence/CLV do not affect tier classification per Universal EDGE/LEAN spec'
            }
        }
    
    @staticmethod
    def calculate_parlay_ev(
        legs: List[Dict[str, Any]],
        sim_count: int = 50000
    ) -> Dict[str, Any]:
        """
        Calculate parlay EV from individual leg probabilities
        
        Args:
            legs: List of {
                'model_prob': 0.58,
                'american_odds': -110,
                'description': 'Lakers -5'
            }
            sim_count: Simulation count for EV+ validation
            
        Returns:
            {
                'parlay_probability': 0.195,  # Product of all legs
                'parlay_ev': 0.124,
                'individual_evs': [...],
                'combined_odds': +450,
                'is_ev_plus': True,
                'edge_display': '+12.4%'
            }
        """
        if not legs:
            return {
                'error': 'No legs provided',
                'parlay_probability': 0,
                'parlay_ev': 0
            }
        
        # Calculate combined probability (product of all legs)
        parlay_prob = 1.0
        for leg in legs:
            parlay_prob *= leg['model_prob']
        
        # Calculate individual EVs
        individual_evs = []
        for leg in legs:
            ev_result = AnalyticsService.calculate_expected_value(
                model_probability=leg['model_prob'],
                american_odds=leg['american_odds'],
                sim_count=sim_count
            )
            individual_evs.append({
                'description': leg.get('description', 'Unknown'),
                'ev': ev_result['ev_per_dollar'],
                'edge': ev_result['display_edge']
            })
        
        # Calculate parlay odds (multiply all decimal odds)
        parlay_decimal = 1.0
        for leg in legs:
            # Convert American to decimal
            odds = leg['american_odds']
            if odds > 0:
                decimal = 1 + (odds / 100)
            else:
                decimal = 1 + (100 / abs(odds))
            parlay_decimal *= decimal
        
        # Calculate parlay EV
        parlay_ev = parlay_prob * (parlay_decimal - 1) - (1 - parlay_prob)
        
        # Convert parlay decimal back to American
        if parlay_decimal >= 2.0:
            combined_odds = int((parlay_decimal - 1) * 100)
        else:
            combined_odds = int(-100 / (parlay_decimal - 1))
        
        # EV+ check for parlay
        parlay_edge = parlay_ev
        is_ev_plus = parlay_edge >= 0.03 and sim_count >= 25000
        
        edge_display = f"+{parlay_edge * 100:.1f}%" if parlay_edge > 0 else f"{parlay_edge * 100:.1f}%"
        
        return {
            'parlay_probability': parlay_prob,
            'parlay_ev': parlay_ev,
            'individual_evs': individual_evs,
            'combined_odds': combined_odds,
            'parlay_decimal_odds': parlay_decimal,
            'is_ev_plus': is_ev_plus,
            'edge_display': edge_display,
            'leg_count': len(legs)
        }
    
    @staticmethod
    def get_tier_message(sim_count: int, context: str = 'general') -> str:
        """
        Get tier-specific messaging for simulation power
        
        Args:
            sim_count: Number of simulations run
            context: 'general' | 'game' | 'parlay' | 'confidence'
            
        Returns:
            Tier-appropriate message explaining simulation depth
        """
        tier_config = SimulationTierConfig.get_tier_config(sim_count)
        label = tier_config['label']
        
        messages = {
            10000: {
                'general': f"{label} Tier (10K sims) - Upgrade to Core (25K), Pro (50K) or Elite (100K) for sharper edges.",
                'game': f"Running at {label} tier (10K sims). Higher tiers use 25K-100K sims for tighter projections.",
                'parlay': f"Parlay built with {label} simulation power (10K). Pro/Elite tiers run 50K-100K for multi-leg precision.",
                'confidence': f"Confidence limited by {label} tier (10K sims). More simulations = tighter bands."
            },
            25000: {
                'general': f"{label} Tier (25K sims) - Upgrade to Pro (50K) or Elite (100K) for maximum precision.",
                'game': f"Running at {label} tier (25K sims). Elite tier uses 100K sims for complex matchups.",
                'parlay': f"Parlay validated with {label} depth (25K sims). Elite tier runs 100K for correlation analysis.",
                'confidence': f"{label} tier provides solid confidence bands (25K sims). Elite offers ±3.5% precision."
            },
            50000: {
                'general': f"{label} Tier (50K sims) - Near-maximum simulation depth. Elite runs 100K for the tightest edges.",
                'game': f"Running at {label} tier (50K sims). You're getting high-resolution projections.",
                'parlay': f"Parlay built with {label} precision (50K sims). Elite tier adds 2x depth for micro-edges.",
                'confidence': f"{label} tier delivers tight confidence bands (±6%). Elite offers ±3.5%."
            },
            100000: {
                'general': f"You're running BeatVegas at full simulation power ({label} - 100K sims).",
                'game': f"{label} tier - Maximum 100K simulations. You're seeing our highest-resolution projections.",
                'parlay': f"Parlay optimized with {label} depth (100K sims). Full correlation and edge detection enabled.",
                'confidence': f"{label} confidence bands (±3.5%) - Tightest variance possible at 100K sims."
            }
        }
        
        return messages.get(sim_count, {}).get(context, f"{label} Tier - {sim_count:,} simulations")
    
    @staticmethod
    def format_confidence_message(
        confidence_score: int,
        volatility: str,
        sim_count: int
    ) -> Dict[str, Any]:
        """
        Format confidence score with proper context
        
        Returns banner color, message, and tooltip explanation
        
        Args:
            confidence_score: 0-100 score from ConfidenceCalculator
            volatility: 'LOW' | 'MEDIUM' | 'HIGH'
            sim_count: Simulation count
            
        Returns:
            {
                'score': 73,
                'label': 'High' | 'Medium' | 'Low',
                'banner_type': 'success' | 'warning' | 'info',
                'banner_message': '...',
                'tooltip': '...'
            }
        """
        # Get label
        if confidence_score >= 70:
            label = 'High'
            banner_type = 'success'
            banner_message = "High-confidence simulation – strong alignment across simulations, market lines and correlation data."
        elif confidence_score >= 40:
            label = 'Medium'
            banner_type = 'info'
            banner_message = "Medium-confidence simulation – moderate variance in outcomes. Proceed with awareness."
        else:
            label = 'Low'
            banner_type = 'warning'
            banner_message = "Low-confidence simulation – high volatility expected. Treat as informational, not strong edge."
        
        # Tooltip explanation (mandatory from spec)
        tooltip = (
            "Confidence measures how stable the simulation output is.\n\n"
            "• Low confidence = wide distribution / volatile game\n"
            "• High confidence = tight distribution / predictable game\n\n"
            "Low confidence does not mean the model is wrong – it means "
            "the matchup is inherently swingy."
        )
        
        # Add tier context if not max tier
        tier_config = SimulationTierConfig.get_tier_config(sim_count)
        if sim_count < 100000:
            tooltip += f"\n\nConfidence limited by {tier_config['label']} tier ({sim_count:,} sims). Higher tiers use up to 100K sims for more stable outcomes."
        
        return {
            'score': confidence_score,
            'label': label,
            'banner_type': banner_type,
            'banner_message': banner_message,
            'tooltip': tooltip,
            'volatility': volatility,
            'tier_label': tier_config['label']
        }
