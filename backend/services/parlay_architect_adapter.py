"""
Parlay Architect Integration Adapter

Bridges existing parlay_architect.py with new truth_mode_parlay.py system.
Enables gradual migration from hard-block gates to penalty-based optimization.
"""

from typing import Dict, List, Any
from datetime import datetime, timezone
import logging

from core.truth_mode_parlay import (
    TruthMode, RiskProfile, MarketType,
    calculate_parlay_weight
)
from core.parlay_optimization_engine import ParlayOptimizationEngine
from db.mongo import db

logger = logging.getLogger(__name__)


class ParlayArchitectAdapter:
    """
    Adapter that adds PARLAY mode to existing parlay_architect
    
    Usage:
        adapter = ParlayArchitectAdapter()
        
        # Old way (STRICT — blocks most slates)
        result = adapter.generate(mode=TruthMode.STRICT, ...)
        
        # New way (PARLAY — always produces)
        result = adapter.generate(mode=TruthMode.PARLAY, ...)
    """
    
    def __init__(self):
        self.engine = ParlayOptimizationEngine(db=db)
    
    def enrich_simulation_with_parlay_data(
        self,
        simulation: Dict[str, Any],
        mode: TruthMode = TruthMode.PARLAY
    ) -> Dict[str, Any]:
        """
        Add parlay-specific fields to simulation data
        
        Converts existing simulation to parlay candidate format with:
        - strict_state (PICK/LEAN/NO_PLAY from existing pick_state)
        - parlay_weight (computed from simulation metrics)
        - parlay_eligible (boolean)
        - parlay_reason_codes (why penalized)
        """
        # Map pick_state to strict_state
        pick_state = simulation.get('pick_state', 'NO_PLAY')
        strict_state_map = {
            'PICK': 'PICK',
            'LEAN': 'LEAN',
            'NO_PLAY': 'NO_PLAY',
            'UNKNOWN': 'NO_PLAY'
        }
        strict_state = strict_state_map.get(pick_state, 'NO_PLAY')
        
        # Extract relevant metrics
        candidate_data = {
            'event_id': simulation.get('event_id'),
            'sport_key': simulation.get('sport_key'),
            'strict_state': strict_state,
            'can_parlay': simulation.get('can_parlay', False),
            'win_probability': simulation.get('win_probability', 0.5),
            'edge_points': self._extract_edge(simulation),
            'confidence_score': simulation.get('confidence_score', 0.5),
            'volatility_band': self._map_volatility_band(simulation),
            'distribution_stable': self._check_distribution_stable(simulation),
            'data_confidence': self._assess_data_confidence(simulation),
            'market_type': self._determine_market_type(simulation),
            'data_integrity_pass': simulation.get('rcl_passed', True),
            'model_validity_pass': True,  # Assumed if simulation exists
        }
        
        # Compute parlay weight
        weight_result = calculate_parlay_weight(candidate_data, mode=mode)
        
        # Add parlay fields to simulation
        simulation['parlay_weight'] = weight_result.final_weight
        simulation['parlay_eligible'] = weight_result.final_weight >= 0.5
        simulation['parlay_reason_codes'] = weight_result.reason_codes
        simulation['strict_state'] = strict_state
        
        return simulation
    
    def generate_parlay_with_new_engine(
        self,
        simulations: List[Dict[str, Any]],
        mode: TruthMode = TruthMode.PARLAY,
        risk_profile: RiskProfile = RiskProfile.BALANCED,
        leg_count: int = 4,
        include_higher_risk_legs: bool = False,
        include_props: bool = False,  # Disable props by default until prop feed ready
        dfs_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Generate parlay using new optimization engine
        
        This is the bridge method that:
        1. Enriches simulations with parlay data
        2. Calls new optimization engine
        3. Formats result for existing API contracts
        """
        # Enrich all simulations
        enriched = []
        for sim in simulations:
            try:
                enriched_sim = self.enrich_simulation_with_parlay_data(sim, mode=mode)
                enriched.append(enriched_sim)
            except Exception as e:
                logger.warning(f"Failed to enrich simulation {sim.get('event_id')}: {e}")
                continue
        
        if not enriched:
            return {
                'success': False,
                'error': 'NO_ENRICHED_CANDIDATES',
                'message': 'No simulations could be processed for parlay generation',
                'mode': mode.value,
                'risk_profile': risk_profile.value
            }
        
        # Generate parlay with optimization engine
        result = self.engine.generate_parlay(
            candidates=enriched,
            mode=mode,
            risk_profile=risk_profile,
            leg_count=leg_count,
            include_higher_risk_legs=include_higher_risk_legs,
            include_props=include_props,
            include_game_lines=True,
            dfs_mode=dfs_mode,
            allow_same_game=False,
            allow_cross_sport=True
        )
        
        # Format for existing API
        if not result.success:
            return {
                'success': False,
                'error': result.fail_reason,
                'message': self._format_failure_message(result),
                'mode': mode.value,
                'risk_profile': risk_profile.value,
                'fallback_steps': result.fallback_steps_taken
            }
        
        # Success — format legs
        formatted_legs = []
        for leg in result.legs:
            formatted_legs.append({
                'event_id': leg.get('event_id'),
                'sport': leg.get('sport_key'),
                'matchup': f"{leg.get('team_a', 'Team A')} vs {leg.get('team_b', 'Team B')}",
                'pick': self._extract_pick(leg),
                'win_probability': leg.get('win_probability'),
                'edge': leg.get('edge_points', 0),
                'confidence': leg.get('confidence_score'),
                'parlay_weight': leg.get('parlay_weight'),
                'strict_state': leg.get('strict_state'),
                'volatility': leg.get('volatility_band'),
                'reason_codes': leg.get('parlay_reason_codes', [])
            })
        
        return {
            'success': True,
            'parlay_id': result.parlay_id,
            'mode': mode.value,
            'risk_profile': result.risk_profile_used.value,
            'risk_profile_requested': result.risk_profile_requested.value,
            'leg_count': result.leg_count_used,
            'legs': formatted_legs,
            'portfolio_score': result.portfolio_score,
            'expected_hit_rate': result.expected_hit_rate,
            'expected_value': result.expected_value_proxy,
            'fallback_steps': result.fallback_steps_taken,
            'generated_at': result.generation_timestamp,
            
            # Metadata for UI
            'pick_leg_count': sum(1 for leg in result.legs if leg.get('strict_state') == 'PICK'),
            'lean_leg_count': sum(1 for leg in result.legs if leg.get('strict_state') == 'LEAN'),
            'high_vol_leg_count': sum(1 for leg in result.legs if leg.get('volatility_band') == 'HIGH'),
            'message': self._format_success_message(result)
        }
    
    def _extract_edge(self, simulation: Dict[str, Any]) -> float:
        """Extract edge from simulation"""
        # Try spread analysis first
        sharp_analysis = simulation.get('sharp_analysis', {})
        spread_edge = sharp_analysis.get('spread', {}).get('edge_points', 0)
        if spread_edge > 0:
            return spread_edge
        
        # Try total analysis
        total_edge = sharp_analysis.get('total', {}).get('edge_points', 0)
        return total_edge
    
    def _map_volatility_band(self, simulation: Dict[str, Any]) -> str:
        """Map volatility index to band"""
        volatility_index = simulation.get('volatility_index', 'moderate')
        if isinstance(volatility_index, str):
            vol_map = {
                'low': 'LOW',
                'moderate': 'MED',
                'high': 'HIGH'
            }
            return vol_map.get(volatility_index.lower(), 'MED')
        
        # Numeric volatility
        variance = simulation.get('variance', 100)
        if variance < 150:
            return 'LOW'
        elif variance < 300:
            return 'MED'
        else:
            return 'HIGH'
    
    def _check_distribution_stable(self, simulation: Dict[str, Any]) -> bool:
        """Check if distribution is stable"""
        variance = simulation.get('variance', 100)
        confidence = simulation.get('confidence_score', 0.5)
        
        # Stable if low variance and high confidence
        return variance < 300 and confidence >= 0.60
    
    def _assess_data_confidence(self, simulation: Dict[str, Any]) -> str:
        """Assess data quality confidence"""
        rcl_passed = simulation.get('rcl_passed', True)
        injury_impact = abs(simulation.get('injury_impact_weighted', 0))
        
        if rcl_passed and injury_impact < 5:
            return 'HIGH'
        elif rcl_passed or injury_impact < 10:
            return 'MED'
        else:
            return 'LOW'
    
    def _determine_market_type(self, simulation: Dict[str, Any]) -> str:
        """Determine market type from simulation"""
        # Check sharp analysis for market type
        sharp_analysis = simulation.get('sharp_analysis', {})
        if sharp_analysis.get('spread', {}).get('sharp_side'):
            return 'GAME_SPREAD'
        elif sharp_analysis.get('total', {}).get('sharp_side'):
            return 'GAME_TOTAL'
        else:
            return 'GAME_TOTAL'  # Default
    
    def _extract_pick(self, leg: Dict[str, Any]) -> str:
        """Extract pick from leg data"""
        sharp_analysis = leg.get('sharp_analysis', {})
        
        # Try spread first
        spread_pick = sharp_analysis.get('spread', {}).get('sharp_side')
        if spread_pick:
            return spread_pick
        
        # Try total
        total_pick = sharp_analysis.get('total', {}).get('sharp_side')
        if total_pick:
            return total_pick
        
        # Fallback
        return f"{leg.get('team_a', 'Team A')} (Model Lean)"
    
    def _format_failure_message(self, result) -> str:
        """Format user-friendly failure message"""
        if 'DI_MV_FAILED' in result.fail_reason:
            return "No eligible legs: Data integrity checks failed across slate. This is rare and may indicate a feed issue."
        
        if 'FALLBACK_EXHAUSTED' in result.fail_reason:
            return "No High-Confidence parlay available today. Balanced / High-Volatility options may be available with adjusted settings."
        
        return f"Parlay generation failed: {result.fail_reason}"
    
    def _format_success_message(self, result) -> str:
        """Format user-friendly success message"""
        if result.fallback_steps_taken:
            fallback_desc = ' → '.join(result.fallback_steps_taken)
            return f"Parlay generated with fallbacks: {fallback_desc}"
        
        if result.risk_profile_used != result.risk_profile_requested:
            return f"Parlay generated with adjusted risk profile: {result.risk_profile_used.value}"
        
        return f"Optimal {result.risk_profile_used.value} parlay generated"


# Global adapter instance
parlay_adapter = ParlayArchitectAdapter()
