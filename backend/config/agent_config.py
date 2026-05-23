"""
Agent Config — Phase 2C

Single source of truth for all Sentinel monitoring thresholds.
Zero hardcoded values in any middleware or service file.
All values are overridable via environment variables at runtime.
"""
import os

AGENT_CONFIG: dict = {
    # ── Rate limiting ────────────────────────────────────────────────────────
    "rate_limiting": {
        "rate_limit_per_user_rpm": int(os.getenv("RATE_LIMIT_USER_RPM", "120")),
        "rate_limit_per_ip_rpm": int(os.getenv("RATE_LIMIT_IP_RPM", "60")),
        "rate_limit_burst_multiplier": float(os.getenv("RATE_LIMIT_BURST", "1.5")),
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
    },
}
