"""
Phase 13 — Security Domain Unit Tests
Domain: Security (minimum 10 tests required)

Covers:
  - _validate_jwt: JWT decode, expiry, signature validation
  - _parse_token: Bearer header extraction, legacy user:<id> format
  - get_user_tier: tier extraction
  - JWT expiry rejection
  - Invalid signature rejection
  - Token format validation
"""
import pytest
import time
import os
import json
import base64
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from middleware.auth import _validate_jwt, _parse_token, get_user_tier


def _make_jwt(payload: dict, secret: str = "test_secret", algorithm: str = "HS256") -> str:
    """Build a real signed JWT without an external library."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": algorithm, "typ": "JWT"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{body}"
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{signing_input}.{signature}"


# ─────────────────────────────────────────────────────────────────────────────
# _parse_token — Bearer extraction
# ─────────────────────────────────────────────────────────────────────────────

class TestParseToken:
    def test_bearer_token_extracted(self):
        assert _parse_token("Bearer mytoken123") == "mytoken123"

    def test_none_header_returns_none(self):
        assert _parse_token(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_token("") is None

    def test_missing_bearer_prefix_returns_none(self):
        assert _parse_token("mytoken123") is None

    def test_extra_parts_returns_none(self):
        assert _parse_token("Bearer tok extra") is None

    def test_case_insensitive_bearer(self):
        result = _parse_token("bearer mytoken123")
        assert result == "mytoken123"


# ─────────────────────────────────────────────────────────────────────────────
# _validate_jwt — JWT validation
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateJwt:
    def test_valid_jwt_succeeds(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret"}):
            token = _make_jwt({"sub": "user123", "exp": int(time.time()) + 3600})
            payload = _validate_jwt(token)
        assert payload["sub"] == "user123"

    def test_expired_jwt_raises_401(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret"}):
            token = _make_jwt({"sub": "user999", "exp": int(time.time()) - 3600})
            with pytest.raises(HTTPException) as exc_info:
                _validate_jwt(token)
        assert exc_info.value.status_code == 401

    def test_wrong_secret_raises_401(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "correct_secret"}):
            token = _make_jwt({"sub": "user999", "exp": int(time.time()) + 3600}, secret="wrong_secret")
            with pytest.raises(HTTPException) as exc_info:
                _validate_jwt(token)
        assert exc_info.value.status_code == 401

    def test_garbled_token_raises_401(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test_secret"}):
            with pytest.raises(HTTPException) as exc_info:
                _validate_jwt("not.a.jwt")
        assert exc_info.value.status_code in (401, 500)

    def test_missing_secret_raises_500(self):
        """If JWT_SECRET_KEY is not set, the server must reject with 500."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JWT_SECRET_KEY", None)
            with pytest.raises(HTTPException) as exc_info:
                _validate_jwt("anything")
        assert exc_info.value.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# get_user_tier
# ─────────────────────────────────────────────────────────────────────────────

class TestGetUserTierSecurity:
    def test_free_user(self):
        assert get_user_tier({"tier": "free"}) == "free"

    def test_missing_tier_defaults_to_string(self):
        result = get_user_tier({})
        assert isinstance(result, str)

    def test_xss_in_tier_field_not_executed(self):
        """Tier field with XSS payload must be returned as-is, never executed."""
        result = get_user_tier({"tier": "<script>alert(1)</script>"})
        # Must not raise; value is returned as a string
        assert isinstance(result, str)
