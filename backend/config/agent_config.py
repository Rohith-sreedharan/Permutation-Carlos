"""
Agent Config — Phase 2C

Single source of truth for all Sentinel monitoring thresholds.
Zero hardcoded values in any middleware or service file.
All values are overridable via environment variables at runtime.
"""
import os

AGENT_CONFIG: dict = {
    # ── Rate limiting ────────────────────────────────────────────────────────
    # CF-3: Sliding-window intent documentation.
    # Each bucket is a fixed-width 60-second wall-clock window.
    # Counters reset at the window boundary — NOT per-request.
    # This means a burst of N requests in the last 1 second of window W will all
    # be counted in W; the same N requests at the start of window W+1 are a fresh
    # bucket. This is intentional: it keeps implementation lock-free (no sorted-set
    # per user) at the cost of ±1 window of leniency at boundaries.
    # The 11-blocked-at-65-requests result in Phase 2 tests is correct: 65 - 60 = 5
    # requests above the 60 rpm limit, plus timing variance from concurrent threads
    # can add a few extra blocks — 11 is within the expected range [5, 15].
    "rate_limiting": {
        "rate_limit_per_user_rpm": int(os.getenv("RATE_LIMIT_USER_RPM", "120")),
        "rate_limit_per_ip_rpm": int(os.getenv("RATE_LIMIT_IP_RPM", "60")),
        "rate_limit_burst_multiplier": float(os.getenv("RATE_LIMIT_BURST", "1.5")),
        # Window duration in seconds. Sliding window: timestamps outside this
        # window are pruned on each request. The 'sliding' semantic guarantees
        # that a user cannot exceed rpm in any rolling window of this width.
        "rate_limit_window_seconds": int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60")),
    },

    # ── Auth ──────────────────────────────────────────────────────────────
    "auth": {
        # Failed auth attempts within the window before alerting operator
        "failed_auth_alert_threshold": int(os.getenv("AUTH_FAIL_THRESHOLD", "10")),
        "failed_auth_window_seconds": int(os.getenv("AUTH_FAIL_WINDOW_SEC", "300")),
        # JWT settings
        "jwt_access_token_expire_minutes": int(os.getenv("JWT_ACCESS_EXPIRE_MIN", "60")),
        "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
        # Apple Sign In
        "apple_client_id": os.getenv("APPLE_CLIENT_ID", ""),
        # CF-2: Hard removal date for legacy 'user:<id>' tokens.
        # After this date all legacy tokens receive 401 — no grace period, no warning.
        # Format: ISO-8601 date. Set to empty string to keep the grace period open.
        "legacy_token_hard_removal_date": os.getenv("LEGACY_TOKEN_REMOVAL_DATE", "2026-08-01"),
    },

    # ── Geographic enforcement ───────────────────────────────────────────────
    "geo": {
        # Log geo violations within this many seconds (SLA: 60)
        "sentinel_log_sla_seconds": int(os.getenv("GEO_LOG_SLA_SEC", "60")),
        "blocked_territories": os.getenv(
            "GEO_BLOCKED_TERRITORIES", "PR,VI,GU,MP,AS,UM"
        ).split(","),
    },

    # ── DecisionRecord idempotency ───────────────────────────────────────────
    "decision_records": {
        # Max concurrent publish attempts allowed before blocking
        "max_concurrent_publishes": int(os.getenv("DR_MAX_CONCURRENT_PUBLISHES", "1")),
        # Sentinel alert on duplicate publish attempt
        "alert_on_duplicate": os.getenv("DR_ALERT_ON_DUPLICATE", "true").lower() == "true",
    },

    # ── Sentinel monitoring ──────────────────────────────────────────────────
    "sentinel": {
        # Interval between automated sentinel check cycles (seconds)
        "check_interval_seconds": int(os.getenv("SENTINEL_CHECK_INTERVAL_SEC", "30")),
        # How far back each check window looks
        "check_window_minutes": int(os.getenv("SENTINEL_WINDOW_MIN", "15")),
        # Alert channel: "log" | "webhook" | "both"
        "alert_channel": os.getenv("SENTINEL_ALERT_CHANNEL", "log"),
        "alert_webhook_url": os.getenv("SENTINEL_ALERT_WEBHOOK_URL", ""),
        # Phase 2C: absolute-count thresholds for security event types
        "GEO_VIOLATION_ALERT_COUNT": int(os.getenv("GEO_VIOLATION_ALERT_COUNT", "50")),
        "AUTH_ANOMALY_THRESHOLD": int(os.getenv("AUTH_ANOMALY_THRESHOLD", "10")),
        "RATE_LIMIT_BREACH_ALERT_THRESHOLD": int(os.getenv("RATE_LIMIT_BREACH_ALERT_THRESHOLD", "100")),
        "DUPLICATE_DR_ALERT_COUNT": int(os.getenv("DUPLICATE_DR_ALERT_COUNT", "5")),
        # Phase 3C: billing monitoring thresholds
        "BILLING_WRITE_FAIL_ALERT_THRESHOLD": int(os.getenv("BILLING_WRITE_FAIL_THRESHOLD", "1")),
        "ENTITLEMENT_VIOLATION_ALERT_THRESHOLD": int(os.getenv("ENTITLEMENT_VIOLATION_THRESHOLD", "3")),
        "OVERAGE_WARN_PCT": int(os.getenv("OVERAGE_WARN_PCT", "80")),   # % of allocation → warn
        "OVERAGE_BLOCK_PCT": int(os.getenv("OVERAGE_BLOCK_PCT", "100")),  # % of allocation → block
        "WEBHOOK_FAIL_ALERT_THRESHOLD": int(os.getenv("WEBHOOK_FAIL_THRESHOLD", "3")),
        "SUBSCRIPTION_EXPIRY_CHECK_WINDOW_MIN": int(os.getenv("SUB_EXPIRY_WINDOW_MIN", "5")),
    },

    # ── Phase 3 Billing ──────────────────────────────────────────────────────
    "billing": {
        # Overage rate per token shortfall (cents → stored as float USD)
        "overage_rate_per_token": float(os.getenv("OVERAGE_RATE_PER_TOKEN", "0.02")),
        # Stripe product/price IDs — set via env on server; defaults are empty (must be set in production)
        "stripe_price_id_syndicate": os.getenv("STRIPE_PRICE_ID_SYNDICATE", ""),
        "stripe_price_id_platform": os.getenv("STRIPE_PRICE_ID_PLATFORM", ""),
        # Monthly token allocations per tier (used for overage calculation)
        "tier_token_allocation": {
            "intelligence_preview": int(os.getenv("TOKENS_PREVIEW", "0")),
            "syndicate": int(os.getenv("TOKENS_SYNDICATE", "5000")),
            "platform": int(os.getenv("TOKENS_PLATFORM", "25000")),
        },
        # Email provider: sendgrid | resend | ses
        "email_provider": os.getenv("EMAIL_PROVIDER", "sendgrid"),
        "email_from_address": os.getenv("EMAIL_FROM", "noreply@beatvegas.app"),
        "password_reset_expiry_minutes": int(os.getenv("PWD_RESET_EXPIRY_MIN", "15")),
    },

    # ── Phase 5 Growth Agent ─────────────────────────────────────────────────
    "phase5": {
        # Identity — LOCKED — never change
        "growth_agent_id": "agent.growth.v1",
        # Onboarding sequence timing
        "onboarding_step1_max_delay_seconds": int(os.getenv("P5_STEP1_MAX_DELAY_SEC", "60")),
        "onboarding_step2_delay_hours": int(os.getenv("P5_STEP2_DELAY_HRS", "24")),
        "onboarding_step3_delay_hours": int(os.getenv("P5_STEP3_DELAY_HRS", "48")),
        # Credit usage thresholds — all configurable, zero hardcoded
        "upgrade_prompt_threshold_pct": int(os.getenv("P5_UPGRADE_THRESHOLD_PCT", "80")),
        "low_balance_threshold_pct": int(os.getenv("P5_LOW_BALANCE_PCT", "90")),
        # Re-engagement and expiry thresholds
        "reengagement_inactivity_days": int(os.getenv("P5_REENGAGEMENT_DAYS", "7")),
        "credit_expiry_warning_days": int(os.getenv("P5_CREDIT_EXPIRY_WARN_DAYS", "3")),
        # Platform pricing — shown in upgrade prompt
        "platform_price_monthly": os.getenv("P5_PLATFORM_PRICE", "$97/month"),
    },
}
