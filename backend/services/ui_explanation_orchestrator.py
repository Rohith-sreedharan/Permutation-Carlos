"""
UI Explanation Layer Orchestrator v1.0.2
Status: LOCKED FOR IMPLEMENTATION
Package: 2.5 – Decision Explanation & Transparency

Complete orchestrator that:
1. Computes all 6 explanation boxes
2. Validates forbidden phrases
3. Validates consistency
4. Returns complete explanation layer payload

USAGE:
    from backend.services.ui_explanation_orchestrator import generate_explanation_layer
    
    explanation_layer = generate_explanation_layer(
        spread_data=spread_market_data,
        total_data=total_market_data,
        ml_data=ml_market_data,
        simulation_data=simulation_metadata,
        game_metadata=game_info
    )
    
    if explanation_layer['is_valid']:
        # Render to UI
        render_explanation_boxes(explanation_layer['boxes'])
    else:
        # Handle validation failures
        log_validation_errors(explanation_layer['validation_errors'])
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Import explanation layer components
from services.ui_explanation_layer import (
    Classification,
    NoActionSubtype,
    GlobalState,
    ExecutionConstraint,
    compute_global_state,
    render_key_drivers,
    render_edge_context,
    render_edge_summary,
    render_clv_forecast,
    render_why_edge_exists,
    render_final_unified_summary,
    EDGE_THRESHOLD,
    LEAN_THRESHOLD
)

# Import validation components
from services.explanation_forbidden_phrases import (
    check_forbidden_phrases,
    is_action_language_safe
)

from services.explanation_consistency_validator import (
    validate_explanation_consistency,
    ValidationLevel
)


@dataclass
class MarketData:
    """Market-specific data for explanation generation"""
    classification: Classification
    ev: float
    sharp_side: Optional[str]
    market_type: str  # SPREAD, TOTAL, MONEYLINE
    current_line: Optional[float]
    opening_line: Optional[float]
    projected_close_line: Optional[float]
    odds: Optional[int]
    execution_constraints: List[ExecutionConstraint]


@dataclass
class SimulationMetadata:
    """Simulation metadata for Key Drivers box"""
    pace_delta: float
    injury_adjusted: bool
    matchup_factor: Optional[str]
    total_sims: int
    volatility_state: str  # LOW, NORMAL, HIGH
    calibration_state: str  # CALIBRATED, CALIBRATING, UNCALIBRATED


@dataclass
class GameMetadata:
    """Game-level metadata"""
    event_id: str
    home_team: str
    away_team: str
    sport: str
    league: str
    game_time: datetime


@dataclass
class ExplanationLayer:
    """Complete explanation layer output"""
    is_valid: bool
    boxes: Dict[str, Any]  # All 6 boxes
    validation_errors: List[Dict]
    validation_warnings: List[Dict]
    meta: Dict  # Generation metadata


class UIExplanationOrchestrator:
    """
    Orchestrates generation and validation of complete explanation layer.
    
    This is the main entry point for generating UI explanations.
    """
    
    def generate(
        self,
        spread_data: Optional[MarketData],
        total_data: Optional[MarketData],
        ml_data: Optional[MarketData],
        simulation_data: Optional[SimulationMetadata],
        game_metadata: Optional[GameMetadata]
    ) -> ExplanationLayer:
        """
        Generate complete explanation layer with validation.
        
        Args:
            spread_data: Spread market data (None if not available)
            total_data: Total market data (None if not available)
            ml_data: Moneyline market data (None if not available)
            simulation_data: Simulation metadata
            game_metadata: Game metadata
        
        Returns:
            ExplanationLayer with all boxes, validation results, and metadata
        """
        # Step 1: Compute global state
        spread_cls = spread_data.classification if spread_data else Classification.NO_ACTION
        total_cls = total_data.classification if total_data else Classification.NO_ACTION
        ml_cls = ml_data.classification if ml_data else Classification.NO_ACTION
        
        global_state = compute_global_state(spread_cls, total_cls, ml_cls)
        
        # Step 2: Determine best pick (for display purposes only)
        best_pick = self._determine_best_pick(spread_data, total_data, ml_data)
        
        # Step 3: Determine global verdict and classification
        # CRITICAL: Verdict from classifications ONLY, NOT from best_pick
        global_classification = self._compute_global_classification(
            spread_cls, total_cls, ml_cls
        )
        
        # Step 4: Get execution constraints (union of all markets)
        all_constraints = self._collect_execution_constraints(
            spread_data, total_data, ml_data
        )
        has_execution_constraints = len(all_constraints) > 0
        
        # Step 5: Render all 6 boxes
        boxes = {}
        
        # Box 1: Key Drivers
        if simulation_data:
            boxes['key_drivers'] = render_key_drivers({
                'pace_delta': simulation_data.pace_delta,
                'injury_adjusted': simulation_data.injury_adjusted,
                'matchup_factor': simulation_data.matchup_factor,
                'total_sims': simulation_data.total_sims
            })
        else:
            boxes['key_drivers'] = None
        
        # Box 2: Edge Context Notes (conditional)
        if simulation_data:
            boxes['edge_context'] = render_edge_context(
                classification=global_classification,
                ev=best_pick['ev'] if best_pick else 0.0,
                volatility_state=simulation_data.volatility_state,
                calibration_state=simulation_data.calibration_state,
                max_ev=best_pick['ev'] if best_pick else 0.0,
                execution_constraints=all_constraints
            )
        else:
            boxes['edge_context'] = None
        
        # Box 3: Edge Summary
        boxes['edge_summary'] = render_edge_summary(
            classification=global_classification,
            max_ev=best_pick['ev'] if best_pick else 0.0,
            sharp_side=best_pick['side'] if best_pick else None,
            market_type=best_pick['market'] if best_pick else 'SPREAD',
            execution_constraints=all_constraints
        )
        
        # Box 4: CLV Forecast
        if best_pick:
            boxes['clv_forecast'] = render_clv_forecast(
                classification=global_classification,
                current_line=best_pick.get('current_line', 0),
                opening_line=best_pick.get('opening_line', 0),
                projected_close_line=best_pick.get('projected_close_line'),
                sharp_side=best_pick['side'],
                market_type=best_pick['market']
            )
        else:
            # Fallback for no best pick
            boxes['clv_forecast'] = {
                'title': 'CLV Forecast',
                'forecast': 'No line movement forecast available. No actionable market identified.',
                'line_drift': 0,
                'magnitude': 'minimal',
                'has_projection': False
            }
        
        # Box 5: Why This Edge Exists
        if simulation_data:
            boxes['why_edge_exists'] = render_why_edge_exists(
                classification=global_classification,
                global_state=global_state,
                max_ev=best_pick['ev'] if best_pick else 0.0,
                sharp_side=best_pick['side'] if best_pick else None,
                market_type=best_pick['market'] if best_pick else 'SPREAD',
                volatility_state=simulation_data.volatility_state
            )
        else:
            boxes['why_edge_exists'] = None
        
        # Box 6: Final Unified Summary
        if simulation_data:
            boxes['final_summary'] = render_final_unified_summary(
                spread_classification=spread_cls,
                total_classification=total_cls,
                ml_classification=ml_cls,
                volatility_state=simulation_data.volatility_state,
                calibration_state=simulation_data.calibration_state,
                execution_constraints=all_constraints,
                best_market=best_pick['market'] if best_pick else None,
                best_pick=best_pick
            )
        else:
            boxes['final_summary'] = None
        
        # Step 6: Validate forbidden phrases
        forbidden_phrase_violations = []
        for box_name, box_content in boxes.items():
            if box_content is None:
                continue
            
            # Extract all text from box
            box_text = self._extract_all_text(box_content)
            
            is_valid, violations = check_forbidden_phrases(
                text=box_text,
                classification=global_classification.value,
                has_execution_constraints=has_execution_constraints,
                box_name=box_name
            )
            
            if not is_valid:
                for violation in violations:
                    forbidden_phrase_violations.append({
                        'box': box_name,
                        'phrase': violation['phrase'],
                        'violation_type': violation['violation_type'],
                        'reason': violation['reason']
                    })
        
        # Step 7: Validate consistency (only if all boxes exist)
        if all([boxes.get('key_drivers'), boxes.get('why_edge_exists'), boxes.get('final_summary')]):
            # Type assertions after validation
            assert boxes['key_drivers'] is not None
            assert boxes['why_edge_exists'] is not None
            assert boxes['final_summary'] is not None
            is_consistent, consistency_errors = validate_explanation_consistency(
                key_drivers=boxes['key_drivers'],
                edge_context=boxes['edge_context'],
                edge_summary=boxes['edge_summary'],
                clv_forecast=boxes['clv_forecast'],
                why_edge_exists=boxes['why_edge_exists'],
                final_summary=boxes['final_summary'],
                classification=global_classification.value,
                has_execution_constraints=has_execution_constraints
            )
        else:
            is_consistent = False
            consistency_errors = [{"error": "Missing required boxes for validation"}]
        
        # Step 8: Aggregate validation results
        critical_errors = []
        warnings = []
        
        # Forbidden phrases are CRITICAL
        for violation in forbidden_phrase_violations:
            critical_errors.append({
                'type': 'FORBIDDEN_PHRASE',
                'severity': 'CRITICAL',
                'box': violation['box'],
                'message': f"Forbidden phrase detected: '{violation['phrase']}' - {violation['reason']}"
            })
        
        # Consistency errors
        for error in consistency_errors:
            # Handle both dict and object types
            if isinstance(error, dict):
                error_dict = {
                    'type': 'CONSISTENCY',
                    'severity': error.get('severity', 'CRITICAL'),
                    'boxes': error.get('boxes', []),
                    'message': error.get('error', error.get('message', 'Unknown error')),
                    'rule_id': error.get('rule_id', 'unknown')
                }
                critical_errors.append(error_dict)
            else:
                error_dict = {
                    'type': 'CONSISTENCY',
                    'severity': error.level.value,
                    'boxes': error.affected_boxes,
                    'message': error.message,
                    'rule_id': error.rule_id
                }
                
                if error.level == ValidationLevel.CRITICAL:
                    critical_errors.append(error_dict)
                elif error.level == ValidationLevel.WARNING:
                    warnings.append(error_dict)
        
        # Determine overall validity
        is_valid = len(critical_errors) == 0
        
        # Step 9: Build metadata
        meta = {
            'generated_at': datetime.utcnow().isoformat(),
            'event_id': game_metadata.event_id if game_metadata else 'unknown',
            'global_classification': global_classification.value,
            'global_state': global_state.value,
            'has_execution_constraints': has_execution_constraints,
            'best_pick_market': best_pick['market'] if best_pick else None,
            'validation_passed': is_valid,
            'critical_error_count': len(critical_errors),
            'warning_count': len(warnings)
        }
        
        # Step 10: Return complete explanation layer
        return ExplanationLayer(
            is_valid=is_valid,
            boxes=boxes,
            validation_errors=critical_errors,
            validation_warnings=warnings,
            meta=meta
        )
    
    # ==================== HELPER METHODS ====================
    
    def _compute_global_classification(
        self,
        spread_cls: Classification,
        total_cls: Classification,
        ml_cls: Classification
    ) -> Classification:
        """
        Compute global classification from market classifications.
        
        LOCKED RULE (ADDENDUM v1.0.2):
        EDGE > LEAN > NO_ACTION
        """
        classifications = [spread_cls, total_cls, ml_cls]
        
        if Classification.EDGE in classifications:
            return Classification.EDGE
        elif Classification.LEAN in classifications:
            return Classification.LEAN
        else:
            return Classification.NO_ACTION
    
    def _determine_best_pick(
        self,
        spread_data: Optional[MarketData],
        total_data: Optional[MarketData],
        ml_data: Optional[MarketData]
    ) -> Optional[Dict]:
        """
        Determine best pick for display purposes.
        
        NOTE: This is DISPLAY-ONLY metadata and MUST NOT determine verdict.
        Missing best_pick MUST NOT downgrade verdict.
        
        Priority: Highest EV among EDGE picks, then LEAN picks
        """
        candidates = []
        
        if spread_data and spread_data.classification in [Classification.EDGE, Classification.LEAN]:
            candidates.append({
                'market': 'SPREAD',
                'ev': spread_data.ev,
                'side': spread_data.sharp_side,
                'classification': spread_data.classification,
                'current_line': spread_data.current_line,
                'opening_line': spread_data.opening_line,
                'projected_close_line': spread_data.projected_close_line,
                'odds': spread_data.odds
            })
        
        if total_data and total_data.classification in [Classification.EDGE, Classification.LEAN]:
            candidates.append({
                'market': 'TOTAL',
                'ev': total_data.ev,
                'side': total_data.sharp_side,
                'classification': total_data.classification,
                'current_line': total_data.current_line,
                'opening_line': total_data.opening_line,
                'projected_close_line': total_data.projected_close_line,
                'odds': total_data.odds
            })
        
        if ml_data and ml_data.classification in [Classification.EDGE, Classification.LEAN]:
            candidates.append({
                'market': 'MONEYLINE',
                'ev': ml_data.ev,
                'side': ml_data.sharp_side,
                'classification': ml_data.classification,
                'current_line': None,
                'opening_line': None,
                'projected_close_line': None,
                'odds': ml_data.odds
            })
        
        if not candidates:
            return None
        
        # Sort by classification (EDGE > LEAN), then by EV
        candidates.sort(
            key=lambda x: (
                0 if x['classification'] == Classification.EDGE else 1,
                -x['ev']
            )
        )
        
        return candidates[0]
    
    def _collect_execution_constraints(
        self,
        spread_data: Optional[MarketData],
        total_data: Optional[MarketData],
        ml_data: Optional[MarketData]
    ) -> List[ExecutionConstraint]:
        """Collect all execution constraints from all markets (union)."""
        all_constraints = set()
        
        if spread_data:
            all_constraints.update(spread_data.execution_constraints)
        if total_data:
            all_constraints.update(total_data.execution_constraints)
        if ml_data:
            all_constraints.update(ml_data.execution_constraints)
        
        return list(all_constraints)
    
    def _extract_all_text(self, box_content: Any) -> str:
        """Extract all text from box for validation."""
        if box_content is None:
            return ""
        
        text_parts = []
        
        if isinstance(box_content, dict):
            for key, value in box_content.items():
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif isinstance(item, dict):
                            text_parts.append(self._extract_all_text(item))
                elif isinstance(value, dict):
                    text_parts.append(self._extract_all_text(value))
        
        return " ".join(text_parts)


# ==================== CONVENIENCE FUNCTION ====================

def generate_explanation_layer(
    spread_data: Optional[MarketData] = None,
    total_data: Optional[MarketData] = None,
    ml_data: Optional[MarketData] = None,
    simulation_data: Optional[SimulationMetadata] = None,
    game_metadata: Optional[GameMetadata] = None
) -> ExplanationLayer:
    """
    Generate complete explanation layer with validation.
    
    This is the main entry point for generating UI explanations.
    
    Usage:
        explanation_layer = generate_explanation_layer(
            spread_data=MarketData(
                classification=Classification.EDGE,
                ev=4.2,
                sharp_side='home',
                market_type='SPREAD',
                current_line=-7.5,
                opening_line=-6.5,
                projected_close_line=-8.0,
                odds=-110,
                execution_constraints=[]
            ),
            simulation_data=SimulationMetadata(
                pace_delta=3.2,
                injury_adjusted=True,
                matchup_factor='Defensive efficiency mismatch',
                total_sims=100000,
                volatility_state='LOW',
                calibration_state='CALIBRATED'
            ),
            game_metadata=GameMetadata(
                event_id='evt_123',
                home_team='Lakers',
                away_team='Warriors',
                sport='basketball',
                league='NBA',
                game_time=datetime.utcnow()
            )
        )
        
        if explanation_layer.is_valid:
            # Render boxes to UI
            for box_name, box_content in explanation_layer.boxes.items():
                render_box(box_name, box_content)
        else:
            # Handle validation errors
            for error in explanation_layer.validation_errors:
                log_error(error)
    """
    orchestrator = UIExplanationOrchestrator()
    return orchestrator.generate(
        spread_data=spread_data,
        total_data=total_data,
        ml_data=ml_data,
        simulation_data=simulation_data,
        game_metadata=game_metadata
    )


if __name__ == "__main__":
    print("=== UI Explanation Layer Orchestrator Tests ===\n")
    
    from datetime import datetime, timedelta
    
    # Test 1: Clean EDGE scenario
    print("Test 1: Clean EDGE")
    explanation = generate_explanation_layer(
        spread_data=MarketData(
            classification=Classification.EDGE,
            ev=4.2,
            sharp_side='home',
            market_type='SPREAD',
            current_line=-7.5,
            opening_line=-6.5,
            projected_close_line=-8.0,
            odds=-110,
            execution_constraints=[]
        ),
        total_data=MarketData(
            classification=Classification.NO_ACTION,
            ev=-0.3,
            sharp_side=None,
            market_type='TOTAL',
            current_line=215.5,
            opening_line=215.0,
            projected_close_line=None,
            odds=-110,
            execution_constraints=[]
        ),
        ml_data=None,
        simulation_data=SimulationMetadata(
            pace_delta=3.2,
            injury_adjusted=True,
            matchup_factor='Defensive efficiency mismatch',
            total_sims=100000,
            volatility_state='LOW',
            calibration_state='CALIBRATED'
        ),
        game_metadata=GameMetadata(
            event_id='evt_test_001',
            home_team='Lakers',
            away_team='Warriors',
            sport='basketball',
            league='NBA',
            game_time=datetime.utcnow() + timedelta(hours=2)
        )
    )
    
    print(f"Valid: {explanation.is_valid}")
    print(f"Global Classification: {explanation.meta['global_classification']}")
    print(f"Edge Context Shown: {explanation.boxes['edge_context'] is not None}")
    print(f"Final Verdict: {explanation.boxes['final_summary']['verdict']}")
    print(f"Validation Errors: {len(explanation.validation_errors)}")
    print(f"Warnings: {len(explanation.validation_warnings)}")
    assert explanation.is_valid
    assert explanation.meta['global_classification'] == 'EDGE'
    assert explanation.boxes['edge_context'] is None  # Clean EDGE should hide
    print("✅ Clean EDGE test passed\n")
    
    # Test 2: EDGE with constraints
    print("Test 2: EDGE with Execution Constraints")
    explanation = generate_explanation_layer(
        spread_data=MarketData(
            classification=Classification.EDGE,
            ev=5.1,
            sharp_side='away',
            market_type='SPREAD',
            current_line=3.5,
            opening_line=2.5,
            projected_close_line=4.0,
            odds=-110,
            execution_constraints=[ExecutionConstraint.HIGH_VOLATILITY]
        ),
        total_data=None,
        ml_data=None,
        simulation_data=SimulationMetadata(
            pace_delta=-2.1,
            injury_adjusted=False,
            matchup_factor=None,
            total_sims=100000,
            volatility_state='HIGH',
            calibration_state='CALIBRATED'
        ),
        game_metadata=GameMetadata(
            event_id='evt_test_002',
            home_team='Chiefs',
            away_team='Bills',
            sport='football',
            league='NFL',
            game_time=datetime.utcnow() + timedelta(hours=6)
        )
    )
    
    print(f"Valid: {explanation.is_valid}")
    print(f"Global Classification: {explanation.meta['global_classification']}")
    print(f"Edge Context Shown: {explanation.boxes['edge_context'] is not None}")
    print(f"Edge Context Notes: {explanation.boxes['edge_context']['notes'][0] if explanation.boxes['edge_context'] else 'N/A'}")
    assert explanation.is_valid
    assert explanation.boxes['edge_context'] is not None  # Should show with constraints
    print("✅ EDGE with constraints test passed\n")
    
    # Test 3: NO_ACTION scenario
    print("Test 3: NO_ACTION")
    explanation = generate_explanation_layer(
        spread_data=MarketData(
            classification=Classification.NO_ACTION,
            ev=-0.2,
            sharp_side=None,
            market_type='SPREAD',
            current_line=-3.0,
            opening_line=-3.0,
            projected_close_line=None,
            odds=-110,
            execution_constraints=[]
        ),
        total_data=MarketData(
            classification=Classification.NO_ACTION,
            ev=0.1,
            sharp_side=None,
            market_type='TOTAL',
            current_line=42.5,
            opening_line=42.5,
            projected_close_line=None,
            odds=-110,
            execution_constraints=[]
        ),
        ml_data=None,
        simulation_data=SimulationMetadata(
            pace_delta=0.5,
            injury_adjusted=False,
            matchup_factor=None,
            total_sims=100000,
            volatility_state='NORMAL',
            calibration_state='CALIBRATED'
        ),
        game_metadata=GameMetadata(
            event_id='evt_test_003',
            home_team='Patriots',
            away_team='Jets',
            sport='football',
            league='NFL',
            game_time=datetime.utcnow() + timedelta(hours=3)
        )
    )
    
    print(f"Valid: {explanation.is_valid}")
    print(f"Global Classification: {explanation.meta['global_classification']}")
    print(f"Edge Context Shown: {explanation.boxes['edge_context'] is not None}")
    print(f"NO_ACTION Subtype: {explanation.boxes['final_summary'].get('subtype')}")
    assert explanation.is_valid
    assert explanation.meta['global_classification'] == 'NO_ACTION'
    assert explanation.boxes['edge_context'] is not None  # Should show for NO_ACTION
    print("✅ NO_ACTION test passed\n")
    
    print("=== All Orchestrator Tests Passed ===")
