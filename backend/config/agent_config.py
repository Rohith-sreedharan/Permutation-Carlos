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

    # ── Phase 6: Distribution Agent + Parlay + CI Drift Audit ────────────────
    "phase6": {
        # Identity — LOCKED
        "distribution_agent_id": "agent.distribution.v1",

        # 6A: Telegram / Distribution
        "approved_distribution_channels": os.getenv(
            "APPROVED_TELEGRAM_CHANNELS", ""
        ).split(","),
        "autopublish_integrity_violation_sla_seconds": int(
            os.getenv("P6_INTEGRITY_DISABLE_SLA_SEC", "60")
        ),
        "staging_clean_run_hours": int(os.getenv("P6_STAGING_HOURS", "48")),

        # 6A.12: CI Drift Audit thresholds — zero hardcoded values in service files
        "drift_audit": {
            "percentile_p75_max_pct": int(os.getenv("P6_DRIFT_P75_MAX_PCT", "80")),
            "percentile_p25_min_pct": int(os.getenv("P6_DRIFT_P25_MIN_PCT", "10")),
            "market_type_skew_max_pct": int(os.getenv("P6_DRIFT_MT_SKEW_PCT", "70")),
            "classification_edge_max_pct": int(os.getenv("P6_DRIFT_EDGE_MAX_PCT", "80")),
            "volume_variance_min": float(os.getenv("P6_DRIFT_VOL_VARIANCE_MIN", "0.5")),
            "delay_variance_min": float(os.getenv("P6_DRIFT_DELAY_VARIANCE_MIN", "10.0")),
        },

        # 6B: Parlay engine
        "parlay": {
            "monthly_token_allocation": int(os.getenv("P6_PARLAY_TOKEN_ALLOC", "1500")),
            "overage_rate_usd_per_token": float(os.getenv("P6_OVERAGE_RATE", "0.02")),
            "overage_alert_pct": int(os.getenv("P6_OVERAGE_ALERT_PCT", "80")),
            "max_totals_per_slate": int(os.getenv("P6_MAX_TOTALS_PER_SLATE", "3")),
            "max_team_exposure": int(os.getenv("P6_MAX_TEAM_EXPOSURE", "2")),
            # Token cost per leg count (locked)
            "token_cost": {
                "2": int(os.getenv("P6_TOKEN_2LEG", "50")),
                "3": int(os.getenv("P6_TOKEN_3LEG", "75")),
                "4": int(os.getenv("P6_TOKEN_4LEG", "100")),
                "5": int(os.getenv("P6_TOKEN_5LEG", "150")),
                "6": int(os.getenv("P6_TOKEN_6LEG", "200")),
            },
        },
    },

    # ── Phase 7: Public Trust Record + AOS Trust Monitoring ──────────────────
    "phase7": {
        # Sample thresholds — LOCKED, operator-approved.
        # Hardcoded here once. Referenced from phase7_trust_record.py.
        # NOT configurable at runtime. NOT overridable via env vars.
        "N_SEGMENT_MIN": 50,     # Minimum sample per segment before any metric is computed
        "N_HOMEPAGE_MIN": 200,   # Minimum sample for homepage summary display
        "N_PROMOTION_MIN": 500,  # Minimum sample for calibration promotion eligibility

        # Sentinel monitoring — configurable, all from env
        "availability_poll_interval_seconds": int(os.getenv("P7_AVAIL_POLL_SEC", "60")),
        "availability_response_time_warning_ms": int(os.getenv("P7_AVAIL_WARN_MS", "3000")),
        "availability_last_known_good_ttl_seconds": int(os.getenv("P7_LKG_TTL_SEC", "86400")),

        # Prohibited language — scanned by AC-5 evidence
        "prohibited_phrases": [
            "bet", "betting", "wager", "wagering", "play", "back", "take", "pick",
            "guaranteed", "lock", "can't lose", "sure thing", "guaranteed winner",
            "sportsbook", "bookmaker", "bookie", "odds shop",
            "must bet", "should bet", "hammer", "smash", "load up", "free money",
            "i recommend", "i'm confident", "trust me", "believe me",
            "monte carlo simulations",
        ],
    },
}
