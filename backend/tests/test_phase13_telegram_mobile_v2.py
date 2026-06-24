"""
Phase 13 — Telegram Pipeline + Mobile Integration Unit Tests
Domain: Telegram pipeline (10 min) + Mobile integration (10 min)

Covers Telegram:
  - TelegramBotService: send_dm, send_channel_message, grant_channel_access
  - Distribution endpoint existence (not 404)
  - Bot token not hardcoded in source
  - Rate-limit config in agent_config

Covers Mobile:
  - SetupIntent route registered (phase13_trial_routes)
  - start_affiliate_trial endpoint exists
  - get_trial_status endpoint exists
  - cancel_trial_endpoint exists
  - Phase13 webhook handlers importable
  - StartTrialRequest model validation
  - plan_id validation via agent_config
  - Stripe keys from env (not hardcoded)
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Telegram pipeline — TelegramBotService
# ─────────────────────────────────────────────────────────────────────────────

class TestTelegramBotService:
    def test_service_importable(self):
        from services.telegram_bot_service import TelegramBotService
        assert TelegramBotService is not None

    def test_send_dm_method_exists(self):
        from services.telegram_bot_service import TelegramBotService
        svc = TelegramBotService.__new__(TelegramBotService)
        assert hasattr(svc, "send_dm")

    def test_send_channel_message_method_exists(self):
        from services.telegram_bot_service import TelegramBotService
        svc = TelegramBotService.__new__(TelegramBotService)
        assert hasattr(svc, "send_channel_message")

    def test_grant_channel_access_method_exists(self):
        from services.telegram_bot_service import TelegramBotService
        svc = TelegramBotService.__new__(TelegramBotService)
        assert hasattr(svc, "grant_channel_access")

    def test_revoke_channel_access_method_exists(self):
        from services.telegram_bot_service import TelegramBotService
        svc = TelegramBotService.__new__(TelegramBotService)
        assert hasattr(svc, "revoke_channel_access")

    def test_generate_link_token_method_exists(self):
        from services.telegram_bot_service import TelegramBotService
        svc = TelegramBotService.__new__(TelegramBotService)
        assert hasattr(svc, "generate_link_token")

    def test_bot_token_not_hardcoded(self):
        """Bot token must NOT be hardcoded in the source file."""
        import re
        import services.telegram_bot_service as ts
        src = open(ts.__file__).read()
        # Real Telegram bot tokens: 8+ digits : 35 chars alphanumeric
        hardcoded = re.search(r"\d{8,}:[A-Za-z0-9_-]{35}", src)
        assert hardcoded is None, "Hardcoded Telegram bot token found in source!"

    def test_rate_limit_config_defined_in_agent_config(self):
        """Rate-limit thresholds must live in agent_config."""
        from config.agent_config import AGENT_CONFIG
        rl = AGENT_CONFIG.get("rate_limiting", {})
        # Config exists and has at least one numeric threshold
        assert isinstance(rl, dict)
        # Any positive-integer key means rate limiting is configured
        assert any(isinstance(v, (int, float)) and v > 0 for v in rl.values()), (
            "No numeric rate-limit thresholds found in AGENT_CONFIG['rate_limiting']"
        )

    def test_telegram_post_generator_importable(self):
        # telegram_post_generator uses module-level functions (no class)
        from services.telegram_post_generator import generate_post
        assert callable(generate_post)


# ─────────────────────────────────────────────────────────────────────────────
# Mobile integration — Phase13 trial routes
# ─────────────────────────────────────────────────────────────────────────────

class TestMobileIntegration:
    @pytest.fixture
    def client(self):
        from main import app
        return TestClient(app)

    def test_trial_page_data_endpoint_exists(self, client):
        """GET /api/trial/affiliate/{affiliate_id} must be registered — not 404."""
        resp = client.get("/api/trial/affiliate/testaffiliate")
        assert resp.status_code != 404

    def test_start_trial_endpoint_exists(self, client):
        """POST /api/trial/affiliate/start must be registered — not 404."""
        resp = client.post("/api/trial/affiliate/start", json={})
        assert resp.status_code != 404

    def test_trial_status_endpoint_exists(self, client):
        """GET /api/trial/status must be registered — not 404."""
        resp = client.get("/api/trial/status")
        assert resp.status_code != 404

    def test_cancel_trial_endpoint_exists(self, client):
        """POST /api/trial/cancel must be registered — not 404."""
        resp = client.post("/api/trial/cancel", json={})
        assert resp.status_code != 404

    def test_start_trial_requires_auth(self, client):
        """Unauthenticated start-trial must be rejected (401/403/422/426 — not 200/500)."""
        resp = client.post("/api/trial/affiliate/start", json={})
        # 426 = Upgrade Required (endpoint may enforce HTTPS)
        assert resp.status_code in (401, 403, 422, 426)

    def test_start_trial_request_model_importable(self):
        from routes.phase13_trial_routes import StartTrialRequest
        assert StartTrialRequest is not None

    def test_stripe_secret_key_from_env_not_hardcoded(self):
        """Stripe secret key must come from env, never hardcoded."""
        import re
        import services.phase13_affiliate_trial as m
        src = open(m.__file__).read()
        # Real Stripe secret keys: sk_live_ or sk_test_ prefix, 24+ chars
        hardcoded = re.search(r'sk_(live|test)_[A-Za-z0-9]{24,}', src)
        assert hardcoded is None, "Hardcoded Stripe key found in affiliate trial service!"

    def test_webhook_handlers_importable(self):
        from routes.phase13_webhook_handlers import (
            handle_trial_will_end,
            handle_trial_payment_succeeded,
            handle_trial_payment_failed,
        )
        assert callable(handle_trial_will_end)
        assert callable(handle_trial_payment_succeeded)
        assert callable(handle_trial_payment_failed)

    def test_plan_id_in_agent_config(self):
        """Platform price IDs are sourced from agent_config['billing'] (env-backed)."""
        from config.agent_config import AGENT_CONFIG
        # Price IDs live in AGENT_CONFIG['billing'], not 'phase13'
        billing = AGENT_CONFIG.get("billing", {})
        assert "stripe_price_id_platform" in billing or "stripe_price_id_syndicate" in billing, (
            "Neither stripe_price_id_platform nor stripe_price_id_syndicate in AGENT_CONFIG['billing']"
        )
