"""
IntegritySentinel - Monitoring & Kill Switch Service
Status: LOCKED - INSTITUTIONAL GRADE

Monitors critical integrity metrics and auto-disables features if thresholds exceeded.

MONITORED METRICS:
1. integrity_violation_rate (canonical assertion failures + missing trace/snapshot continuity)
2. missing_selection_id_rate
3. missing_snapshot_hash_rate
4. post_validation_fail_rate (Telegram validation failures)
5. simulation_fetch_fail_rate
6. tier_distribution (edge rate collapse detection)

AUTO-DISABLE CONDITIONS (5-minute window):
- integrity_violation_rate > 0.5%
- OR missing_selection_id_rate > 0.1%
- OR snapshot_hash_missing_rate > 0.1%
- OR post_validation_fail_rate > 1%

ACTION: Set FEATURE_TELEGRAM_AUTOPUBLISH = OFF + alert ops team
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pymongo.database import Database


logger = logging.getLogger(__name__)


def _load_threshold(agent_config_key: str, default: float) -> float:
    """Read a threshold from agent_config; fall back to default if absent."""
    try:
        from config.agent_config import AGENT_CONFIG
        return float(AGENT_CONFIG.get("sentinel", {}).get(agent_config_key, default))
    except Exception:
        return default


@dataclass
class MetricThreshold:
    """Threshold definition for a metric."""

    metric_name: str
    threshold: float
    window_minutes: int
    action: str


@dataclass
class MetricValue:
    """Current metric value."""

    metric_name: str
    value: float
    timestamp: datetime
    breached: bool
    threshold: Optional[float] = None


class IntegritySentinel:
    """Monitors integrity metrics and enforces kill switches."""

    THRESHOLDS = [
        MetricThreshold("integrity_violation_rate", 0.005, 5, "DISABLE_TELEGRAM"),
        MetricThreshold("missing_selection_id_rate", 0.001, 5, "DISABLE_TELEGRAM"),
        MetricThreshold("missing_snapshot_hash_rate", 0.001, 5, "DISABLE_TELEGRAM"),
        MetricThreshold("post_validation_fail_rate", 0.01, 5, "DISABLE_TELEGRAM"),
        MetricThreshold("simulation_fetch_fail_rate", 0.05, 5, "ALERT"),
        MetricThreshold("edge_rate_collapse", 0.9, 30, "ALERT"),
        # ── Phase 2C security event monitors (thresholds from agent_config) ──
        MetricThreshold("geo_violation_rate", _load_threshold("GEO_VIOLATION_ALERT_COUNT", 50), 15, "ALERT"),
        MetricThreshold("auth_anomaly_rate", _load_threshold("AUTH_ANOMALY_THRESHOLD", 10), 5, "ALERT"),
        MetricThreshold("rate_limit_breach_rate", _load_threshold("RATE_LIMIT_BREACH_ALERT_THRESHOLD", 100), 15, "ALERT"),
        MetricThreshold("duplicate_decision_record_rate", _load_threshold("DUPLICATE_DR_ALERT_COUNT", 5), 60, "ALERT"),
        # ── Phase 3C billing monitors (all thresholds from agent_config) ──────
        MetricThreshold("billing_write_fail_rate", _load_threshold("BILLING_WRITE_FAIL_ALERT_THRESHOLD", 1), 5, "ALERT"),
        MetricThreshold("entitlement_violation_rate", _load_threshold("ENTITLEMENT_VIOLATION_ALERT_THRESHOLD", 3), 15, "ALERT"),
        MetricThreshold("overage_warn_rate", _load_threshold("OVERAGE_WARN_PCT", 80), 60, "ALERT"),
        MetricThreshold("overage_block_rate", _load_threshold("OVERAGE_BLOCK_PCT", 100), 60, "ALERT"),
        MetricThreshold("subscription_expiry_rate", _load_threshold("SUBSCRIPTION_EXPIRY_CHECK_WINDOW_MIN", 5), 5, "ALERT"),
        MetricThreshold("webhook_failure_rate", _load_threshold("WEBHOOK_FAIL_ALERT_THRESHOLD", 3), 15, "ALERT"),
    ]

    def __init__(self, db: Database, alert_webhook_url: Optional[str] = None):
        self.db = db
        self.alert_webhook_url = alert_webhook_url
        self.baseline_edge_rate: Optional[float] = None

    def _get_collection(self, *names: str):
        for name in names:
            try:
                return self.db.get_collection(name)
            except Exception:
                pass

            try:
                return self.db[name]
            except Exception:
                pass

            collection = getattr(self.db, name, None)
            if collection is not None:
                return collection

        raise AttributeError(f"Collection not available: {names}")

    def _window_query(self, field_name: str, window_start: datetime) -> Dict[str, Any]:
        return {field_name: {"$gte": window_start.isoformat()}}

    def _count_documents(self, collection_names: List[str], query: Dict[str, Any]) -> int:
        for name in collection_names:
            try:
                return int(self._get_collection(name).count_documents(query))
            except Exception:
                continue
        return 0

    def _safe_find_one(
        self,
        collection_names: List[str],
        query: Dict[str, Any],
        sort_field: str,
    ) -> Optional[Dict[str, Any]]:
        for name in collection_names:
            try:
                collection = self._get_collection(name)
                return collection.find_one(query, sort=[(sort_field, -1)])
            except TypeError:
                try:
                    docs = list(collection.find(query))
                    docs.sort(key=lambda doc: str(doc.get(sort_field, "")), reverse=True)
                    return docs[0] if docs else None
                except Exception:
                    continue
            except Exception:
                continue
        return None

    def check_all_metrics(self) -> Dict[str, MetricValue]:
        metrics: Dict[str, MetricValue] = {}
        for threshold in self.THRESHOLDS:
            metric_value = self._compute_metric(threshold)
            metrics[threshold.metric_name] = metric_value
            if metric_value.breached:
                logger.error(
                    "METRIC BREACH: %s = %.4f (threshold: %s)",
                    threshold.metric_name,
                    metric_value.value,
                    threshold.threshold,
                )
        return metrics

    def get_latest_status(self) -> Optional[Dict[str, Any]]:
        return self._safe_find_one(["sentinel_log"], {}, "timestamp")

    def enforce_kill_switches(self, metrics: Dict[str, MetricValue]) -> List[str]:
        actions_taken: List[str] = []
        autorollback_triggered = False

        for threshold in self.THRESHOLDS:
            metric_value = metrics.get(threshold.metric_name)
            if not metric_value or not metric_value.breached:
                continue

            if threshold.action == "DISABLE_TELEGRAM":
                if self._disable_telegram_autopublish():
                    actions_taken.append(f"DISABLED_TELEGRAM (due to {threshold.metric_name})")
                    self._send_alert(
                        severity="CRITICAL",
                        message=(
                            f"Auto-disabled Telegram publishing due to {threshold.metric_name} = "
                            f"{metric_value.value:.4f} (threshold: {threshold.threshold})"
                        ),
                        metric=metric_value,
                    )
                    rollback_action = None
                    if not autorollback_triggered:
                        rollback_action = self._maybe_trigger_autorollback(threshold.metric_name)
                    if rollback_action:
                        autorollback_triggered = rollback_action.startswith("AUTOROLLBACK_TRIGGERED")
                        actions_taken.append(f"{rollback_action} ({threshold.metric_name})")

            elif threshold.action == "ALERT":
                self._send_alert(
                    severity="WARNING",
                    message=(
                        f"Metric threshold breached: {threshold.metric_name} = "
                        f"{metric_value.value:.4f} (threshold: {threshold.threshold})"
                    ),
                    metric=metric_value,
                )
                actions_taken.append(f"ALERTED ({threshold.metric_name})")

            elif threshold.action == "ROLLBACK":
                self._send_alert(
                    severity="CRITICAL",
                    message=(
                        f"ROLLBACK REQUIRED: {threshold.metric_name} = "
                        f"{metric_value.value:.4f} (threshold: {threshold.threshold})"
                    ),
                    metric=metric_value,
                )
                actions_taken.append(f"ROLLBACK_REQUIRED ({threshold.metric_name})")

        return actions_taken

    def run_check_cycle(self, enforce_actions: bool = True) -> Dict[str, Any]:
        logger.info("Running IntegritySentinel check cycle")

        metrics = self.check_all_metrics()
        actions = self.enforce_kill_switches(metrics) if enforce_actions else []

        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {key: metric.value for key, metric in metrics.items()},
            "metric_details": {
                key: {
                    "value": metric.value,
                    "threshold": metric.threshold,
                    "breached": metric.breached,
                    "timestamp": metric.timestamp.isoformat(),
                }
                for key, metric in metrics.items()
            },
            "breaches": [key for key, metric in metrics.items() if metric.breached],
            "actions_taken": actions,
            "enforce_actions": enforce_actions,
        }

        self.db.sentinel_log.insert_one(status)
        logger.info(
            "Check cycle complete: %s breaches, %s actions",
            len(status["breaches"]),
            len(actions),
        )
        return status

    def _compute_metric(self, threshold: MetricThreshold) -> MetricValue:
        window_start = datetime.now(timezone.utc) - timedelta(minutes=threshold.window_minutes)

        if threshold.metric_name == "integrity_violation_rate":
            value = self._compute_integrity_violation_rate(window_start)
        elif threshold.metric_name == "missing_selection_id_rate":
            value = self._compute_missing_selection_id_rate(window_start)
        elif threshold.metric_name == "missing_snapshot_hash_rate":
            value = self._compute_missing_snapshot_hash_rate(window_start)
        elif threshold.metric_name == "post_validation_fail_rate":
            value = self._compute_post_validation_fail_rate(window_start)
        elif threshold.metric_name == "simulation_fetch_fail_rate":
            value = self._compute_simulation_fetch_fail_rate(window_start)
        elif threshold.metric_name == "edge_rate_collapse":
            value = self._compute_edge_rate_collapse(window_start)
        # ── Phase 2C security event metrics ──────────────────────────────────
        elif threshold.metric_name == "geo_violation_rate":
            value = self._compute_sentinel_event_count("GEO_VIOLATION", window_start)
        elif threshold.metric_name == "auth_anomaly_rate":
            value = self._compute_sentinel_event_count("AUTH_ANOMALY", window_start)
        elif threshold.metric_name == "rate_limit_breach_rate":
            value = self._compute_sentinel_event_count("RATE_LIMIT_BREACH", window_start)
        elif threshold.metric_name == "duplicate_decision_record_rate":
            value = self._compute_sentinel_event_count("DUPLICATE_DECISION_RECORD", window_start)
        # ── Phase 3C billing metrics ──────────────────────────────────────────
        elif threshold.metric_name == "billing_write_fail_rate":
            value = self._compute_sentinel_event_count("BILLING_WRITE_FAIL", window_start)
        elif threshold.metric_name == "entitlement_violation_rate":
            value = self._compute_sentinel_event_count("ENTITLEMENT_VIOLATION", window_start)
        elif threshold.metric_name == "overage_warn_rate":
            value = self._compute_sentinel_event_count("OVERAGE_WARN", window_start)
        elif threshold.metric_name == "overage_block_rate":
            value = self._compute_sentinel_event_count("OVERAGE_BLOCK", window_start)
        elif threshold.metric_name == "subscription_expiry_rate":
            value = self._compute_sentinel_event_count("SUBSCRIPTION_EXPIRED", window_start)
        elif threshold.metric_name == "webhook_failure_rate":
            value = self._compute_sentinel_event_count("WEBHOOK_FAILURE", window_start)
        else:
            logger.warning("Unknown metric: %s", threshold.metric_name)
            value = 0.0

        return MetricValue(
            metric_name=threshold.metric_name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            breached=value > threshold.threshold,
            threshold=threshold.threshold,
        )

    def _compute_integrity_violation_rate(self, window_start: datetime) -> float:
        lifecycle_query = {
            "stage": {"$in": ["PREDICTION_CREATED", "DECISION_COMPUTED", "PUBLISHED", "DISTRIBUTION_GOVERNANCE"]},
            **self._window_query("timestamp", window_start),
        }
        total = self._count_documents(["prediction_lifecycle_log"], lifecycle_query)
        if total == 0:
            total = self._count_documents(["decision_audit_log"], self._window_query("timestamp", window_start))
        if total == 0:
            return 0.0

        assertion_violations = self._count_documents(["assertion_failure_log"], self._window_query("created_at_utc", window_start))
        lifecycle_missing_ids = self._count_documents(
            ["prediction_lifecycle_log"],
            {
                **lifecycle_query,
                "$or": [
                    {"trace_id": {"$exists": False}},
                    {"trace_id": None},
                    {"trace_id": ""},
                    {"snapshot_hash": {"$exists": False}},
                    {"snapshot_hash": None},
                    {"snapshot_hash": ""},
                ],
            },
        )
        audit_missing_ids = self._count_documents(
            ["decision_audit_log"],
            {
                **self._window_query("timestamp", window_start),
                "$or": [
                    {"trace_id": {"$exists": False}},
                    {"trace_id": None},
                    {"trace_id": ""},
                    {"snapshot_hash": {"$exists": False}},
                    {"snapshot_hash": None},
                    {"snapshot_hash": ""},
                ],
            },
        )
        return (assertion_violations + lifecycle_missing_ids + audit_missing_ids) / total

    def _compute_missing_selection_id_rate(self, window_start: datetime) -> float:
        total = self._count_documents(["decision_records"], self._window_query("created_at", window_start))
        if total == 0:
            return 0.0

        missing = self._count_documents(
            ["decision_records"],
            {
                **self._window_query("created_at", window_start),
                "$or": [
                    {
                        "payload.spread": {"$ne": None},
                        "payload.spread.selection_id": {"$in": [None, ""]},
                    },
                    {
                        "payload.total": {"$ne": None},
                        "payload.total.selection_id": {"$in": [None, ""]},
                    },
                    {
                        "payload.moneyline": {"$ne": None},
                        "payload.moneyline.selection_id": {"$in": [None, ""]},
                    },
                ],
            },
        )
        return missing / total

    def _compute_missing_snapshot_hash_rate(self, window_start: datetime) -> float:
        total = self._count_documents(["prediction_lifecycle_log"], self._window_query("timestamp", window_start))
        if total == 0:
            return 0.0

        missing = self._count_documents(
            ["prediction_lifecycle_log", "decision_audit_log"],
            {
                **self._window_query("timestamp", window_start),
                "$or": [
                    {"snapshot_hash": {"$exists": False}},
                    {"snapshot_hash": None},
                    {"snapshot_hash": ""},
                ],
            },
        )
        return missing / total

    def _compute_post_validation_fail_rate(self, window_start: datetime) -> float:
        total = self._count_documents(["telegram_post_log"], self._window_query("created_at", window_start))
        if total == 0:
            return 0.0

        failed = self._count_documents(
            ["telegram_post_log"],
            {**self._window_query("created_at", window_start), "validation_failed": True},
        )
        return failed / total

    def _compute_simulation_fetch_fail_rate(self, window_start: datetime) -> float:
        total = self._count_documents(["odds_refresh_log"], self._window_query("refreshed_at", window_start))
        if total == 0:
            return 0.0

        failed = self._count_documents(
            ["odds_refresh_log"],
            {**self._window_query("refreshed_at", window_start), "success": False},
        )
        return failed / total

    def _compute_edge_rate_collapse(self, window_start: datetime) -> float:
        total = self._count_documents(["decision_audit_log"], self._window_query("timestamp", window_start))
        if total == 0:
            return 0.0

        edges = self._count_documents(
            ["decision_audit_log"],
            {**self._window_query("timestamp", window_start), "classification": "EDGE"},
        )
        current_edge_rate = edges / total

        if self.baseline_edge_rate is None:
            baseline_start = datetime.now(timezone.utc) - timedelta(days=7)
            baseline_total = self._count_documents(["decision_audit_log"], self._window_query("timestamp", baseline_start))
            if baseline_total > 0:
                baseline_edges = self._count_documents(
                    ["decision_audit_log"],
                    {**self._window_query("timestamp", baseline_start), "classification": "EDGE"},
                )
                self.baseline_edge_rate = baseline_edges / baseline_total
            else:
                self.baseline_edge_rate = 0.05

        if self.baseline_edge_rate == 0:
            return 0.0

        collapse_ratio = 1.0 - (current_edge_rate / self.baseline_edge_rate)
        return max(0.0, collapse_ratio)

    # ── Phase 2C: sentinel_event_log counters ─────────────────────────────────

    def _compute_sentinel_event_count(self, event_type: str, window_start: datetime) -> float:
        """
        Count events of the given type in sentinel_event_log within the window.
        Returns raw count (not a rate) — thresholds are absolute counts, not fractions.
        """
        return float(
            self._count_documents(
                ["sentinel_event_log"],
                {
                    "event_type": event_type,
                    **self._window_query("timestamp", window_start),
                },
            )
        )

    def _disable_telegram_autopublish(self) -> bool:
        from services.feature_flags import FeatureFlagService

        flags = FeatureFlagService(self.db)
        return flags.set_flag(
            flag_name="FEATURE_TELEGRAM_AUTOPUBLISH",
            enabled=False,
            changed_by="IntegritySentinel",
            reason="Auto-disabled due to integrity metric breach",
        )

    def _should_autorollback(self) -> bool:
        from services.feature_flags import FeatureFlagService

        return FeatureFlagService(self.db).is_enabled("FEATURE_AUTOROLLBACK_ON_INTEGRITY")

    def _maybe_trigger_autorollback(self, triggering_metric: str) -> Optional[str]:
        if not self._should_autorollback():
            return None

        from services.rollback_controller import RollbackController

        rollback = RollbackController(self.db)
        if not rollback.get_lkg_config():
            self.db.ops_alerts.insert_one(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "severity": "CRITICAL",
                    "message": f"AUTOROLLBACK_SKIPPED_NO_LKG for {triggering_metric}",
                    "triggering_metric": triggering_metric,
                }
            )
            return "AUTOROLLBACK_SKIPPED_NO_LKG"

        result = rollback.rollback_to_lkg(
            triggered_by="IntegritySentinel",
            reason=f"Integrity breach on {triggering_metric}",
            dry_run=False,
        )
        return "AUTOROLLBACK_TRIGGERED" if result.get("success") else "AUTOROLLBACK_FAILED"

    def _send_alert(self, severity: str, message: str, metric: MetricValue):
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "message": message,
            "metric": {
                "name": metric.metric_name,
                "value": metric.value,
                "threshold": metric.threshold,
            },
        }
        self.db.ops_alerts.insert_one(alert)

        if self.alert_webhook_url:
            try:
                import requests

                requests.post(self.alert_webhook_url, json=alert, timeout=5)
            except Exception as exc:
                logger.error("Failed to send webhook alert: %s", exc)

        log_fn = logger.critical if severity == "CRITICAL" else logger.warning
        log_fn("[%s] %s", severity, message)


class SentinelDaemon:
    """Daemon that runs IntegritySentinel continuously."""

    def __init__(
        self,
        db: Database,
        alert_webhook_url: Optional[str] = None,
        check_interval_seconds: int = 60,
    ):
        self.sentinel = IntegritySentinel(db, alert_webhook_url)
        self.check_interval_seconds = check_interval_seconds
        self.running = False

    def start(self):
        import time

        self.running = True
        logger.info("Starting SentinelDaemon (check interval: %ss)", self.check_interval_seconds)

        while self.running:
            try:
                status = self.sentinel.run_check_cycle()
                if status["breaches"]:
                    logger.warning("Breaches detected: %s", status["breaches"])
                else:
                    logger.debug("All metrics within thresholds")
            except Exception as exc:
                logger.exception("Error in sentinel check cycle: %s", exc)
            time.sleep(self.check_interval_seconds)

    def stop(self):
        logger.info("Stopping SentinelDaemon")
        self.running = False


_integrity_sentinel: Optional[IntegritySentinel] = None


def get_integrity_sentinel() -> IntegritySentinel:
    global _integrity_sentinel
    if _integrity_sentinel is None:
        from db.mongo import db

        _integrity_sentinel = IntegritySentinel(db)
    return _integrity_sentinel


if __name__ == "__main__":
    import os
    from pymongo import MongoClient

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "beatvegas")
    client = MongoClient(mongo_uri)
    db = client[db_name]

    sentinel = IntegritySentinel(db=db, alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL"))
    status = sentinel.run_check_cycle()

    print("=== IntegritySentinel Status ===")
    print(f"Timestamp: {status['timestamp']}")
    print(f"Metrics: {status['metrics']}")
    print(f"Breaches: {status['breaches']}")
    print(f"Actions: {status['actions_taken']}")
