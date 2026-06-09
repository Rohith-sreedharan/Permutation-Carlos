"""
Phase 13 — Entitlement Gating + Billing Domain Unit Tests
Domain: Entitlement gating (15 min) + Billing (additional coverage)

Covers:
  - BillingLedgerService (billing domain)
  - EntitlementsEngine tier rules (entitlement domain)
  - get_user_tier middleware helper
  - Subscription context construction
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Billing: BillingLedgerService
# ─────────────────────────────────────────────────────────────────────────────

class TestBillingLedgerService:
    def _fake_collection(self):
        class FakeCol:
            def __init__(self):
                self._docs = []
            def create_index(self, *a, **kw): pass
            def insert_one(self, doc):
                self._docs.append(doc)
                return type("R", (), {"inserted_id": "ok"})()
            def aggregate(self, pipeline):
                return []
        return FakeCol()

    def test_service_instantiates(self):
        from services.billing_state_service import BillingLedgerService
        col = self._fake_collection()
        svc = BillingLedgerService(ledger_collection=col)
        assert svc is not None

    def test_service_has_append_ledger_entry(self):
        from services.billing_state_service import BillingLedgerService
        svc = BillingLedgerService.__new__(BillingLedgerService)
        assert hasattr(svc, "append_ledger_entry")

    def test_service_has_get_derived_balance(self):
        from services.billing_state_service import BillingLedgerService
        svc = BillingLedgerService.__new__(BillingLedgerService)
        assert hasattr(svc, "get_derived_balance")

    def test_get_derived_balance_returns_zero_for_empty(self):
        from services.billing_state_service import BillingLedgerService
        col = self._fake_collection()
        svc = BillingLedgerService(ledger_collection=col)
        balance = svc.get_derived_balance("u_none")
        assert balance == 0.0

    def test_default_tier_is_free(self):
        from services.entitlements_service import SubscriptionContext
        ctx = SubscriptionContext(user_id="u1")
        assert ctx.beatvegas_tier == "free"
        assert ctx.beatvegas_active is False

    def test_telegram_only_subscription(self):
        from services.entitlements_service import SubscriptionContext
        ctx = SubscriptionContext(
            user_id="u2",
            telegram_only_active=True,
            telegram_linked=True,
        )
        assert ctx.telegram_only_active is True

    def test_beatvegas_active_flag(self):
        from services.entitlements_service import SubscriptionContext
        ctx = SubscriptionContext(
            user_id="u3",
            beatvegas_tier="100k",
            beatvegas_active=True,
        )
        assert ctx.beatvegas_active is True
        assert ctx.beatvegas_tier == "100k"

    def test_user_id_required(self):
        from services.entitlements_service import SubscriptionContext
        import pydantic
        with pytest.raises((pydantic.ValidationError, TypeError)):
            SubscriptionContext()  # missing user_id


# ─────────────────────────────────────────────────────────────────────────────
# Entitlement gating: middleware get_user_tier
# ─────────────────────────────────────────────────────────────────────────────

class TestGetUserTier:
    def test_free_user_returns_free(self):
        from middleware.auth import get_user_tier
        user = {"tier": "free", "user_id": "u1"}
        assert get_user_tier(user) == "free"

    def test_platform_user_returns_tier(self):
        from middleware.auth import get_user_tier
        user = {"tier": "platform", "user_id": "u2"}
        assert get_user_tier(user) == "platform"

    def test_missing_tier_returns_default(self):
        from middleware.auth import get_user_tier
        user = {"user_id": "u3"}
        tier = get_user_tier(user)
        # Should return some default string, not raise
        assert isinstance(tier, str)

    def test_intelligence_preview_tier(self):
        from middleware.auth import get_user_tier
        user = {"tier": "intelligence_preview", "user_id": "u4"}
        assert get_user_tier(user) == "intelligence_preview"


# ─────────────────────────────────────────────────────────────────────────────
# Entitlement gating: require_active_subscription gate logic
# ─────────────────────────────────────────────────────────────────────────────

class TestEntitlementGateLogic:
    def test_require_feature_function_exists(self):
        """Smoke test: entitlement gate functions are importable."""
        from services.entitlement_gate import require_active_subscription
        assert callable(require_active_subscription)

    def test_require_allocation_remaining_importable(self):
        from services.entitlement_gate import require_allocation_remaining
        assert callable(require_allocation_remaining)

    def test_require_intelligence_with_allocation_importable(self):
        from services.entitlement_gate import require_intelligence_with_allocation
        assert callable(require_intelligence_with_allocation)
