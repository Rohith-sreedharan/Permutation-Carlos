"""
IntegritySentinel - Monitoring & Kill Switch Service
Status: LOCKED - INSTITUTIONAL GRADE

Monitors critical integrity metrics and auto-disables features if thresholds exceeded.

MONITORED METRICS:
1. integrity_violation_rate (missing snapshot_hash, selection_id, etc.)
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
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pymongo.database import Database
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class MetricThreshold:
    """Threshold definition for a metric"""
    metric_name: str
    threshold: float
    window_minutes: int
    action: str  # "DISABLE_TELEGRAM", "ALERT", "ROLLBACK"


@dataclass
class MetricValue:
    """Current metric value"""
    metric_name: str
    value: float
    timestamp: datetime
    breached: bool
    threshold: Optional[float] = None


class IntegritySentinel:
    """
    Monitors integrity metrics and enforces kill switches.
    
    CRITICAL: This runs continuously (every 1-5 minutes).
    If thresholds breached → immediate action (no delays).
    """
    
    # Metric thresholds (from spec)
    THRESHOLDS = [
        MetricThreshold(
            metric_name="integrity_violation_rate",
            threshold=0.005,  # 0.5%
            window_minutes=5,
            action="DISABLE_TELEGRAM"
        ),
        MetricThreshold(
            metric_name="missing_selection_id_rate",
            threshold=0.001,  # 0.1%
            window_minutes=5,
            action="DISABLE_TELEGRAM"
        ),
        MetricThreshold(
            metric_name="missing_snapshot_hash_rate",
            threshold=0.001,  # 0.1%
            window_minutes=5,
            action="DISABLE_TELEGRAM"
        ),
        MetricThreshold(
            metric_name="post_validation_fail_rate",
            threshold=0.01,  # 1%
            window_minutes=5,
            action="DISABLE_TELEGRAM"
        ),
        MetricThreshold(
            metric_name="simulation_fetch_fail_rate",
            threshold=0.05,  # 5%
            window_minutes=5,
            action="ALERT"
        ),
        MetricThreshold(
            metric_name="edge_rate_collapse",
            threshold=0.9,  # 90% drop from baseline
            window_minutes=30,
            action="ALERT"
        ),
    ]
    
    def __init__(self, db: Database, alert_webhook_url: Optional[str] = None):
        """
        Initialize sentinel.
        
        Args:
            db: MongoDB database connection
            alert_webhook_url: Webhook URL for alerts (Slack, Telegram, etc.)
        """
        self.db = db
        self.alert_webhook_url = alert_webhook_url
        
        # Baseline metrics (for anomaly detection)
        self.baseline_edge_rate: Optional[float] = None
    
    def check_all_metrics(self) -> Dict[str, MetricValue]:
        """
        Check all monitored metrics.
        
        Returns:
            Dict of metric_name -> MetricValue
        """
        metrics = {}
        
        # Check each threshold
        for threshold in self.THRESHOLDS:
            metric_value = self._compute_metric(threshold)
            metrics[threshold.metric_name] = metric_value
            
            # Log if breached
            if metric_value.breached:
                logger.error(
                    f"METRIC BREACH: {threshold.metric_name} = {metric_value.value:.4f} "
                    f"(threshold: {threshold.threshold})"
                )
        
        return metrics
    
    def enforce_kill_switches(self, metrics: Dict[str, MetricValue]) -> List[str]:
        """
        Enforce kill switches based on metric breaches.
        
        Returns:
            List of actions taken
        """
        actions_taken = []
        
        for threshold in self.THRESHOLDS:
            metric_value = metrics.get(threshold.metric_name)
            
            if not metric_value or not metric_value.breached:
                continue
            
            # Execute action
            if threshold.action == "DISABLE_TELEGRAM":
                if self._disable_telegram_autopublish():
                    actions_taken.append(f"DISABLED_TELEGRAM (due to {threshold.metric_name})")
                    self._send_alert(
                        severity="CRITICAL",
                        message=f"Auto-disabled Telegram publishing due to {threshold.metric_name} = {metric_value.value:.4f} (threshold: {threshold.threshold})",
                        metric=metric_value,
                    )
            
            elif threshold.action == "ALERT":
                self._send_alert(
                    severity="WARNING",
                    message=f"Metric threshold breached: {threshold.metric_name} = {metric_value.value:.4f} (threshold: {threshold.threshold})",
                    metric=metric_value,
                )
                actions_taken.append(f"ALERTED ({threshold.metric_name})")
            
            elif threshold.action == "ROLLBACK":
                # Future: implement automated rollback
                self._send_alert(
                    severity="CRITICAL",
                    message=f"ROLLBACK REQUIRED: {threshold.metric_name} = {metric_value.value:.4f} (threshold: {threshold.threshold})",
                    metric=metric_value,
                )
                actions_taken.append(f"ROLLBACK_REQUIRED ({threshold.metric_name})")
        
        return actions_taken
    
    def run_check_cycle(self) -> Dict:
        """
        Run one complete check cycle.
        
        Returns:
            Status dict
        """
        logger.info("Running IntegritySentinel check cycle")
        
        # Check metrics
        metrics = self.check_all_metrics()
        
        # Enforce kill switches
        actions = self.enforce_kill_switches(metrics)
        
        # Build status
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {k: v.value for k, v in metrics.items()},
            "breaches": [k for k, v in metrics.items() if v.breached],
            "actions_taken": actions,
        }
        
        # Log to sentinel_log collection
        self.db.sentinel_log.insert_one(status)
        
        logger.info(f"Check cycle complete: {len(status['breaches'])} breaches, {len(actions)} actions")
        
        return status
    
    def _compute_metric(self, threshold: MetricThreshold) -> MetricValue:
        """
        Compute metric value and check against threshold.
        
        Returns:
            MetricValue with breach status
        """
        window_start = datetime.utcnow() - timedelta(minutes=threshold.window_minutes)
        
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
        
        else:
            logger.warning(f"Unknown metric: {threshold.metric_name}")
            value = 0.0
        
        breached = value > threshold.threshold
        
        return MetricValue(
            metric_name=threshold.metric_name,
            value=value,
            timestamp=datetime.utcnow(),
            breached=breached,
            threshold=threshold.threshold,
        )
    
    def _compute_integrity_violation_rate(self, window_start: datetime) -> float:
        """
        Compute rate of integrity violations (any type).
        
        Integrity violations include:
        - Missing snapshot_hash
        - Missing selection_id
        - Probability mismatches
        - etc.
        """
        # Query prediction_log for recent entries
        total = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start}
        })
        
        if total == 0:
            return 0.0
        
        # Count violations (integrity_violations field exists and non-empty)
        violations = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start},
            "integrity_violations": {"$exists": True, "$ne": []}
        })
        
        return violations / total
    
    def _compute_missing_selection_id_rate(self, window_start: datetime) -> float:
        """Compute rate of missing selection_id"""
        total = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start}
        })
        
        if total == 0:
            return 0.0
        
        missing = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start},
            "$or": [
                {"selection_id": {"$exists": False}},
                {"selection_id": None},
                {"selection_id": ""},
            ]
        })
        
        return missing / total
    
    def _compute_missing_snapshot_hash_rate(self, window_start: datetime) -> float:
        """Compute rate of missing snapshot_hash"""
        total = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start}
        })
        
        if total == 0:
            return 0.0
        
        missing = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start},
            "$or": [
                {"snapshot_hash": {"$exists": False}},
                {"snapshot_hash": None},
                {"snapshot_hash": ""},
            ]
        })
        
        return missing / total
    
    def _compute_post_validation_fail_rate(self, window_start: datetime) -> float:
        """Compute rate of Telegram post validation failures"""
        total = self.db.telegram_post_log.count_documents({
            "created_at": {"$gte": window_start}
        })
        
        if total == 0:
            return 0.0
        
        failed = self.db.telegram_post_log.count_documents({
            "created_at": {"$gte": window_start},
            "validation_failed": True
        })
        
        return failed / total
    
    def _compute_simulation_fetch_fail_rate(self, window_start: datetime) -> float:
        """Compute rate of simulation fetch failures"""
        # This would query API request logs or similar
        # For now, placeholder
        return 0.0
    
    def _compute_edge_rate_collapse(self, window_start: datetime) -> float:
        """
        Detect edge rate collapse (anomaly detection).
        
        Returns:
            Collapse ratio (0.0 = no collapse, 1.0 = 100% collapse)
        """
        # Compute current edge rate
        total = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start}
        })
        
        if total == 0:
            return 0.0
        
        edges = self.db.prediction_log.count_documents({
            "created_at": {"$gte": window_start},
            "tier": "EDGE"
        })
        
        current_edge_rate = edges / total
        
        # Get baseline (if not set, compute from last 7 days)
        if self.baseline_edge_rate is None:
            baseline_start = datetime.utcnow() - timedelta(days=7)
            baseline_total = self.db.prediction_log.count_documents({
                "created_at": {"$gte": baseline_start}
            })
            
            if baseline_total > 0:
                baseline_edges = self.db.prediction_log.count_documents({
                    "created_at": {"$gte": baseline_start},
                    "tier": "EDGE"
                })
                self.baseline_edge_rate = baseline_edges / baseline_total
            else:
                self.baseline_edge_rate = 0.05  # Default 5% edge rate
        
        # Compute collapse ratio
        if self.baseline_edge_rate == 0:
            return 0.0
        
        collapse_ratio = 1.0 - (current_edge_rate / self.baseline_edge_rate)
        
        return max(0.0, collapse_ratio)  # Clamp to [0, inf)
    
    def _disable_telegram_autopublish(self) -> bool:
        """
        Disable Telegram autopublish feature flag.
        
        Returns:
            True if flag was changed, False if already disabled
        """
        # Update feature flag
        result = self.db.feature_flags.update_one(
            {"flag_name": "FEATURE_TELEGRAM_AUTOPUBLISH"},
            {
                "$set": {
                    "enabled": False,
                    "changed_by": "IntegritySentinel",
                    "changed_at": datetime.utcnow(),
                    "reason": "Auto-disabled due to integrity metric breach"
                }
            },
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            logger.critical("DISABLED Telegram autopublish via kill switch")
            return True
        
        logger.warning("Telegram autopublish already disabled")
        return False
    
    def _send_alert(self, severity: str, message: str, metric: MetricValue):
        """
        Send alert to ops team.
        
        Args:
            severity: CRITICAL, WARNING, INFO
            message: Alert message
            metric: Metric that triggered alert
        """
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "message": message,
            "metric": {
                "name": metric.metric_name,
                "value": metric.value,
                "threshold": metric.threshold,
            }
        }
        
        # Log to database
        self.db.ops_alerts.insert_one(alert)
        
        # Send to webhook (if configured)
        if self.alert_webhook_url:
            try:
                import requests
                requests.post(
                    self.alert_webhook_url,
                    json=alert,
                    timeout=5
                )
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")
        
        # Log locally
        log_fn = logger.critical if severity == "CRITICAL" else logger.warning
        log_fn(f"[{severity}] {message}")


# ==================== CONTINUOUS MONITOR ====================

class SentinelDaemon:
    """
    Daemon that runs IntegritySentinel continuously.
    
    Run this in a separate process/container in production.
    """
    
    def __init__(
        self,
        db: Database,
        alert_webhook_url: Optional[str] = None,
        check_interval_seconds: int = 60
    ):
        self.sentinel = IntegritySentinel(db, alert_webhook_url)
        self.check_interval_seconds = check_interval_seconds
        self.running = False
    
    def start(self):
        """Start daemon (blocking)"""
        import time
        
        self.running = True
        logger.info(f"Starting SentinelDaemon (check interval: {self.check_interval_seconds}s)")
        
        while self.running:
            try:
                status = self.sentinel.run_check_cycle()
                
                # Log summary
                if status["breaches"]:
                    logger.warning(f"Breaches detected: {status['breaches']}")
                else:
                    logger.debug("All metrics within thresholds")
                
            except Exception as e:
                logger.exception(f"Error in sentinel check cycle: {e}")
            
            # Sleep until next check
            time.sleep(self.check_interval_seconds)
    
    def stop(self):
        """Stop daemon"""
        logger.info("Stopping SentinelDaemon")
        self.running = False


if __name__ == "__main__":
    # Test sentinel
    import os
    from pymongo import MongoClient
    
    # Connect to DB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "beatvegas")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # Create sentinel
    sentinel = IntegritySentinel(
        db=db,
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL")
    )
    
    # Run one check cycle
    status = sentinel.run_check_cycle()
    
    print("=== IntegritySentinel Status ===")
    print(f"Timestamp: {status['timestamp']}")
    print(f"Metrics: {status['metrics']}")
    print(f"Breaches: {status['breaches']}")
    print(f"Actions: {status['actions_taken']}")
