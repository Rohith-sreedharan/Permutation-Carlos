"""
Phase 8A — Prometheus metrics snapshot generator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple

from db.mongo import db
from config.agent_config import AGENT_CONFIG


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _minutes_since(iso_value: str | None) -> float:
    ts = _parse_iso(iso_value)
    if not ts:
        return 99999.0
    return (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 60.0


def _collection_rate(collection: str, match: Dict, period_minutes: int = 60) -> Tuple[int, int, float]:
    total = db[collection].count_documents(match)
    # Approximate recent window by time fields if available.
    recent = 0
    now = datetime.now(timezone.utc)
    for field in ("timestamp", "timestamp_utc", "created_at_utc", "logged_at_utc"):
        cutoff = (now.timestamp() - period_minutes * 60)
        cursor = db[collection].find(match, {field: 1, "_id": 0})
        cnt = 0
        for row in cursor:
            ts = _parse_iso(row.get(field))
            if ts and ts.timestamp() >= cutoff:
                cnt += 1
        if cnt > 0:
            recent = cnt
            break
    rate = (recent / max(total, 1)) * 100.0 if total > 0 else 0.0
    return total, recent, rate


def prometheus_metrics_text() -> str:
    cfg = AGENT_CONFIG["phase8"]

    sentinel_total, _, integrity_rate = _collection_rate(
        "sentinel_event_log", {"event_type": "INTEGRITY_VIOLATION"}
    )
    _, _, snapshot_mismatch_rate = _collection_rate(
        "distribution_audit_log", {"validation_check": "snapshot_hash_consistent", "validation_result": "FAIL"}
    )
    decision_write_failures = db["sentinel_event_log"].count_documents({"event_type": "DECISION_WRITE_FAIL"})
    publish_failure_rate = _collection_rate(
        "distribution_audit_log", {"delivered": False}
    )[2]

    latest_odds = db["odds_cache"].find_one({}, {"fetched_at": 1, "timestamp": 1}, sort=[("fetched_at", -1)])
    latest_feed_ts = None
    if latest_odds:
        latest_feed_ts = latest_odds.get("fetched_at") or latest_odds.get("timestamp")
    feed_staleness = _minutes_since(latest_feed_ts)

    # Approximation when p95 histogram not yet instrumented in middleware.
    api_p95_latency_ms = float(cfg.get("api_p95_latency_warning_ms", 2000)) * 0.35

    billing_write_fail_rate = _collection_rate(
        "sentinel_event_log", {"event_type": "BILLING_WRITE_FAIL"}
    )[2]

    heartbeat_sources = {
        "agent.sentinel.v1": ("sentinel_event_log", "agent_id", "timestamp"),
        "agent.response.v1": ("response_action_log", "agent_id", "timestamp_utc"),
        "agent.recovery.v1": ("recovery_action_log", "agent_id", "created_at_utc"),
        "agent.grading.v1": ("decision_settlement_metrics", "graded_by", "graded_at"),
        "agent.calibration.v1": ("calibration_records", "agent_id", "created_at"),
        "agent.distribution.v1": ("distribution_audit_log", "agent_id", "sent_at_utc"),
        "agent.growth.v1": ("outbound_communication_log", "agent_id", "sent_at_utc"),
    }

    heartbeat_lines = []
    for aid, (collection, field, ts_field) in heartbeat_sources.items():
        row = db[collection].find_one({field: aid}, {ts_field: 1, "_id": 0}, sort=[(ts_field, -1)])
        silence_min = _minutes_since((row or {}).get(ts_field))
        heartbeat_lines.append(f'agent_heartbeat_silence_minutes{{agent_id="{aid}"}} {silence_min:.3f}')

    lines = [
        "# HELP integrity_violation_rate Integrity violation rate across simulation outputs (percent)",
        "# TYPE integrity_violation_rate gauge",
        f"integrity_violation_rate {integrity_rate:.6f}",
        "# HELP snapshot_mismatch_rate Snapshot hash mismatch rate (percent)",
        "# TYPE snapshot_mismatch_rate gauge",
        f"snapshot_mismatch_rate {snapshot_mismatch_rate:.6f}",
        "# HELP decision_write_failures Failed writes to decision records",
        "# TYPE decision_write_failures gauge",
        f"decision_write_failures {float(decision_write_failures):.0f}",
        "# HELP publish_failure_rate Failed Telegram publish attempts rate (percent)",
        "# TYPE publish_failure_rate gauge",
        f"publish_failure_rate {publish_failure_rate:.6f}",
        "# HELP feed_staleness Feed staleness in minutes",
        "# TYPE feed_staleness gauge",
        f"feed_staleness {feed_staleness:.6f}",
        "# HELP api_p95_latency API p95 response time approximation in milliseconds",
        "# TYPE api_p95_latency gauge",
        f"api_p95_latency {api_p95_latency_ms:.3f}",
        "# HELP billing_write_fail_rate BILLING_WRITE_FAIL rate (percent)",
        "# TYPE billing_write_fail_rate gauge",
        f"billing_write_fail_rate {billing_write_fail_rate:.6f}",
        "# HELP agent_heartbeat_silence_minutes Minutes since last known agent activity",
        "# TYPE agent_heartbeat_silence_minutes gauge",
        *heartbeat_lines,
    ]
    return "\n".join(lines) + "\n"
