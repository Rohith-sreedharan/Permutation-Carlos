"""
Forbidden Phrases Checker v1.0.2
Status: LOCKED FOR IMPLEMENTATION
Package: 2.5 – Decision Explanation & Transparency

Context-aware forbidden phrase detection for UI explanation layer.

LOCKED RULES:
- Absolute forbidden phrases (ALWAYS blocked regardless of context)
- Context-dependent forbidden phrases (blocked based on classification/state)
- Tone violations (blocked based on language patterns)
- Case-insensitive matching
- Partial match support (substring detection)

PURPOSE: Prevent regulatory/legal risk, maintain institutional voice, avoid misleading language
"""

from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import re


class ViolationType(str, Enum):
    """Types of phrase violations"""
    ABSOLUTE_FORBIDDEN = "ABSOLUTE_FORBIDDEN"  # Never allowed
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"    # Depends on classification/state
    TONE_VIOLATION = "TONE_VIOLATION"          # Violates institutional voice
    ACTION_LANGUAGE = "ACTION_LANGUAGE"        # Implied action when NO_ACTION


@dataclass
class ForbiddenPhrase:
    """Forbidden phrase definition"""
    phrase: str
    violation_type: ViolationType
    context_constraint: Optional[str] = None  # e.g., "when_no_action", "when_lean"
    reason: Optional[str] = None


# ==================== ABSOLUTE FORBIDDEN PHRASES ====================

ABSOLUTE_FORBIDDEN = [
    # Guarantees and certainties
    ForbiddenPhrase("guaranteed", ViolationType.ABSOLUTE_FORBIDDEN, reason="No betting outcomes are guaranteed"),
    ForbiddenPhrase("guarantee", ViolationType.ABSOLUTE_FORBIDDEN, reason="No betting outcomes are guaranteed"),
    ForbiddenPhrase("can't lose", ViolationType.ABSOLUTE_FORBIDDEN, reason="All bets carry risk"),
    ForbiddenPhrase("sure thing", ViolationType.ABSOLUTE_FORBIDDEN, reason="No outcomes are certain"),
    ForbiddenPhrase("lock", ViolationType.ABSOLUTE_FORBIDDEN, reason="Implies certainty"),
    ForbiddenPhrase("mortal lock", ViolationType.ABSOLUTE_FORBIDDEN, reason="Implies certainty"),
    ForbiddenPhrase("100%", ViolationType.ABSOLUTE_FORBIDDEN, reason="No prediction is 100%"),
    
    # Financial promises
    ForbiddenPhrase("guaranteed profit", ViolationType.ABSOLUTE_FORBIDDEN, reason="Cannot guarantee profit"),
    ForbiddenPhrase("risk-free", ViolationType.ABSOLUTE_FORBIDDEN, reason="All bets carry risk"),
    ForbiddenPhrase("free money", ViolationType.ABSOLUTE_FORBIDDEN, reason="Misleading financial promise"),
    
    # Urgency/pressure tactics
    ForbiddenPhrase("must bet", ViolationType.ABSOLUTE_FORBIDDEN, reason="Coercive language"),
    ForbiddenPhrase("bet now", ViolationType.ABSOLUTE_FORBIDDEN, reason="Pressure tactic"),
    ForbiddenPhrase("last chance", ViolationType.ABSOLUTE_FORBIDDEN, reason="False urgency"),
    ForbiddenPhrase("don't miss", ViolationType.ABSOLUTE_FORBIDDEN, reason="Pressure tactic"),
    ForbiddenPhrase("limited time", ViolationType.ABSOLUTE_FORBIDDEN, reason="False urgency"),
    
    # Recovery promises (gambling addiction triggers)
    ForbiddenPhrase("get it back", ViolationType.ABSOLUTE_FORBIDDEN, reason="Triggers loss-chasing"),
    ForbiddenPhrase("make up for", ViolationType.ABSOLUTE_FORBIDDEN, reason="Triggers loss-chasing"),
    ForbiddenPhrase("recoup losses", ViolationType.ABSOLUTE_FORBIDDEN, reason="Triggers loss-chasing"),
    
    # Insider language
    ForbiddenPhrase("inside information", ViolationType.ABSOLUTE_FORBIDDEN, reason="Implies illegal activity"),
    ForbiddenPhrase("insider tip", ViolationType.ABSOLUTE_FORBIDDEN, reason="Implies illegal activity"),
    ForbiddenPhrase("fix is in", ViolationType.ABSOLUTE_FORBIDDEN, reason="Implies game manipulation"),
    
    # Skill exaggeration
    ForbiddenPhrase("can't miss", ViolationType.ABSOLUTE_FORBIDDEN, reason="Implies certainty"),
    ForbiddenPhrase("always wins", ViolationType.ABSOLUTE_FORBIDDEN, reason="Impossible claim"),
    ForbiddenPhrase("never loses", ViolationType.ABSOLUTE_FORBIDDEN, reason="Impossible claim"),
]


# ==================== CONTEXT-DEPENDENT FORBIDDEN PHRASES ====================

CONTEXT_DEPENDENT_FORBIDDEN = [
    # Action language when NO_ACTION
    ForbiddenPhrase(
        "should bet", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_no_action",
        reason="Contradicts NO_ACTION verdict"
    ),
    ForbiddenPhrase(
        "recommend betting", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_no_action",
        reason="Contradicts NO_ACTION verdict"
    ),
    ForbiddenPhrase(
        "take this", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_no_action",
        reason="Contradicts NO_ACTION verdict"
    ),
    ForbiddenPhrase(
        "play this", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_no_action",
        reason="Contradicts NO_ACTION verdict"
    ),
    ForbiddenPhrase(
        "go with", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_no_action",
        reason="Contradicts NO_ACTION verdict"
    ),
    
    # Strong confidence language when LEAN
    ForbiddenPhrase(
        "strong edge", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_lean",
        reason="LEAN does not qualify as strong edge"
    ),
    ForbiddenPhrase(
        "high confidence", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_lean",
        reason="LEAN does not qualify as high confidence"
    ),
    ForbiddenPhrase(
        "significant edge", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_lean",
        reason="LEAN does not qualify as significant edge"
    ),
    ForbiddenPhrase(
        "clear edge", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_lean",
        reason="LEAN does not qualify as clear edge"
    ),
    
    # Execution language when constraints exist
    ForbiddenPhrase(
        "all risk controls passed", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_execution_constraints",
        reason="Contradicts presence of constraints"
    ),
    ForbiddenPhrase(
        "all systems go", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_execution_constraints",
        reason="Contradicts presence of constraints"
    ),
    ForbiddenPhrase(
        "ready for execution", ViolationType.CONTEXT_DEPENDENT,
        context_constraint="when_execution_constraints",
        reason="Contradicts presence of constraints"
    ),
]


# ==================== TONE VIOLATIONS ====================

TONE_VIOLATIONS = [
    # Hype language
    ForbiddenPhrase("🔥", ViolationType.TONE_VIOLATION, reason="Informal/hype emoji"),
    ForbiddenPhrase("fire", ViolationType.TONE_VIOLATION, reason="Slang/hype language"),
    ForbiddenPhrase("smash", ViolationType.TONE_VIOLATION, reason="Informal action verb"),
    ForbiddenPhrase("crush", ViolationType.TONE_VIOLATION, reason="Informal action verb"),
    ForbiddenPhrase("hammer", ViolationType.TONE_VIOLATION, reason="Informal action verb"),
    ForbiddenPhrase("pound", ViolationType.TONE_VIOLATION, reason="Informal action verb"),
    
    # Casual language
    ForbiddenPhrase("ez money", ViolationType.TONE_VIOLATION, reason="Casual slang"),
    ForbiddenPhrase("easy money", ViolationType.TONE_VIOLATION, reason="Misleading simplification"),
    ForbiddenPhrase("no brainer", ViolationType.TONE_VIOLATION, reason="Trivializes analysis"),
    ForbiddenPhrase("slam dunk", ViolationType.TONE_VIOLATION, reason="Informal certainty"),
    
    # Emotional appeals
    ForbiddenPhrase("trust me", ViolationType.TONE_VIOLATION, reason="Emotional manipulation"),
    ForbiddenPhrase("believe me", ViolationType.TONE_VIOLATION, reason="Emotional manipulation"),
    ForbiddenPhrase("you'll thank me", ViolationType.TONE_VIOLATION, reason="Presumptive language"),
    
    # Entertainment language
    ForbiddenPhrase("let's go", ViolationType.TONE_VIOLATION, reason="Cheerleading tone"),
    ForbiddenPhrase("boom", ViolationType.TONE_VIOLATION, reason="Exclamatory hype"),
    ForbiddenPhrase("lfg", ViolationType.TONE_VIOLATION, reason="Casual slang"),
]


# ==================== ALLOWED EXCEPTIONS (EDGE CONTEXT NOTES) ====================

EDGE_CONTEXT_NOTES_ALLOWED = {
    # These phrases ARE allowed specifically in Edge Context Notes box
    # when explaining constraints for EDGE classification
    "all risk controls passed": "allowed_in_clean_edge_summary",  # Edge Summary only, when no constraints
}


# ==================== FORBIDDEN PHRASES CHECKER ====================

class ForbiddenPhrasesChecker:
    """
    Context-aware forbidden phrase detection.
    
    Checks for:
    1. Absolute forbidden phrases (always blocked)
    2. Context-dependent forbidden (blocked based on classification/state)
    3. Tone violations (blocked based on institutional voice)
    """
    
    def __init__(self):
        self.absolute_forbidden = ABSOLUTE_FORBIDDEN
        self.context_dependent = CONTEXT_DEPENDENT_FORBIDDEN
        self.tone_violations = TONE_VIOLATIONS
    
    def check_text(
        self,
        text: str,
        classification: str,
        has_execution_constraints: bool = False,
        box_name: Optional[str] = None
    ) -> Tuple[bool, List[Dict]]:
        """
        Check text for forbidden phrases.
        
        Args:
            text: Text to check
            classification: Classification enum value (NO_ACTION, LEAN, EDGE)
            has_execution_constraints: Whether execution constraints exist
            box_name: Name of explanation box (for context-aware exceptions)
        
        Returns:
            (is_valid, violations) where violations is list of dicts with:
                - phrase: The forbidden phrase detected
                - violation_type: Type of violation
                - reason: Why it's forbidden
                - context: Context that made it forbidden (if context-dependent)
        """
        violations = []
        text_lower = text.lower()
        
        # Check absolute forbidden phrases
        for forbidden in self.absolute_forbidden:
            if self._phrase_matches(forbidden.phrase, text_lower):
                violations.append({
                    'phrase': forbidden.phrase,
                    'violation_type': forbidden.violation_type.value,
                    'reason': forbidden.reason,
                    'context': None
                })
        
        # Check context-dependent forbidden phrases
        for forbidden in self.context_dependent:
            if self._should_check_context_dependent(
                forbidden, classification, has_execution_constraints
            ):
                if self._phrase_matches(forbidden.phrase, text_lower):
                    # Check for allowed exceptions
                    if self._is_allowed_exception(forbidden.phrase, box_name, classification, has_execution_constraints):
                        continue
                    
                    violations.append({
                        'phrase': forbidden.phrase,
                        'violation_type': forbidden.violation_type.value,
                        'reason': forbidden.reason,
                        'context': forbidden.context_constraint
                    })
        
        # Check tone violations
        for forbidden in self.tone_violations:
            if self._phrase_matches(forbidden.phrase, text_lower):
                violations.append({
                    'phrase': forbidden.phrase,
                    'violation_type': forbidden.violation_type.value,
                    'reason': forbidden.reason,
                    'context': None
                })
        
        is_valid = len(violations) == 0
        return is_valid, violations
    
    def _phrase_matches(self, phrase: str, text: str) -> bool:
        """
        Check if phrase matches text (case-insensitive substring match).
        Uses word boundary matching to avoid false positives.
        """
        # Escape special regex characters
        pattern = re.escape(phrase.lower())
        
        # Add word boundaries if phrase is alphanumeric
        if phrase.replace(' ', '').isalnum():
            pattern = r'\b' + pattern + r'\b'
        
        return bool(re.search(pattern, text))
    
    def _should_check_context_dependent(
        self,
        forbidden: ForbiddenPhrase,
        classification: str,
        has_execution_constraints: bool
    ) -> bool:
        """Determine if context-dependent phrase should be checked based on context."""
        constraint = forbidden.context_constraint
        
        if constraint == "when_no_action":
            return classification == "NO_ACTION"
        elif constraint == "when_lean":
            return classification == "LEAN"
        elif constraint == "when_execution_constraints":
            return has_execution_constraints
        else:
            return True
    
    def _is_allowed_exception(
        self,
        phrase: str,
        box_name: Optional[str],
        classification: str,
        has_execution_constraints: bool
    ) -> bool:
        """Check if phrase is an allowed exception in specific context."""
        # "all risk controls passed" is allowed ONLY in Edge Summary for clean EDGE
        if phrase == "all risk controls passed":
            return (
                box_name == "edge_summary" and
                classification == "EDGE" and
                not has_execution_constraints
            )
        
        return False
    
    def get_all_forbidden_phrases(self) -> List[str]:
        """Get list of all forbidden phrases for reference."""
        all_phrases = []
        
        for forbidden in self.absolute_forbidden:
            all_phrases.append(forbidden.phrase)
        for forbidden in self.context_dependent:
            all_phrases.append(forbidden.phrase)
        for forbidden in self.tone_violations:
            all_phrases.append(forbidden.phrase)
        
        return sorted(set(all_phrases))


# ==================== ACTION LANGUAGE DETECTOR ====================

def is_action_language_safe(text: str, classification: str) -> Tuple[bool, List[str]]:
    """
    Detect action language that implies betting recommendation.
    
    This is a stricter check than forbidden phrases - it detects ANY action language
    when classification is NO_ACTION.
    
    Returns:
        (is_safe, detected_phrases)
    """
    if classification != "NO_ACTION":
        # Action language is acceptable for LEAN (with caution) and EDGE
        return True, []
    
    # Action verbs that imply betting (when NO_ACTION)
    action_verbs = [
        r'\bbet\b',
        r'\bplay\b',
        r'\btake\b',
        r'\bback\b',
        r'\bfade\b',
        r'\bhammer\b',
        r'\bpound\b',
        r'\bsmash\b',
        r'\bgo\s+with\b',
        r'\bshould\s+bet\b',
        r'\brecommend\b',
        r'\badvise\b',
    ]
    
    detected = []
    text_lower = text.lower()
    
    for verb_pattern in action_verbs:
        if re.search(verb_pattern, text_lower):
            detected.append(verb_pattern.replace(r'\b', '').replace(r'\s+', ' '))
    
    is_safe = len(detected) == 0
    return is_safe, detected


# ==================== EXPORTS ====================

def check_forbidden_phrases(
    text: str,
    classification: str,
    has_execution_constraints: bool = False,
    box_name: Optional[str] = None
) -> Tuple[bool, List[Dict]]:
    """
    Convenience function to check forbidden phrases.
    
    Usage:
        is_valid, violations = check_forbidden_phrases(
            text="This is a guaranteed win!",
            classification="EDGE",
            has_execution_constraints=False,
            box_name="edge_summary"
        )
        
        if not is_valid:
            for violation in violations:
                print(f"Forbidden phrase detected: {violation['phrase']}")
                print(f"Reason: {violation['reason']}")
    """
    checker = ForbiddenPhrasesChecker()
    return checker.check_text(text, classification, has_execution_constraints, box_name)


if __name__ == "__main__":
    print("=== Forbidden Phrases Checker Tests ===\n")
    
    checker = ForbiddenPhrasesChecker()
    
    # Test 1: Absolute forbidden
    print("Test 1: Absolute Forbidden Phrases")
    is_valid, violations = checker.check_text(
        text="This is a guaranteed profit opportunity!",
        classification="EDGE",
        has_execution_constraints=False
    )
    print(f"Text: 'This is a guaranteed profit opportunity!'")
    print(f"Valid: {is_valid}")
    print(f"Violations: {[v['phrase'] for v in violations]}")
    assert not is_valid
    assert len(violations) == 2  # 'guaranteed' and 'guaranteed profit'
    print("✅ Absolute forbidden test passed\n")
    
    # Test 2: Context-dependent (action language when NO_ACTION)
    print("Test 2: Context-Dependent Forbidden (NO_ACTION)")
    is_valid, violations = checker.check_text(
        text="You should bet on this opportunity.",
        classification="NO_ACTION",
        has_execution_constraints=False
    )
    print(f"Text: 'You should bet on this opportunity.'")
    print(f"Classification: NO_ACTION")
    print(f"Valid: {is_valid}")
    print(f"Violations: {[v['phrase'] for v in violations]}")
    assert not is_valid
    assert any('should bet' in v['phrase'] for v in violations)
    print("✅ Context-dependent (NO_ACTION) test passed\n")
    
    # Test 3: Context-dependent (strong edge when LEAN)
    print("Test 3: Context-Dependent Forbidden (LEAN)")
    is_valid, violations = checker.check_text(
        text="This is a strong edge opportunity.",
        classification="LEAN",
        has_execution_constraints=False
    )
    print(f"Text: 'This is a strong edge opportunity.'")
    print(f"Classification: LEAN")
    print(f"Valid: {is_valid}")
    print(f"Violations: {[v['phrase'] for v in violations]}")
    assert not is_valid
    assert any('strong edge' in v['phrase'] for v in violations)
    print("✅ Context-dependent (LEAN) test passed\n")
    
    # Test 4: Allowed exception (all risk controls passed for clean EDGE)
    print("Test 4: Allowed Exception (Clean EDGE)")
    is_valid, violations = checker.check_text(
        text="All risk controls passed.",
        classification="EDGE",
        has_execution_constraints=False,
        box_name="edge_summary"
    )
    print(f"Text: 'All risk controls passed.'")
    print(f"Classification: EDGE, Constraints: False, Box: edge_summary")
    print(f"Valid: {is_valid}")
    assert is_valid  # Should be allowed
    print("✅ Allowed exception test passed\n")
    
    # Test 5: Forbidden exception (all risk controls passed with constraints)
    print("Test 5: Forbidden (EDGE with Constraints)")
    is_valid, violations = checker.check_text(
        text="All risk controls passed.",
        classification="EDGE",
        has_execution_constraints=True,
        box_name="edge_summary"
    )
    print(f"Text: 'All risk controls passed.'")
    print(f"Classification: EDGE, Constraints: True, Box: edge_summary")
    print(f"Valid: {is_valid}")
    print(f"Violations: {[v['phrase'] for v in violations]}")
    assert not is_valid  # Should be forbidden
    print("✅ Forbidden exception test passed\n")
    
    # Test 6: Tone violations
    print("Test 6: Tone Violations")
    is_valid, violations = checker.check_text(
        text="This is easy money, let's go! 🔥",
        classification="EDGE",
        has_execution_constraints=False
    )
    print(f"Text: 'This is easy money, let's go! 🔥'")
    print(f"Valid: {is_valid}")
    print(f"Violations: {[v['phrase'] for v in violations]}")
    assert not is_valid
    assert len(violations) >= 3  # easy money, let's go, 🔥
    print("✅ Tone violations test passed\n")
    
    # Test 7: Action language detector
    print("Test 7: Action Language Detector")
    is_safe, detected = is_action_language_safe(
        text="You should bet on the home team.",
        classification="NO_ACTION"
    )
    print(f"Text: 'You should bet on the home team.'")
    print(f"Classification: NO_ACTION")
    print(f"Safe: {is_safe}")
    print(f"Detected: {detected}")
    assert not is_safe
    print("✅ Action language detector test passed\n")
    
    # Test 8: Clean text
    print("Test 8: Clean Text")
    is_valid, violations = checker.check_text(
        text="Model projections diverge from market consensus by statistically significant margin.",
        classification="EDGE",
        has_execution_constraints=False
    )
    print(f"Text: 'Model projections diverge from market consensus...'")
    print(f"Valid: {is_valid}")
    assert is_valid
    print("✅ Clean text test passed\n")
    
    print("=== All Forbidden Phrases Tests Passed ===")
