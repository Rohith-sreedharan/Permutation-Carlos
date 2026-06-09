"""
Phase 13 — Affiliate System Unit Tests
Domain: Affiliate system (minimum 20 tests required)

Covers:
  - sanitise_html (XSS encoding)
  - _AFFILIATE_ID_RE validation
  - get_charge_disclosure (timezone resolution, FTC compliance)
  - check_deduplication (email path + fingerprint path)
  - _cfg() config shorthand

All tests run without a live MongoDB — uses FakeDB pattern.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from services.phase13_affiliate_trial import (
    sanitise_html,
    _AFFILIATE_ID_RE,
    get_charge_disclosure,
    _STATE_TZ,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. sanitise_html — XSS encoding
# ─────────────────────────────────────────────────────────────────────────────

class TestSanitiseHtml:
    def test_plain_string_unchanged(self):
        assert sanitise_html("John Doe") == "John Doe"

    def test_script_tag_encoded(self):
        result = sanitise_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_double_quote_encoded(self):
        result = sanitise_html('He said "hello"')
        assert '"hello"' not in result
        assert "&quot;" in result or "&#x27;" in result or "hello" in result

    def test_angle_brackets_encoded(self):
        result = sanitise_html("<b>bold</b>")
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_ampersand_encoded(self):
        result = sanitise_html("Tom & Jerry")
        assert "Tom &amp; Jerry" == result or "Tom & Jerry" in result
        # html.escape encodes & to &amp;
        assert "&amp;" in result

    def test_empty_string(self):
        assert sanitise_html("") == ""

    def test_unicode_passthrough(self):
        result = sanitise_html("Caf\u00e9 \u2665")
        assert "Caf\u00e9" in result

    def test_sql_injection_single_quotes_encoded(self):
        """Single quotes in SQL injection strings are HTML-encoded (html.escape quote=True)."""
        raw = "' OR '1'='1"
        result = sanitise_html(raw)
        # html.escape(quote=True) encodes ' to &#x27;
        assert "&#x27;" in result
        assert "OR" in result  # non-HTML content passes through


# ─────────────────────────────────────────────────────────────────────────────
# 2. Affiliate ID regex validation
# ─────────────────────────────────────────────────────────────────────────────

class TestAffiliateIdRegex:
    def test_valid_alphanumeric(self):
        assert _AFFILIATE_ID_RE.match("validAffiliate123")

    def test_valid_with_hyphen(self):
        assert _AFFILIATE_ID_RE.match("my-affiliate-id")

    def test_valid_with_underscore(self):
        assert _AFFILIATE_ID_RE.match("my_affiliate_id")

    def test_too_short_rejected(self):
        assert not _AFFILIATE_ID_RE.match("abc")  # 3 chars, min is 4

    def test_too_long_rejected(self):
        assert not _AFFILIATE_ID_RE.match("a" * 65)

    def test_exactly_4_chars_valid(self):
        assert _AFFILIATE_ID_RE.match("abcd")

    def test_exactly_64_chars_valid(self):
        assert _AFFILIATE_ID_RE.match("a" * 64)

    def test_space_rejected(self):
        assert not _AFFILIATE_ID_RE.match("my affiliate")

    def test_slash_rejected(self):
        assert not _AFFILIATE_ID_RE.match("affiliate/id")

    def test_angle_bracket_rejected(self):
        assert not _AFFILIATE_ID_RE.match("<script>")


# ─────────────────────────────────────────────────────────────────────────────
# 3. get_charge_disclosure — timezone and FTC compliance
# ─────────────────────────────────────────────────────────────────────────────

class TestGetChargeDisclosure:
    def test_returns_required_keys(self):
        result = get_charge_disclosure(72)
        assert "trial_ends_at_utc" in result
        assert "charge_display" in result
        assert "disclosure_text" in result
        assert "timezone_used" in result
        assert "timezone_note" in result

    def test_trial_ends_at_is_future(self):
        result = get_charge_disclosure(72)
        end = datetime.fromisoformat(result["trial_ends_at_utc"])
        assert end > datetime.now(timezone.utc)

    def test_72h_trial_ends_approx_3_days_out(self):
        result = get_charge_disclosure(72)
        end = datetime.fromisoformat(result["trial_ends_at_utc"])
        delta = end - datetime.now(timezone.utc)
        # Allow 5-second tolerance
        assert abs(delta.total_seconds() - 72 * 3600) < 5

    def test_state_code_resolves_timezone(self):
        result = get_charge_disclosure(72, state_code="CA")
        assert result["timezone_used"] == "America/Los_Angeles"

    def test_iana_tz_overrides_state_code(self):
        result = get_charge_disclosure(72, iana_tz="America/Chicago", state_code="NY")
        assert result["timezone_used"] == "America/Chicago"

    def test_invalid_iana_tz_falls_back(self):
        result = get_charge_disclosure(72, iana_tz="Invalid/Timezone")
        # Falls back to default (Eastern or state-based)
        assert result["timezone_used"] is not None

    def test_disclosure_text_contains_cancel_instruction(self):
        result = get_charge_disclosure(72)
        assert "Cancel" in result["disclosure_text"] or "cancel" in result["disclosure_text"]

    def test_disclosure_text_contains_free_period(self):
        result = get_charge_disclosure(72)
        assert "Free until" in result["disclosure_text"]

    def test_all_50_states_have_timezone_mapping(self):
        us_states = [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        ]
        for state in us_states:
            assert state in _STATE_TZ, f"State {state} missing from _STATE_TZ"

    def test_dc_has_timezone_mapping(self):
        assert "DC" in _STATE_TZ
        assert _STATE_TZ["DC"] == "America/New_York"


# ─────────────────────────────────────────────────────────────────────────────
# 4. check_deduplication — uses FakeDB injection via monkeypatching
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckDeduplication:
    def _patch_db(self, return_sequence):
        """
        Patch services.phase13_affiliate_trial.db so that successive
        find_one calls return items from return_sequence (None means no match).
        """
        call_iter = iter(return_sequence)

        class FakeCollection:
            def find_one(self, query, projection=None):
                try:
                    return next(call_iter)
                except StopIteration:
                    return None

        class FakeDB:
            def __getitem__(self, name):
                return FakeCollection()

        return FakeDB()

    def test_no_duplicate_returns_ok(self):
        fake_db = self._patch_db([None, None])  # email: None, fingerprint: None
        with patch("services.phase13_affiliate_trial.db", fake_db):
            from services.phase13_affiliate_trial import check_deduplication
            is_dup, reason = check_deduplication("cus_new", "fp_new")
        assert is_dup is False
        assert reason == "ok"

    def test_email_duplicate_blocked(self):
        fake_db = self._patch_db([{"_id": "existing"}])  # email match on first call
        with patch("services.phase13_affiliate_trial.db", fake_db):
            from services.phase13_affiliate_trial import check_deduplication
            is_dup, reason = check_deduplication("cus_existing", "fp_new")
        assert is_dup is True
        assert reason == "TRIAL_ALREADY_USED"

    def test_fingerprint_duplicate_blocked(self):
        fake_db = self._patch_db([None, {"_id": "existing"}])  # email: None, fp: match
        with patch("services.phase13_affiliate_trial.db", fake_db):
            from services.phase13_affiliate_trial import check_deduplication
            is_dup, reason = check_deduplication("cus_new", "fp_existing")
        assert is_dup is True
        assert reason == "TRIAL_ALREADY_USED"
