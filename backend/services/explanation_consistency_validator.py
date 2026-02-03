"""
Explanation Consistency Validator v1.0.2
Status: LOCKED FOR IMPLEMENTATION
Package: 2.5 – Decision Explanation & Transparency

Validates consistency across all 6 explanation boxes to prevent contradictions.

LOCKED VALIDATION RULES:
1. Verdict matches Edge Summary classification
2. Edge Context Notes display logic correct (classification != EDGE OR constraints exist)
3. CLV forecast framing matches classification
4. Global context aligns with verdict
5. No implied action when NO_ACTION

PURPOSE: Ensure all sub-boxes tell consistent story, prevent internal contradictions
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(str, Enum):
    """Severity levels for validation failures"""
    CRITICAL = "CRITICAL"      # MUST fix before rendering (blocks publish)
    WARNING = "WARNING"        # SHOULD fix (logs alert)
    INFO = "INFO"              # Nice to have (informational)


@dataclass
class ValidationError:
    """Validation error definition"""
    rule_id: str
    level: ValidationLevel
    message: str
    affected_boxes: List[str]
    context: Optional[Dict] = None


class ExplanationConsistencyValidator:
    """
    Validates consistency across all 6 explanation boxes.
    
    Ensures:
    - Final verdict matches Edge Summary
    - Edge Context Notes visibility logic correct
    - CLV forecast framing appropriate
    - Global context aligns with verdict
    - No action language when NO_ACTION
    """
    
    def validate_all(
        self,
        key_drivers: Dict,
        edge_context: Optional[Dict],
        edge_summary: Dict,
        clv_forecast: Dict,
        why_edge_exists: Dict,
        final_summary: Dict,
        classification: str,
        has_execution_constraints: bool
    ) -> Tuple[bool, List[ValidationError]]:
        """
        Validate consistency across all 6 boxes.
        
        Args:
            key_drivers: Key Drivers box output
            edge_context: Edge Context Notes box output (None if hidden)
            edge_summary: Edge Summary box output
            clv_forecast: CLV Forecast box output
            why_edge_exists: Why This Edge Exists box output
            final_summary: Final Unified Summary box output
            classification: Classification enum value (NO_ACTION, LEAN, EDGE)
            has_execution_constraints: Whether execution constraints exist
        
        Returns:
            (is_valid, errors) where is_valid is True if no CRITICAL errors
        """
        errors = []
        
        # Rule 1: Verdict matches Edge Summary
        errors.extend(self._validate_verdict_matches_edge_summary(
            edge_summary, final_summary
        ))
        
        # Rule 2: Edge Context Notes display logic
        errors.extend(self._validate_edge_context_display_logic(
            edge_context, classification, has_execution_constraints
        ))
        
        # Rule 3: CLV forecast framing
        errors.extend(self._validate_clv_framing(
            clv_forecast, classification
        ))
        
        # Rule 4: Global context alignment
        errors.extend(self._validate_global_context_alignment(
            why_edge_exists, final_summary, classification
        ))
        
        # Rule 5: No implied action when NO_ACTION
        errors.extend(self._validate_no_implied_action(
            key_drivers, edge_context, edge_summary, clv_forecast,
            why_edge_exists, final_summary, classification
        ))
        
        # Check for CRITICAL errors
        critical_errors = [e for e in errors if e.level == ValidationLevel.CRITICAL]
        is_valid = len(critical_errors) == 0
        
        return is_valid, errors
    
    # ==================== VALIDATION RULES ====================
    
    def _validate_verdict_matches_edge_summary(
        self,
        edge_summary: Dict,
        final_summary: Dict
    ) -> List[ValidationError]:
        """
        RULE 1: Final verdict must match Edge Summary classification.
        
        CRITICAL if mismatch.
        """
        errors = []
        
        edge_classification = edge_summary.get('classification', '')
        final_verdict = final_summary.get('verdict', '')
        
        if edge_classification != final_verdict:
            errors.append(ValidationError(
                rule_id="VERDICT_MISMATCH",
                level=ValidationLevel.CRITICAL,
                message=(
                    f"Final verdict ({final_verdict}) does not match "
                    f"Edge Summary classification ({edge_classification}). "
                    f"This is an internal contradiction."
                ),
                affected_boxes=['edge_summary', 'final_summary'],
                context={
                    'edge_classification': edge_classification,
                    'final_verdict': final_verdict
                }
            ))
        
        return errors
    
    def _validate_edge_context_display_logic(
        self,
        edge_context: Optional[Dict],
        classification: str,
        has_execution_constraints: bool
    ) -> List[ValidationError]:
        """
        RULE 2: Edge Context Notes display logic must be correct.
        
        DISPLAY RULES (ADDENDUM v1.0.2):
        - Shows when classification != EDGE
        - Shows when classification == EDGE AND execution_constraints non-empty
        - Hidden when classification == EDGE AND no execution_constraints
        
        CRITICAL if display logic violated.
        """
        errors = []
        
        # Determine if should be shown
        should_show = (
            classification != "EDGE" or
            has_execution_constraints
        )
        
        is_shown = edge_context is not None
        
        if should_show and not is_shown:
            errors.append(ValidationError(
                rule_id="EDGE_CONTEXT_HIDDEN_WHEN_SHOULD_SHOW",
                level=ValidationLevel.CRITICAL,
                message=(
                    f"Edge Context Notes hidden but should be shown "
                    f"(classification={classification}, constraints={has_execution_constraints})"
                ),
                affected_boxes=['edge_context'],
                context={
                    'classification': classification,
                    'has_execution_constraints': has_execution_constraints,
                    'should_show': True,
                    'is_shown': False
                }
            ))
        
        elif not should_show and is_shown:
            errors.append(ValidationError(
                rule_id="EDGE_CONTEXT_SHOWN_WHEN_SHOULD_HIDE",
                level=ValidationLevel.CRITICAL,
                message=(
                    f"Edge Context Notes shown but should be hidden "
                    f"(classification={classification}, constraints={has_execution_constraints})"
                ),
                affected_boxes=['edge_context'],
                context={
                    'classification': classification,
                    'has_execution_constraints': has_execution_constraints,
                    'should_show': False,
                    'is_shown': True
                }
            ))
        
        return errors
    
    def _validate_clv_framing(
        self,
        clv_forecast: Dict,
        classification: str
    ) -> List[ValidationError]:
        """
        RULE 3: CLV forecast framing must match classification.
        
        EXPECTATIONS:
        - NO_ACTION: "Informational only—no execution threshold met"
        - LEAN: "Movement insufficient to clear execution thresholds"
        - EDGE: "Market likely to incorporate mispricing"
        
        WARNING if framing inappropriate.
        """
        errors = []
        
        forecast_text = clv_forecast.get('forecast', '').lower()
        
        # Check for inappropriate framing
        if classification == "NO_ACTION":
            if "execution" in forecast_text and "threshold met" not in forecast_text:
                errors.append(ValidationError(
                    rule_id="CLV_FRAMING_INAPPROPRIATE_NO_ACTION",
                    level=ValidationLevel.WARNING,
                    message=(
                        "CLV forecast suggests execution possibility for NO_ACTION. "
                        "Should clarify 'no execution threshold met'."
                    ),
                    affected_boxes=['clv_forecast'],
                    context={'forecast': forecast_text}
                ))
        
        elif classification == "LEAN":
            if "execution" in forecast_text and "insufficient" not in forecast_text:
                errors.append(ValidationError(
                    rule_id="CLV_FRAMING_INAPPROPRIATE_LEAN",
                    level=ValidationLevel.WARNING,
                    message=(
                        "CLV forecast doesn't clarify execution insufficiency for LEAN. "
                        "Should mention 'insufficient to clear execution thresholds'."
                    ),
                    affected_boxes=['clv_forecast'],
                    context={'forecast': forecast_text}
                ))
        
        elif classification == "EDGE":
            if "insufficient" in forecast_text or "threshold not met" in forecast_text:
                errors.append(ValidationError(
                    rule_id="CLV_FRAMING_INAPPROPRIATE_EDGE",
                    level=ValidationLevel.WARNING,
                    message=(
                        "CLV forecast suggests execution insufficiency for EDGE. "
                        "Contradicts EDGE classification."
                    ),
                    affected_boxes=['clv_forecast'],
                    context={'forecast': forecast_text}
                ))
        
        return errors
    
    def _validate_global_context_alignment(
        self,
        why_edge_exists: Dict,
        final_summary: Dict,
        classification: str
    ) -> List[ValidationError]:
        """
        RULE 4: Global context must align with verdict.
        
        EXPECTATIONS:
        - NO_ACTION: "No statistically significant edge detected"
        - LEAN: "Directional bias identified, but global edge criteria not satisfied"
        - EDGE: "Localized mispricing detected relative to global distribution"
        
        WARNING if misalignment detected.
        """
        errors = []
        
        global_context = why_edge_exists.get('global_context', {})
        global_statement = global_context.get('statement', '').lower()
        
        # Check alignment
        if classification == "NO_ACTION":
            if "edge detected" in global_statement and "no" not in global_statement[:20]:
                errors.append(ValidationError(
                    rule_id="GLOBAL_CONTEXT_MISALIGNED_NO_ACTION",
                    level=ValidationLevel.WARNING,
                    message=(
                        "Global context suggests edge detection for NO_ACTION. "
                        "Should clarify 'No edge detected'."
                    ),
                    affected_boxes=['why_edge_exists', 'final_summary'],
                    context={'global_statement': global_statement}
                ))
        
        elif classification == "LEAN":
            if "mispricing" in global_statement:
                errors.append(ValidationError(
                    rule_id="GLOBAL_CONTEXT_MISALIGNED_LEAN",
                    level=ValidationLevel.WARNING,
                    message=(
                        "Global context mentions 'mispricing' for LEAN. "
                        "LEAN does not qualify as mispricing (insufficient edge)."
                    ),
                    affected_boxes=['why_edge_exists', 'final_summary'],
                    context={'global_statement': global_statement}
                ))
        
        elif classification == "EDGE":
            if "no edge" in global_statement or "insufficient" in global_statement:
                errors.append(ValidationError(
                    rule_id="GLOBAL_CONTEXT_MISALIGNED_EDGE",
                    level=ValidationLevel.CRITICAL,
                    message=(
                        "Global context suggests no edge for EDGE classification. "
                        "Critical contradiction."
                    ),
                    affected_boxes=['why_edge_exists', 'final_summary'],
                    context={'global_statement': global_statement}
                ))
        
        return errors
    
    def _validate_no_implied_action(
        self,
        key_drivers: Dict,
        edge_context: Optional[Dict],
        edge_summary: Dict,
        clv_forecast: Dict,
        why_edge_exists: Dict,
        final_summary: Dict,
        classification: str
    ) -> List[ValidationError]:
        """
        RULE 5: No implied action when NO_ACTION.
        
        FORBIDDEN when NO_ACTION:
        - "should bet", "recommend", "take this"
        - "execution", "actionable" (unless prefixed with "not" or "no")
        - "opportunity", "value" (unless context is "no opportunity")
        
        CRITICAL if action language detected in NO_ACTION.
        """
        errors = []
        
        if classification != "NO_ACTION":
            return errors  # Only applies to NO_ACTION
        
        # Action keywords to check
        action_keywords = [
            ('should bet', 'direct betting recommendation'),
            ('recommend', 'recommendation language'),
            ('take this', 'direct action suggestion'),
            ('play this', 'direct action suggestion'),
            ('go with', 'directional recommendation'),
        ]
        
        # Check all boxes for action language
        all_text = {
            'key_drivers': ' '.join(key_drivers.get('items', [])),
            'edge_context': ' '.join(edge_context.get('notes', [])) if edge_context else '',
            'edge_summary': edge_summary.get('text', ''),
            'clv_forecast': clv_forecast.get('forecast', ''),
            'why_edge_exists': why_edge_exists.get('global_context', {}).get('statement', ''),
            'final_summary': final_summary.get('summary', '')
        }
        
        for box_name, text in all_text.items():
            if not text:
                continue
            
            text_lower = text.lower()
            
            for keyword, description in action_keywords:
                if keyword in text_lower:
                    # Check if negated (e.g., "not recommended", "no execution")
                    negation_words = ['not', 'no', 'never', 'without']
                    is_negated = any(
                        neg in text_lower[:text_lower.index(keyword)][-20:]
                        for neg in negation_words
                        if keyword in text_lower
                    )
                    
                    if not is_negated:
                        errors.append(ValidationError(
                            rule_id="IMPLIED_ACTION_IN_NO_ACTION",
                            level=ValidationLevel.CRITICAL,
                            message=(
                                f"Action language detected in {box_name} for NO_ACTION: '{keyword}' "
                                f"({description}). This contradicts NO_ACTION verdict."
                            ),
                            affected_boxes=[box_name],
                            context={
                                'keyword': keyword,
                                'box': box_name,
                                'text': text[:200]  # First 200 chars for context
                            }
                        ))
        
        return errors
    
    # ==================== HELPER METHODS ====================
    
    def validate_single_box(
        self,
        box_name: str,
        box_content: Dict,
        classification: str,
        has_execution_constraints: bool = False
    ) -> Tuple[bool, List[ValidationError]]:
        """
        Validate a single box in isolation.
        
        Useful for incremental validation during rendering.
        """
        errors = []
        
        # Box-specific validation rules
        if box_name == "key_drivers":
            errors.extend(self._validate_key_drivers(box_content))
        elif box_name == "edge_context":
            errors.extend(self._validate_edge_context(box_content, classification, has_execution_constraints))
        elif box_name == "edge_summary":
            errors.extend(self._validate_edge_summary(box_content, classification))
        elif box_name == "clv_forecast":
            errors.extend(self._validate_clv_forecast(box_content, classification))
        elif box_name == "why_edge_exists":
            errors.extend(self._validate_why_edge_exists(box_content, classification))
        elif box_name == "final_summary":
            errors.extend(self._validate_final_summary(box_content, classification))
        
        critical_errors = [e for e in errors if e.level == ValidationLevel.CRITICAL]
        is_valid = len(critical_errors) == 0
        
        return is_valid, errors
    
    def _validate_key_drivers(self, box_content: Dict) -> List[ValidationError]:
        """Validate Key Drivers box"""
        errors = []
        
        items = box_content.get('items', [])
        if not items:
            errors.append(ValidationError(
                rule_id="KEY_DRIVERS_EMPTY",
                level=ValidationLevel.INFO,
                message="Key Drivers has no items. Consider adding simulation metadata.",
                affected_boxes=['key_drivers']
            ))
        
        return errors
    
    def _validate_edge_context(
        self,
        box_content: Dict,
        classification: str,
        has_execution_constraints: bool
    ) -> List[ValidationError]:
        """Validate Edge Context Notes box"""
        errors = []
        
        notes = box_content.get('notes', [])
        if not notes:
            errors.append(ValidationError(
                rule_id="EDGE_CONTEXT_EMPTY",
                level=ValidationLevel.WARNING,
                message="Edge Context Notes shown but has no notes. Should explain why.",
                affected_boxes=['edge_context']
            ))
        
        return errors
    
    def _validate_edge_summary(
        self,
        box_content: Dict,
        classification: str
    ) -> List[ValidationError]:
        """Validate Edge Summary box"""
        errors = []
        
        box_classification = box_content.get('classification', '')
        if box_classification != classification:
            errors.append(ValidationError(
                rule_id="EDGE_SUMMARY_CLASSIFICATION_MISMATCH",
                level=ValidationLevel.CRITICAL,
                message=(
                    f"Edge Summary classification ({box_classification}) does not match "
                    f"expected classification ({classification})"
                ),
                affected_boxes=['edge_summary'],
                context={
                    'box_classification': box_classification,
                    'expected': classification
                }
            ))
        
        return errors
    
    def _validate_clv_forecast(
        self,
        box_content: Dict,
        classification: str
    ) -> List[ValidationError]:
        """Validate CLV Forecast box"""
        errors = []
        
        forecast = box_content.get('forecast', '')
        if not forecast:
            errors.append(ValidationError(
                rule_id="CLV_FORECAST_EMPTY",
                level=ValidationLevel.WARNING,
                message="CLV Forecast is empty. Should provide market movement context.",
                affected_boxes=['clv_forecast']
            ))
        
        return errors
    
    def _validate_why_edge_exists(
        self,
        box_content: Dict,
        classification: str
    ) -> List[ValidationError]:
        """Validate Why This Edge Exists box"""
        errors = []
        
        global_context = box_content.get('global_context', {})
        if not global_context:
            errors.append(ValidationError(
                rule_id="WHY_EDGE_GLOBAL_CONTEXT_MISSING",
                level=ValidationLevel.CRITICAL,
                message="Why This Edge Exists missing global context. Critical for trust.",
                affected_boxes=['why_edge_exists']
            ))
        
        return errors
    
    def _validate_final_summary(
        self,
        box_content: Dict,
        classification: str
    ) -> List[ValidationError]:
        """Validate Final Unified Summary box"""
        errors = []
        
        verdict = box_content.get('verdict', '')
        if not verdict:
            errors.append(ValidationError(
                rule_id="FINAL_SUMMARY_NO_VERDICT",
                level=ValidationLevel.CRITICAL,
                message="Final Unified Summary missing verdict.",
                affected_boxes=['final_summary']
            ))
        
        summary = box_content.get('summary', '')
        if not summary:
            errors.append(ValidationError(
                rule_id="FINAL_SUMMARY_EMPTY",
                level=ValidationLevel.CRITICAL,
                message="Final Unified Summary text is empty.",
                affected_boxes=['final_summary']
            ))
        
        return errors


# ==================== EXPORTS ====================

def validate_explanation_consistency(
    key_drivers: Dict,
    edge_context: Optional[Dict],
    edge_summary: Dict,
    clv_forecast: Dict,
    why_edge_exists: Dict,
    final_summary: Dict,
    classification: str,
    has_execution_constraints: bool
) -> Tuple[bool, List[ValidationError]]:
    """
    Convenience function to validate consistency across all boxes.
    
    Usage:
        is_valid, errors = validate_explanation_consistency(
            key_drivers=drivers_box,
            edge_context=context_box,  # None if hidden
            edge_summary=summary_box,
            clv_forecast=clv_box,
            why_edge_exists=why_box,
            final_summary=final_box,
            classification="EDGE",
            has_execution_constraints=False
        )
        
        if not is_valid:
            for error in errors:
                if error.level == ValidationLevel.CRITICAL:
                    print(f"CRITICAL: {error.message}")
    """
    validator = ExplanationConsistencyValidator()
    return validator.validate_all(
        key_drivers, edge_context, edge_summary, clv_forecast,
        why_edge_exists, final_summary, classification, has_execution_constraints
    )


if __name__ == "__main__":
    print("=== Explanation Consistency Validator Tests ===\n")
    
    validator = ExplanationConsistencyValidator()
    
    # Test 1: Verdict mismatch (CRITICAL)
    print("Test 1: Verdict Mismatch")
    is_valid, errors = validator.validate_all(
        key_drivers={'items': []},
        edge_context=None,
        edge_summary={'classification': 'EDGE', 'text': 'Edge detected'},
        clv_forecast={'forecast': 'Movement expected'},
        why_edge_exists={'global_context': {'statement': 'Edge detected'}},
        final_summary={'verdict': 'LEAN', 'summary': 'Lean verdict'},  # MISMATCH
        classification='EDGE',
        has_execution_constraints=False
    )
    print(f"Valid: {is_valid}")
    print(f"Errors: {[e.rule_id for e in errors]}")
    assert not is_valid
    assert any(e.rule_id == "VERDICT_MISMATCH" for e in errors)
    print("✅ Verdict mismatch test passed\n")
    
    # Test 2: Edge Context display logic violation
    print("Test 2: Edge Context Display Logic (should show for NO_ACTION)")
    is_valid, errors = validator.validate_all(
        key_drivers={'items': []},
        edge_context=None,  # Hidden
        edge_summary={'classification': 'NO_ACTION', 'text': 'No action'},
        clv_forecast={'forecast': 'Movement expected'},
        why_edge_exists={'global_context': {'statement': 'No edge'}},
        final_summary={'verdict': 'NO_ACTION', 'summary': 'No action'},
        classification='NO_ACTION',
        has_execution_constraints=False
    )
    print(f"Valid: {is_valid}")
    print(f"Errors: {[e.rule_id for e in errors]}")
    assert not is_valid
    assert any("EDGE_CONTEXT_HIDDEN" in e.rule_id for e in errors)
    print("✅ Edge Context display logic test passed\n")
    
    # Test 3: Implied action in NO_ACTION (CRITICAL)
    print("Test 3: Implied Action in NO_ACTION")
    is_valid, errors = validator.validate_all(
        key_drivers={'items': []},
        edge_context={'notes': ['No edge detected']},
        edge_summary={'classification': 'NO_ACTION', 'text': 'You should bet on this!'},  # VIOLATION
        clv_forecast={'forecast': 'Movement expected'},
        why_edge_exists={'global_context': {'statement': 'No edge'}},
        final_summary={'verdict': 'NO_ACTION', 'summary': 'No action'},
        classification='NO_ACTION',
        has_execution_constraints=False
    )
    print(f"Valid: {is_valid}")
    print(f"Errors: {[e.rule_id for e in errors]}")
    assert not is_valid
    assert any(e.rule_id == "IMPLIED_ACTION_IN_NO_ACTION" for e in errors)
    print("✅ Implied action test passed\n")
    
    # Test 4: Clean EDGE (should pass all validations)
    print("Test 4: Clean EDGE (Valid)")
    is_valid, errors = validator.validate_all(
        key_drivers={'items': ['Pace differential: faster by 3.2 possessions']},
        edge_context=None,  # Hidden for clean EDGE
        edge_summary={'classification': 'EDGE', 'text': 'Edge detected at 4.2% EV. All risk controls passed.'},
        clv_forecast={'forecast': 'Moderate movement toward sharp side expected.'},
        why_edge_exists={'global_context': {'statement': 'Localized mispricing detected'}},
        final_summary={'verdict': 'EDGE', 'summary': 'Edge identified.'},
        classification='EDGE',
        has_execution_constraints=False
    )
    print(f"Valid: {is_valid}")
    print(f"Errors: {[e.rule_id for e in errors]}")
    assert is_valid
    print("✅ Clean EDGE test passed\n")
    
    print("=== All Consistency Validator Tests Passed ===")
