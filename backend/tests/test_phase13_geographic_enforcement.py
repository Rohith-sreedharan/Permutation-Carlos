"""
Phase 13 — Geographic Enforcement Unit Tests
Domain: Geographic enforcement (minimum 10 tests required)

Covers:
  - _get_client_ip: CF-Connecting-IP, X-Forwarded-For, X-Real-IP, fallback
  - _BLOCKED_SUBDIVISIONS: PR, VI, GU, MP, AS, UM all blocked
  - GeoIPMiddleware: enabled flag
  - No bypass paths registered
"""
import pytest
from unittest.mock import MagicMock, patch

from middleware.geoip import _get_client_ip, _BLOCKED_SUBDIVISIONS, _BYPASS_PATHS


# ─────────────────────────────────────────────────────────────────────────────
# IP extraction
# ─────────────────────────────────────────────────────────────────────────────

def _mock_request(headers: dict, client_host: str = "10.0.0.1"):
    req = MagicMock()
    req.headers = headers
    req.client = MagicMock()
    req.client.host = client_host
    return req


class TestGetClientIp:
    def test_cf_connecting_ip_takes_priority(self):
        req = _mock_request({
            "CF-Connecting-IP": "1.2.3.4",
            "X-Forwarded-For": "5.6.7.8",
        })
        assert _get_client_ip(req) == "1.2.3.4"

    def test_x_forwarded_for_leftmost(self):
        req = _mock_request({
            "X-Forwarded-For": "9.10.11.12, 192.168.1.1",
        })
        assert _get_client_ip(req) == "9.10.11.12"

    def test_x_real_ip_used_if_no_forwarded(self):
        req = _mock_request({
            "X-Real-IP": "203.0.113.5",
        })
        assert _get_client_ip(req) == "203.0.113.5"

    def test_fallback_to_client_host(self):
        req = _mock_request({}, client_host="172.16.0.1")
        assert _get_client_ip(req) == "172.16.0.1"

    def test_cf_ip_whitespace_stripped(self):
        req = _mock_request({"CF-Connecting-IP": "  1.2.3.4  "})
        assert _get_client_ip(req) == "1.2.3.4"

    def test_x_forwarded_for_whitespace_stripped(self):
        req = _mock_request({"X-Forwarded-For": "  9.9.9.9 , 1.1.1.1"})
        assert _get_client_ip(req) == "9.9.9.9"


# ─────────────────────────────────────────────────────────────────────────────
# Blocked subdivisions
# ─────────────────────────────────────────────────────────────────────────────

class TestBlockedSubdivisions:
    def test_puerto_rico_blocked(self):
        assert "PR" in _BLOCKED_SUBDIVISIONS

    def test_us_virgin_islands_blocked(self):
        assert "VI" in _BLOCKED_SUBDIVISIONS

    def test_guam_blocked(self):
        assert "GU" in _BLOCKED_SUBDIVISIONS

    def test_northern_mariana_islands_blocked(self):
        assert "MP" in _BLOCKED_SUBDIVISIONS

    def test_american_samoa_blocked(self):
        assert "AS" in _BLOCKED_SUBDIVISIONS

    def test_us_minor_outlying_blocked(self):
        assert "UM" in _BLOCKED_SUBDIVISIONS

    def test_total_blocked_count_is_six(self):
        assert len(_BLOCKED_SUBDIVISIONS) == 6


# ─────────────────────────────────────────────────────────────────────────────
# No bypass paths
# ─────────────────────────────────────────────────────────────────────────────

class TestNoBypassPaths:
    def test_bypass_paths_set_is_empty(self):
        """
        The spec directive states 'no bypass path of any kind'.
        _BYPASS_PATHS must be an empty set.
        """
        assert len(_BYPASS_PATHS) == 0

    def test_bypass_paths_is_a_set(self):
        assert isinstance(_BYPASS_PATHS, set)
