"""
Content Moderation Service
Enforces "Insights, Not Bets" compliance rule (PDF Page 3)
Blocks prohibited betting language from creator submissions
"""
import re
from typing import Tuple, List, Optional
from legacy_config import PROHIBITED_TERMS, APPROVED_TERMS, COMPLIANCE_ERROR_MSG


class ModerationService:
    """
    Regex-based content filter for creator submissions
    Ensures legal compliance: BeatVegas sells analysis, not bets
    """
    
    def __init__(self):
        # Compile regex patterns for performance
        # Word boundary matching to avoid false positives (e.g., "debate" contains "bet")
        self.prohibited_patterns = [
            re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            for term in PROHIBITED_TERMS
        ]
    
    def check_content(self, content: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Check if content contains prohibited terms
        
        Args:
            content: User-submitted text (post, comment, forecast, etc.)
        
        Returns:
            Tuple of (is_compliant, error_message, found_violations)
            - is_compliant: True if content passes, False if blocked
            - error_message: Compliance error message if blocked
            - found_violations: List of prohibited terms found in content
        """
        if not content:
            return True, None, []
        
        violations = []
        
        # Check each prohibited pattern
        for pattern in self.prohibited_patterns:
            matches = pattern.findall(content)
            if matches:
                violations.extend(matches)
        
        # Remove duplicates and convert to lowercase
        violations = list(set([v.lower() for v in violations]))
        
        if violations:
            error_detail = f"{COMPLIANCE_ERROR_MSG}\n\nFound prohibited terms: {', '.join(violations)}"
            return False, error_detail, violations
        
        return True, None, []
    
    def get_suggestions(self) -> List[str]:
        """
        Return list of approved alternative terms
        Helps creators rephrase their content compliantly
        """
        return APPROVED_TERMS
    
    def auto_suggest_replacement(self, content: str) -> str:
        """
        Attempt to auto-replace prohibited terms with approved alternatives
        
        Simple mapping:
        - "bet" -> "forecast"
        - "wager" -> "projection"
        - "lock" -> "high-confidence insight"
        - "guaranteed win" -> "strong expectation"
        - "units" -> "confidence level"
        """
        replacement_map = {
            r'\bbet\b': 'forecast',
            r'\bbets\b': 'forecasts',
            r'\bbetting\b': 'analyzing',
            r'\bwager\b': 'projection',
            r'\bwagers\b': 'projections',
            r'\bwagering\b': 'projecting',
            r'\block\b': 'high-confidence insight',
            r'\blocks\b': 'high-confidence insights',
            r'\bguaranteed win\b': 'strong positive expectation',
            r'\bguaranteed\b': 'high confidence',
            r'\bsure thing\b': 'strong edge',
            r'\bcan\'t lose\b': 'favorable outlook',
            r'\bunits\b': 'confidence level',
            r'\bunit\b': 'confidence',
            r'\bput money on\b': 'view as valuable',
            r'\bcash out\b': 'realize value',
            r'\bwinnings\b': 'analytical performance',
            r'\bpayout\b': 'expected value',
            r'\bstake\b': 'exposure',
            r'\bstakes\b': 'exposure',
            r'\bbookie\b': 'market',
            r'\bbookies\b': 'markets',
        }
        
        suggested_content = content
        for pattern, replacement in replacement_map.items():
            suggested_content = re.sub(pattern, replacement, suggested_content, flags=re.IGNORECASE)
        
        return suggested_content


# Singleton instance
moderation = ModerationService()


def validate_content(content: str) -> Tuple[bool, Optional[str], List[str]]:
    """
    Convenience function for content validation
    
    Usage:
        is_valid, error_msg, violations = validate_content(user_post)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
    """
    return moderation.check_content(content)


def suggest_compliant_version(content: str) -> str:
    """
    Generate a compliance-friendly version of the content
    """
    return moderation.auto_suggest_replacement(content)


def get_approved_terms() -> List[str]:
    """
    Get list of approved alternative terms for creator guidance
    """
    return moderation.get_suggestions()
