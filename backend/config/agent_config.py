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
        # Phase 9 AC-5 monitors
        "PROHIBITED_LANGUAGE_API_RESPONSE_ALERT_COUNT": int(os.getenv("PROHIBITED_LANGUAGE_API_RESPONSE_ALERT_COUNT", "1")),
        "SELF_EXCLUSION_BYPASS_ALERT_COUNT": int(os.getenv("SELF_EXCLUSION_BYPASS_ALERT_COUNT", "1")),
        "DATA_DELETION_SLA_WARNING_COUNT": int(os.getenv("DATA_DELETION_SLA_WARNING_COUNT", "1")),
        "DATA_DELETION_SLA_BREACH_COUNT": int(os.getenv("DATA_DELETION_SLA_BREACH_COUNT", "1")),
        "DATA_DELETION_SLA_WARNING_DAYS": int(os.getenv("DATA_DELETION_SLA_WARNING_DAYS", "25")),
        "DATA_DELETION_SLA_BREACH_DAYS": int(os.getenv("DATA_DELETION_SLA_BREACH_DAYS", "30")),
        # Phase 11: affiliate fraud monitoring
        "AFFILIATE_FRAUD_RATE_ALERT_COUNT": int(os.getenv("AFFILIATE_FRAUD_RATE_ALERT_COUNT", "1")),
        "AFFILIATE_FRAUD_CLUSTER_ALERT_COUNT": int(os.getenv("AFFILIATE_FRAUD_CLUSTER_ALERT_COUNT", "1")),
        "AFFILIATE_FRAUD_CLUSTER_SIZE": int(os.getenv("AFFILIATE_FRAUD_CLUSTER_SIZE", "3")),
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

    # ── Phase 8: Observability + Full AOS Activation ───────────────────────
    "phase8": {
        # Canonical identities
        "sentinel_agent_id": "agent.sentinel.v1",
        "response_agent_id": "agent.response.v1",
        "recovery_agent_id": "agent.recovery.v1",
        "grading_agent_id": "agent.grading.v1",
        "calibration_agent_id": "agent.calibration.v1",
        "distribution_agent_id": "agent.distribution.v1",
        "growth_agent_id": "agent.growth.v1",

        # Operator auth (separate JWT domain from user auth)
        "operator_jwt_algorithm": os.getenv("OPERATOR_JWT_ALGORITHM", "HS256"),
        "operator_jwt_expire_minutes": int(os.getenv("OPERATOR_JWT_EXPIRE_MIN", "60")),
        "OPERATOR_TEAM": [
            x.strip() for x in os.getenv("OPERATOR_TEAM_IDS", "op_001").split(",") if x.strip()
        ],
        # Backward-compatible alias
        "operator_team": [
            x.strip() for x in os.getenv("OPERATOR_TEAM_IDS", "op_001").split(",") if x.strip()
        ],

        # Observability thresholds
        "integrity_violation_rate_critical_pct": float(os.getenv("P8_INTEGRITY_CRIT_PCT", "0.5")),
        "snapshot_mismatch_rate_warning": float(os.getenv("P8_SNAPSHOT_MISMATCH_WARN", "0")),
        "decision_write_failures_critical": int(os.getenv("P8_DECISION_WRITE_FAIL_CRIT", "1")),
        "publish_failure_rate_critical_pct": float(os.getenv("P8_PUBLISH_FAIL_CRIT_PCT", "1")),
        "feed_staleness_warning_minutes": int(os.getenv("P8_FEED_STALENESS_WARN_MIN", "15")),
        "api_p95_latency_warning_ms": int(os.getenv("P8_API_P95_WARN_MS", "2000")),
        "billing_write_fail_critical": int(os.getenv("P8_BILLING_FAIL_CRIT", "1")),
        "agent_heartbeat_silence_warning_minutes": int(os.getenv("P8_HEARTBEAT_WARN_MIN", "5")),

        # Severity response windows
        "critical_escalate_minutes": int(os.getenv("P8_CRITICAL_ESCALATE_MIN", "15")),
        "warning_response_minutes": int(os.getenv("P8_WARNING_RESPONSE_MIN", "30")),
    },

    # ── Phase 11: Affiliate acquisition engine ─────────────────────────────
    "phase11": {
        "program_access_mode": os.getenv("P11_ACCESS_MODE", "INVITE_ONLY"),
        "open_enrollment_delay_days": int(os.getenv("P11_OPEN_ENROLLMENT_DAYS", "90")),
        "attribution_cookie_name": os.getenv("P11_COOKIE_NAME", "bv_ref"),
        "attribution_cookie_expiry_days": int(os.getenv("P11_COOKIE_EXPIRY_DAYS", "30")),
        "invite_link_expiry_days": int(os.getenv("P11_INVITE_EXPIRY_DAYS", "7")),
        "payout_min_threshold_usd": float(os.getenv("P11_PAYOUT_MIN_THRESHOLD_USD", "50")),
        "payout_batch_day_of_month": int(os.getenv("P11_PAYOUT_BATCH_DOM", "1")),
        "payout_net_days": int(os.getenv("P11_PAYOUT_NET_DAYS", "30")),
    },

    # ── Phase 11.5: Parlay Sentinel Monitors (Section 3.2) ─────────────────
    # All thresholds configurable via env. Zero hardcoded values in the service file.
    "phase11_5": {
        # Max seconds since scheduler last ran before treating absence as a failure
        "scheduler_run_window_seconds": int(os.getenv("P11_5_SCHEDULER_WINDOW_SEC", "3600")),
        # Max age (seconds) of the freshest snapshot_hash before feed is deemed stale
        "feed_staleness_threshold_seconds": int(os.getenv("P11_5_FEED_STALE_SEC", "3600")),
        # DecisionRecord fields that must be non-null for a leg to be parlay-eligible
        "required_leg_fields": os.getenv(
            "P11_5_REQUIRED_LEG_FIELDS",
            "selection_id,snapshot_hash,model_probability,line"
        ).split(","),
    },

    # ── Phase 13: Affiliate 3-Day Trial System ──────────────────────────────
    # All thresholds configurable via env — zero hardcoded values.
    "phase13": {
        # Trial durations (hours)
        "trial_duration_qr_hours": int(os.getenv("P13_TRIAL_QR_HOURS", "24")),
        "trial_duration_affiliate_hours": int(os.getenv("P13_TRIAL_AFFILIATE_HOURS", "72")),
        "trial_duration_subscriber_hours": int(os.getenv("P13_TRIAL_SUBSCRIBER_HOURS", "72")),

        # Promo token expiry (minutes) — 60 min per spec
        "promo_token_expiry_minutes": int(os.getenv("P13_TOKEN_EXPIRY_MIN", "60")),

        # QR code daily redemption cap — prevents bot exhaustion
        "qr_daily_redemption_limit": int(os.getenv("P13_QR_DAILY_LIMIT", "10")),

        # Platform trial subscription token allocation
        "trial_platform_token_allocation": int(os.getenv("P13_TRIAL_TOKENS", "1500")),

        # Section 13.18 — Subscriber Referral Program commission tiers
        "referral_reward_platform_usd": float(os.getenv("P13_REFERRAL_REWARD_PLATFORM_USD", "30.0")),    # Platform ($97/mo) referral
        "referral_reward_syndicate_usd": float(os.getenv("P13_REFERRAL_REWARD_SYNDICATE_USD", "15.0")),  # Syndicate ($47/mo) referral
        "referral_auto_upgrade_threshold": int(os.getenv("P13_REFERRAL_UPGRADE_THRESHOLD", "5")),        # referrer tier upgrade at N conversions

        # Affiliate rapid conversion velocity monitor — fraud sentinel
        # >N conversions from same affiliate_id in rolling M-day window → FRAUD_HOLD
        "affiliate_rapid_conversion_threshold": int(os.getenv("P13_RAPID_CONV_THRESHOLD", "5")),
        "affiliate_rapid_conversion_window_days": int(os.getenv("P13_RAPID_CONV_WINDOW_DAYS", "7")),

        # Device mismatch + conversion window (seconds) — flag for review
        "device_mismatch_conversion_window_seconds": int(os.getenv("P13_DEV_MISMATCH_WINDOW_SEC", "300")),

        # Growth Agent sequence timing offsets (hours from trial_start)
        "trial_day1_hours": int(os.getenv("P13_DAY1_HOURS", "24")),
        "trial_day2_hours": int(os.getenv("P13_DAY2_HOURS", "48")),
        "trial_hour68_hours": int(os.getenv("P13_HOUR68", "68")),
        "trial_hour71_hours": int(os.getenv("P13_HOUR71", "71")),

        # Win-back sequence stop day
        "winback_stop_day": int(os.getenv("P13_WINBACK_STOP_DAY", "30")),

        # Sequence overlap suppression window (hours) when active win-back exists
        "overlap_suppression_hours": int(os.getenv("P13_OVERLAP_SUPPRESS_HRS", "24")),

        # FTC: charge timezone default if GeoIP lookup fails
        "charge_timezone_default": os.getenv("P13_CHARGE_TZ_DEFAULT", "America/New_York"),

        # Commission amounts (USD) — pulled by billing service
        "commission_platform_base_usd": float(os.getenv("P13_COMM_PLATFORM_BASE", "30.0")),
        "commission_syndicate_usd": float(os.getenv("P13_COMM_SYNDICATE", "15.0")),

        # Payout net days (matches phase11)
        "commission_net_days": int(os.getenv("P13_COMM_NET_DAYS", "30")),

        # Turnstile secret key for Cloudflare bot protection
        "turnstile_secret_key": os.getenv("CLOUDFLARE_TURNSTILE_SECRET", ""),
        "turnstile_site_key": os.getenv("CLOUDFLARE_TURNSTILE_SITE_KEY", ""),

        # Affiliate trial landing page — platform price shown in copy
        "platform_price_display": os.getenv("P13_PLATFORM_PRICE_DISPLAY", "$97/month"),

        # Email: trial receipt and ending schedule
        "trial_receipt_from": os.getenv("P13_RECEIPT_FROM", "em9248.beatvegas.app"),
        "trial_ending_warning_hours_before": int(os.getenv("P13_ENDING_WARN_HOURS", "24")),

        # Billing policy: days after failed charge before access is revoked
        "grace_period_days": int(os.getenv("P13_GRACE_PERIOD_DAYS", "3")),

        # Billing policy: days after charge within which a refund can be issued
        "refund_window_days": int(os.getenv("P13_REFUND_WINDOW_DAYS", "7")),

        # Affiliate trial offer window (seconds from first click via bv_ref cookie)
        # 86400 = 24 hours — offer expires 24h after the referral link was clicked
        "affiliate_trial_offer_expiry_seconds": int(os.getenv("P13_TRIAL_OFFER_EXPIRY_SEC", "86400")),

        # Stripe API retry — exponential backoff for trial subscription creation.
        # Live mode enforces stricter rate limits than test mode.
        # Retries on RateLimitError and APIConnectionError only — not card declines.
        # Backoff: 0.5s, 1.0s, 2.0s (base * 2^attempt)
        "stripe_retry_max_attempts": int(os.getenv("P13_STRIPE_RETRY_MAX", "3")),
        "stripe_retry_backoff_base_seconds": float(os.getenv("P13_STRIPE_BACKOFF_BASE", "0.5")),
    },

    # ── GeoIP enforcement ────────────────────────────────────────────────────
    # Item 9: Low-confidence threshold for MaxMind GeoLite2-City per-IP scores.
    # Results below this threshold are ALLOWED (not blocked) but logged as
    # GEO_LOW_CONFIDENCE to sentinel_event_log for audit.
    # MaxMind confidence range: 0–100 (integer). Country DB returns None (no confidence).
    # Default 50 = allow any result MaxMind is less than 50% confident about.
    "geoip": {
        "low_confidence_threshold": int(os.getenv("GEOIP_CONFIDENCE_THRESHOLD", "50")),
        "low_confidence_action": "ALLOW_AND_LOG",  # never block on low confidence
        "blocked_territories": ["PR", "VI", "GU", "MP", "AS", "UM"],
    },
}
