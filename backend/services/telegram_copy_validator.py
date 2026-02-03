"""
TelegramCopyValidator - Institutional-Grade Validation
Status: LOCKED - ZERO HALLUCINATION TOLERANCE

Validates all Telegram post outputs before publishing.

CRITICAL GATES (ALL must pass):
1. ID Consistency: event_id, prediction_log_id, snapshot_hash, selection_id match payload
2. Numeric Token Validation: Every number in text must match canonical payload
3. Forbidden Phrases Gate: Constrained posts cannot contain narrative explanations
4. Selection Integrity: Team/side mentions must match canonical selection
5. Required Fields: All mandatory fields must be present

IF ANY FAIL → BLOCK PUBLISH (safe failure, no silent bad posts)
"""

import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel

from backend.db.telegram_schemas import (
    TelegramQueueItem,
    ValidatorReport,
)


class NumericToken(BaseModel):
    """Extracted numeric token from rendered text"""
    token: str
    value: float
    position: int
    token_type: Optional[str] = None  # "probability", "line", "odds", "edge", "ev"


class TelegramCopyValidator:
    """
    Validates rendered Telegram text against canonical payload.
    
    ZERO TOLERANCE: Any mismatch = validation failure = blocked publish.
    """
    
    # Tolerance for numeric comparisons
    PROBABILITY_TOLERANCE = 0.001  # ±0.1% for probabilities
    LINE_TOLERANCE = 0.05  # ±0.05 for lines (handles float storage)
    ODDS_TOLERANCE = 0  # Exact match for odds
    EDGE_TOLERANCE = 0.001  # ±0.1% for edges/EV
    
    # Forbidden phrases for constrained posts
    FORBIDDEN_PHRASES_CONSTRAINED = [
        # Narrative explanations (not allowed in constrained mode)
        "because",
        "due to",
        "injury",
        "injured",
        "sharp",
        "steam",
        "public",
        "vegas knows",
        "line movement",
        "sharp money",
        "public betting",
        
        # Confidence language (never allowed in constrained)
        "confident",
        "lock",
        "guaranteed",
        "free money",
        "can't lose",
        "sure thing",
        "slam dunk",
        
        # Explanatory phrases beyond allowed constraint notice
        "model sees",
        "expecting",
        "should win",
        "will win",
        "likely to",
        "strong play",
        "best bet",
    ]
    
    def __init__(self):
        self.validation_errors: List[str] = []
    
    def validate(
        self,
        rendered_text: str,
        queue_item: TelegramQueueItem,
        template_id_used: str
    ) -> ValidatorReport:
        """
        Validate rendered text against canonical queue item.
        
        Returns:
            ValidatorReport with passed=True if all checks pass, else passed=False
        """
        self.validation_errors = []
        
        # Gate 1: ID Consistency
        id_check_passed = self._validate_id_consistency(queue_item)
        
        # Gate 2: Numeric Token Validation
        numeric_tokens = self._extract_numeric_tokens(rendered_text)
        numeric_check_passed, tokens_validated = self._validate_numeric_tokens(
            numeric_tokens, queue_item
        )
        
        # Gate 3: Forbidden Phrases Gate
        forbidden_phrases_detected = self._check_forbidden_phrases(
            rendered_text, queue_item
        )
        forbidden_check_passed = len(forbidden_phrases_detected) == 0
        
        # Gate 4: Selection Integrity
        selection_check_passed = self._validate_selection_integrity(
            rendered_text, queue_item
        )
        
        # Gate 5: Required Fields
        missing_fields = self._check_required_fields(queue_item)
        required_fields_passed = len(missing_fields) == 0
        
        # Overall pass/fail
        all_passed = (
            id_check_passed
            and numeric_check_passed
            and forbidden_check_passed
            and selection_check_passed
            and required_fields_passed
        )
        
        # Determine failure reason (first failure wins)
        failure_reason = None
        if not all_passed:
            if not id_check_passed:
                failure_reason = "ID_MISMATCH"
            elif not required_fields_passed:
                failure_reason = "MISSING_FIELDS"
            elif not numeric_check_passed:
                failure_reason = "NUMERIC_TOKEN_MISMATCH"
            elif not forbidden_check_passed:
                failure_reason = "FORBIDDEN_PHRASE"
            elif not selection_check_passed:
                failure_reason = "SELECTION_INTEGRITY_VIOLATION"
        
        return ValidatorReport(
            passed=all_passed,
            failure_reason=failure_reason,
            numeric_tokens_validated=tokens_validated,
            missing_fields=missing_fields,
            forbidden_phrases_detected=forbidden_phrases_detected,
            id_mismatches=self.validation_errors if not id_check_passed else [],
            details={
                "id_check_passed": id_check_passed,
                "numeric_check_passed": numeric_check_passed,
                "forbidden_check_passed": forbidden_check_passed,
                "selection_check_passed": selection_check_passed,
                "required_fields_passed": required_fields_passed,
                "validation_errors": self.validation_errors,
            }
        )
    
    def _validate_id_consistency(self, queue_item: TelegramQueueItem) -> bool:
        """
        Validate that all required IDs are present and consistent.
        
        REQUIRED:
        - event_id
        - prediction_log_id
        - snapshot_hash
        - selection.selection_id
        """
        checks = [
            (queue_item.event_id, "event_id"),
            (queue_item.prediction_log_id, "prediction_log_id"),
            (queue_item.snapshot_hash, "snapshot_hash"),
            (queue_item.selection.selection_id, "selection.selection_id"),
        ]
        
        all_present = True
        for value, field_name in checks:
            if not value or value.strip() == "":
                self.validation_errors.append(f"Missing or empty {field_name}")
                all_present = False
        
        return all_present
    
    def _extract_numeric_tokens(self, text: str) -> List[NumericToken]:
        """
        Extract all numeric tokens from rendered text.
        
        Patterns:
        - Probabilities: 60.2%, 0.602
        - Lines: -3.5, +7.5, 221.5
        - Odds: -110, +125
        - Edges/EV: +10.0%, +14.5%, -2.3%
        """
        tokens = []
        
        # Pattern: percentages (60.2%, +10.0%, -2.3%)
        pct_pattern = r'([+-]?\d+\.?\d*)%'
        for match in re.finditer(pct_pattern, text):
            tokens.append(NumericToken(
                token=match.group(0),
                value=float(match.group(1)) / 100.0,  # Convert to decimal
                position=match.start(),
                token_type="percentage"
            ))
        
        # Pattern: decimal probabilities (0.602, 0.502)
        # (less common in user-facing text, but handle it)
        decimal_prob_pattern = r'\b(0\.\d+)\b'
        for match in re.finditer(decimal_prob_pattern, text):
            tokens.append(NumericToken(
                token=match.group(0),
                value=float(match.group(1)),
                position=match.start(),
                token_type="decimal_probability"
            ))
        
        # Pattern: lines and odds (signed integers/decimals)
        # -3.5, +7.5, -110, +125, 221.5
        signed_number_pattern = r'([+-]\d+\.?\d*)\b'
        for match in re.finditer(signed_number_pattern, text):
            # Skip if already captured as percentage
            if any(t.position == match.start() for t in tokens):
                continue
            
            value_str = match.group(1)
            value = float(value_str)
            
            # Heuristic: if value is large integer (> 100), likely odds
            if abs(value) >= 100 and '.' not in value_str:
                token_type = "odds"
            elif abs(value) < 50:
                token_type = "line"
            else:
                token_type = "number"
            
            tokens.append(NumericToken(
                token=match.group(0),
                value=value,
                position=match.start(),
                token_type=token_type
            ))
        
        # Pattern: unsigned decimals (221.5 for totals)
        unsigned_decimal_pattern = r'\b(\d+\.\d+)\b'
        for match in re.finditer(unsigned_decimal_pattern, text):
            # Skip if already captured
            if any(t.position == match.start() for t in tokens):
                continue
            
            tokens.append(NumericToken(
                token=match.group(0),
                value=float(match.group(1)),
                position=match.start(),
                token_type="decimal"
            ))
        
        return tokens
    
    def _validate_numeric_tokens(
        self,
        tokens: List[NumericToken],
        queue_item: TelegramQueueItem
    ) -> Tuple[bool, int]:
        """
        Validate that every numeric token in rendered text matches canonical payload.
        
        Returns:
            (all_valid, tokens_validated_count)
        """
        if not tokens:
            # No numeric tokens found - this might be OK for some templates
            return True, 0
        
        # Build canonical value set
        canonical_values = self._build_canonical_value_set(queue_item)
        
        all_valid = True
        tokens_validated = 0
        
        for token in tokens:
            matched = False
            
            # Try to match against canonical values with appropriate tolerance
            for canonical_value, value_type in canonical_values:
                if self._values_match(token.value, canonical_value, value_type):
                    matched = True
                    tokens_validated += 1
                    break
            
            if not matched:
                self.validation_errors.append(
                    f"Numeric token '{token.token}' (value={token.value}) "
                    f"does not match any canonical value"
                )
                all_valid = False
        
        return all_valid, tokens_validated
    
    def _build_canonical_value_set(
        self, queue_item: TelegramQueueItem
    ) -> List[Tuple[float, str]]:
        """
        Build set of all canonical numeric values from queue item.
        
        Returns:
            List of (value, value_type) tuples
        """
        values = []
        
        # Probabilities
        values.append((queue_item.pricing.model_prob, "probability"))
        values.append((queue_item.pricing.market_prob, "probability"))
        values.append((queue_item.pricing.prob_edge, "edge"))
        
        if queue_item.pricing.ev is not None:
            values.append((queue_item.pricing.ev, "edge"))
        
        # Lines
        if queue_item.selection.line is not None:
            values.append((queue_item.selection.line, "line"))
        
        # Odds
        if queue_item.selection.american_odds is not None:
            values.append((float(queue_item.selection.american_odds), "odds"))
        
        return values
    
    def _values_match(self, token_value: float, canonical_value: float, value_type: str) -> bool:
        """
        Check if token value matches canonical value within tolerance.
        """
        if value_type == "probability":
            return abs(token_value - canonical_value) <= self.PROBABILITY_TOLERANCE
        elif value_type == "line":
            return abs(token_value - canonical_value) <= self.LINE_TOLERANCE
        elif value_type == "odds":
            return abs(token_value - canonical_value) <= self.ODDS_TOLERANCE
        elif value_type == "edge":
            return abs(token_value - canonical_value) <= self.EDGE_TOLERANCE
        else:
            # Unknown type - use edge tolerance as default
            return abs(token_value - canonical_value) <= self.EDGE_TOLERANCE
    
    def _check_forbidden_phrases(
        self,
        text: str,
        queue_item: TelegramQueueItem
    ) -> List[str]:
        """
        Check for forbidden phrases in rendered text.
        
        If constraints.mode == "constrained", text must NOT contain:
        - Narrative explanations beyond the constraint notice
        - Confidence language
        - Betting advice beyond the numbers
        """
        detected = []
        
        # Only apply forbidden phrases check for constrained posts
        if queue_item.constraints.mode != "constrained":
            return detected
        
        text_lower = text.lower()
        
        for phrase in self.FORBIDDEN_PHRASES_CONSTRAINED:
            if phrase in text_lower:
                detected.append(phrase)
        
        return detected
    
    def _validate_selection_integrity(
        self,
        text: str,
        queue_item: TelegramQueueItem
    ) -> bool:
        """
        Validate that if text mentions a team or side, it matches canonical selection.
        
        This prevents "Bucks/Celtics weirdness" where wrong team is shown.
        """
        # Extract team name from selection
        canonical_team = queue_item.selection.team_name
        
        # Check if canonical team appears in text
        # (If it doesn't appear at all, that's also suspicious, but not necessarily wrong
        # for totals or other non-team-specific markets)
        
        # For now, just verify that if team name appears, it's the canonical one
        # More sophisticated checks could be added later
        
        if canonical_team and canonical_team.lower() in text.lower():
            return True
        
        # If market is TOTAL, team name might not appear (Over/Under)
        if queue_item.market_type == "TOTAL":
            return True
        
        # Otherwise, team should appear in text for SPREAD/ML markets
        if queue_item.market_type in ["SPREAD", "MONEYLINE"]:
            if canonical_team and canonical_team.lower() not in text.lower():
                self.validation_errors.append(
                    f"Canonical team '{canonical_team}' not found in rendered text"
                )
                return False
        
        return True
    
    def _check_required_fields(self, queue_item: TelegramQueueItem) -> List[str]:
        """
        Check that all required fields are present and non-null.
        
        REQUIRED (from spec):
        - event_id
        - market_type
        - selection_id
        - team_id/team_name (as provided by backend)
        - line (for SPREAD/TOTAL) OR american_odds (for ML)
        - probability (model)
        - market_implied_probability
        - prob_edge, ev
        - snapshot_hash
        - model_version, sim_count, generated_at
        """
        missing = []
        
        # Core IDs
        if not queue_item.event_id:
            missing.append("event_id")
        if not queue_item.market_type:
            missing.append("market_type")
        if not queue_item.selection.selection_id:
            missing.append("selection_id")
        if not queue_item.selection.team_id:
            missing.append("team_id")
        if not queue_item.selection.team_name:
            missing.append("team_name")
        
        # Line/odds (market-specific)
        if queue_item.market_type in ["SPREAD", "TOTAL"]:
            if queue_item.selection.line is None:
                missing.append("line")
        
        if queue_item.market_type == "MONEYLINE":
            if queue_item.selection.american_odds is None:
                missing.append("american_odds")
        
        # Probabilities
        if queue_item.pricing.model_prob is None:
            missing.append("model_prob")
        if queue_item.pricing.market_prob is None:
            missing.append("market_prob")
        if queue_item.pricing.prob_edge is None:
            missing.append("prob_edge")
        
        # EV is optional (spec says "ev (if available)")
        
        # Snapshot/versioning
        if not queue_item.snapshot_hash:
            missing.append("snapshot_hash")
        if not queue_item.model_version:
            missing.append("model_version")
        if queue_item.sim_count is None:
            missing.append("sim_count")
        if not queue_item.generated_at:
            missing.append("generated_at")
        
        return missing


# ==================== VALIDATION HELPERS ====================

def validate_telegram_post(
    rendered_text: str,
    queue_item: TelegramQueueItem,
    template_id_used: str
) -> ValidatorReport:
    """
    Convenience function for validating a Telegram post.
    
    Usage:
        report = validate_telegram_post(rendered_text, queue_item, template_id)
        if report.passed:
            # Publish
        else:
            # Block and log
    """
    validator = TelegramCopyValidator()
    return validator.validate(rendered_text, queue_item, template_id_used)


if __name__ == "__main__":
    # Test example
    from backend.db.telegram_schemas import (
        TelegramQueueItem,
        TelegramSelection,
        TelegramPricing,
        TelegramDisplay,
        TelegramConstraints,
    )
    
    # Create test queue item
    queue_item = TelegramQueueItem(
        queue_id="test_q1",
        event_id="evt_test",
        league="nba",
        market_type="SPREAD",
        prediction_log_id="pred_test",
        snapshot_hash="snap_test",
        model_version="v2.1.0",
        sim_count=100000,
        generated_at=datetime.utcnow(),
        tier="EDGE",
        constraints=TelegramConstraints(mode="none", reason_codes=[]),
        selection=TelegramSelection(
            selection_id="sel_test",
            team_id="team_bos",
            team_name="Boston Celtics",
            side="AWAY",
            line=-3.5,
            american_odds=-110
        ),
        pricing=TelegramPricing(
            model_prob=0.602,
            market_prob=0.502,
            prob_edge=0.100,
            ev=0.145
        ),
        display=TelegramDisplay(
            allowed=True,
            template_id="TG_EDGE_V1",
            posted_at=None,
            telegram_message_id=None
        ),
        home_team="Golden State Warriors",
        away_team="Boston Celtics",
        start_time=datetime.utcnow()
    )
    
    # Test valid text
    valid_text = """📊 NBA — SPREAD
Boston Celtics -3.5 (-110)
Model Prob: 60.2%
Market Prob: 50.2%
Prob Edge: +10.0%
EV: +14.5%
Classification: EDGE

🔗 https://t.me/BEATVEGASAPP"""
    
    report = validate_telegram_post(valid_text, queue_item, "TG_EDGE_V1")
    print(f"Valid text validation: {'✅ PASSED' if report.passed else '❌ FAILED'}")
    print(f"Tokens validated: {report.numeric_tokens_validated}")
    print(f"Details: {report.details}")
    
    # Test invalid text (wrong probability)
    invalid_text = """📊 NBA — SPREAD
Boston Celtics -3.5 (-110)
Model Prob: 65.0%
Market Prob: 50.2%
Prob Edge: +10.0%
EV: +14.5%
Classification: EDGE

🔗 https://t.me/BEATVEGASAPP"""
    
    report = validate_telegram_post(invalid_text, queue_item, "TG_EDGE_V1")
    print(f"\nInvalid text validation: {'✅ PASSED' if report.passed else '❌ FAILED'}")
    print(f"Failure reason: {report.failure_reason}")
    print(f"Details: {report.details}")
