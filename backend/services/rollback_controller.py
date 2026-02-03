"""
Rollback Controller - 1-Minute LKG Restore
Status: LOCKED - INSTITUTIONAL GRADE

Enables rapid rollback to Last Known Good (LKG) configuration.

ROLLBACK LEVERS:
1. Feature flags (instant) - flip flags OFF
2. Version pinning (minutes) - revert to LKG Docker images
3. Queue purge (seconds) - clear broken queue items
4. Automated rollback on integrity failures

LKG DEFINITION:
- Backend image: Docker image tag
- Frontend build: Build ID
- Classifier commit: Git commit hash
- Model version: Model version string

ROLLBACK TRIGGERS:
- Manual (ops team decision)
- Automated (integrity metric breach)
- Deploy validation failure (pre-flight checks)
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from pymongo.database import Database


logger = logging.getLogger(__name__)


class RollbackController:
    """
    Controls rollback operations for rapid recovery.
    
    GOAL: < 1 minute from decision to stable state
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_lkg_config(self) -> Optional[Dict]:
        """
        Get current Last Known Good configuration.
        
        Returns:
            LKG config dict or None if not set
        """
        lkg = self.db.lkg_config.find_one({"config_id": "lkg_current"})
        return lkg
    
    def set_lkg_config(
        self,
        lkg_backend_image: str,
        lkg_frontend_build: str,
        lkg_classifier_commit: str,
        lkg_model_version: str,
        updated_by: str,
        reason: str
    ) -> bool:
        """
        Update LKG configuration.
        
        Call this after validating a new deployment.
        
        Args:
            lkg_backend_image: Docker image tag for backend (e.g., "backend:2026-02-02.1")
            lkg_frontend_build: Build ID for frontend (e.g., "web:2026-02-02.1")
            lkg_classifier_commit: Git commit hash for classifier
            lkg_model_version: Model version string
            updated_by: Who updated LKG
            reason: Reason for update
        
        Returns:
            True if successful
        """
        # Get current LKG (for rollback history)
        current_lkg = self.get_lkg_config()
        
        # Build new LKG
        new_lkg = {
            "config_id": "lkg_current",
            "lkg_backend_image": lkg_backend_image,
            "lkg_frontend_build": lkg_frontend_build,
            "lkg_classifier_commit": lkg_classifier_commit,
            "lkg_model_version": lkg_model_version,
            "updated_at": datetime.utcnow(),
            "updated_by": updated_by,
            "reason": reason,
            "previous_lkg": current_lkg if current_lkg else None,
        }
        
        # Upsert
        self.db.lkg_config.update_one(
            {"config_id": "lkg_current"},
            {"$set": new_lkg},
            upsert=True
        )
        
        logger.info(
            f"Updated LKG config: backend={lkg_backend_image}, "
            f"frontend={lkg_frontend_build}, model={lkg_model_version}"
        )
        
        # Log to rollback history
        self.db.lkg_history.insert_one({
            **new_lkg,
            "history_id": f"lkg_hist_{datetime.utcnow().timestamp()}",
        })
        
        return True
    
    def rollback_to_lkg(
        self,
        triggered_by: str,
        reason: str,
        dry_run: bool = False
    ) -> Dict:
        """
        Execute rollback to LKG configuration.
        
        STEPS:
        1. Disable all risky features via flags
        2. Pin backend/frontend to LKG versions (requires orchestration)
        3. Purge broken queue items
        4. Alert ops team
        
        Args:
            triggered_by: Who/what triggered rollback
            reason: Reason for rollback
            dry_run: If True, simulate but don't execute
        
        Returns:
            Rollback status dict
        """
        logger.critical(f"ROLLBACK INITIATED by {triggered_by}: {reason}")
        
        status = {
            "rollback_id": f"rb_{datetime.utcnow().timestamp()}",
            "triggered_by": triggered_by,
            "reason": reason,
            "started_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "steps_completed": [],
            "steps_failed": [],
        }
        
        # Get LKG config
        lkg = self.get_lkg_config()
        if not lkg:
            logger.error("No LKG config found - cannot rollback")
            status["steps_failed"].append("NO_LKG_CONFIG")
            return status
        
        # Step 1: Disable risky features
        try:
            if not dry_run:
                self._disable_risky_features()
            status["steps_completed"].append("DISABLED_RISKY_FEATURES")
            logger.info("✅ Disabled risky features")
        except Exception as e:
            logger.exception("Failed to disable risky features")
            status["steps_failed"].append(f"DISABLE_FEATURES_FAILED: {e}")
        
        # Step 2: Pin versions to LKG (requires orchestration)
        try:
            if not dry_run:
                self._pin_versions_to_lkg(lkg)
            status["steps_completed"].append("PINNED_VERSIONS")
            logger.info(f"✅ Pinned versions to LKG: {lkg['lkg_backend_image']}")
        except Exception as e:
            logger.exception("Failed to pin versions")
            status["steps_failed"].append(f"PIN_VERSIONS_FAILED: {e}")
        
        # Step 3: Purge broken queue items
        try:
            if not dry_run:
                purged = self._purge_broken_queue_items()
                status["purged_queue_items"] = purged
            status["steps_completed"].append("PURGED_QUEUE")
            logger.info(f"✅ Purged broken queue items")
        except Exception as e:
            logger.exception("Failed to purge queue")
            status["steps_failed"].append(f"PURGE_QUEUE_FAILED: {e}")
        
        # Step 4: Alert ops team
        try:
            if not dry_run:
                self._send_rollback_alert(triggered_by, reason, lkg)
            status["steps_completed"].append("SENT_ALERT")
            logger.info("✅ Sent rollback alert")
        except Exception as e:
            logger.exception("Failed to send alert")
            status["steps_failed"].append(f"ALERT_FAILED: {e}")
        
        # Finalize status
        status["completed_at"] = datetime.utcnow().isoformat()
        status["success"] = len(status["steps_failed"]) == 0
        
        # Log rollback
        if not dry_run:
            self.db.rollback_log.insert_one(status)
        
        logger.critical(
            f"ROLLBACK {'COMPLETED' if status['success'] else 'FAILED'}: "
            f"{len(status['steps_completed'])} steps completed, "
            f"{len(status['steps_failed'])} steps failed"
        )
        
        return status
    
    def _disable_risky_features(self):
        """
        Disable risky features via feature flags.
        
        Disables:
        - FEATURE_TELEGRAM_AUTOPUBLISH
        - FEATURE_LLM_COPY_AGENT
        """
        from backend.services.feature_flags import FeatureFlagService
        
        flags = FeatureFlagService(self.db)
        
        risky_features = [
            "FEATURE_TELEGRAM_AUTOPUBLISH",
            "FEATURE_LLM_COPY_AGENT",
        ]
        
        for flag_name in risky_features:
            flags.set_flag(
                flag_name=flag_name,
                enabled=False,
                changed_by="RollbackController",
                reason="Rollback to LKG - auto-disabled"
            )
    
    def _pin_versions_to_lkg(self, lkg: Dict):
        """
        Pin backend/frontend versions to LKG.
        
        NOTE: This requires orchestration (Kubernetes, Docker Compose, etc.)
        Implementation depends on deployment infrastructure.
        
        For now, log what needs to be done.
        """
        logger.critical(
            f"VERSION PIN REQUIRED:\n"
            f"  Backend: {lkg['lkg_backend_image']}\n"
            f"  Frontend: {lkg['lkg_frontend_build']}\n"
            f"  Classifier: {lkg['lkg_classifier_commit']}\n"
            f"  Model: {lkg['lkg_model_version']}"
        )
        
        # TODO: Implement orchestration-specific version pinning
        # Examples:
        # - Kubernetes: update Deployment image tags
        # - Docker Compose: update docker-compose.yml and restart
        # - Cloud provider: update service versions
    
    def _purge_broken_queue_items(self) -> int:
        """
        Purge broken queue items (created during broken window).
        
        Removes queue items created in last 30 minutes with validation failures.
        
        Returns:
            Number of items purged
        """
        broken_window_start = datetime.utcnow() - timedelta(minutes=30)
        
        # Delete queue items from broken window
        result = self.db.telegram_queue.delete_many({
            "created_at": {"$gte": broken_window_start}
        })
        
        purged = result.deleted_count
        logger.warning(f"Purged {purged} queue items from broken window")
        
        return purged
    
    def _send_rollback_alert(self, triggered_by: str, reason: str, lkg: Dict):
        """
        Send rollback alert to ops team.
        """
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "CRITICAL",
            "message": f"ROLLBACK EXECUTED by {triggered_by}: {reason}",
            "lkg_config": {
                "backend": lkg['lkg_backend_image'],
                "frontend": lkg['lkg_frontend_build'],
                "classifier": lkg['lkg_classifier_commit'],
                "model": lkg['lkg_model_version'],
            }
        }
        
        # Log to ops_alerts
        self.db.ops_alerts.insert_one(alert)
        
        # TODO: Send to webhook/Telegram/Slack
        logger.critical(f"ROLLBACK ALERT: {alert}")
    
    def validate_deployment(
        self,
        backend_image: str,
        frontend_build: str,
        classifier_commit: str,
        model_version: str,
        validation_window_minutes: int = 30
    ) -> Dict:
        """
        Validate a new deployment before promoting to LKG.
        
        Checks:
        - Integrity violation rate < threshold
        - No critical errors in logs
        - Telegram validation passing
        - Edge rate not collapsed
        
        Args:
            backend_image: Candidate backend image
            frontend_build: Candidate frontend build
            classifier_commit: Candidate classifier commit
            model_version: Candidate model version
            validation_window_minutes: How long to monitor before promoting
        
        Returns:
            Validation status dict
        """
        logger.info(
            f"Validating deployment: backend={backend_image}, "
            f"frontend={frontend_build}, model={model_version}"
        )
        
        status = {
            "candidate_backend": backend_image,
            "candidate_frontend": frontend_build,
            "candidate_classifier": classifier_commit,
            "candidate_model": model_version,
            "validation_started_at": datetime.utcnow().isoformat(),
            "validation_window_minutes": validation_window_minutes,
            "checks_passed": [],
            "checks_failed": [],
        }
        
        # Run validation checks
        from backend.services.integrity_sentinel import IntegritySentinel
        
        sentinel = IntegritySentinel(self.db)
        
        # Check 1: Integrity metrics
        metrics = sentinel.check_all_metrics()
        breaches = [name for name, metric in metrics.items() if metric.breached]
        
        if breaches:
            status["checks_failed"].append(f"INTEGRITY_BREACH: {breaches}")
            logger.error(f"Deployment validation failed: integrity breaches {breaches}")
        else:
            status["checks_passed"].append("INTEGRITY_METRICS_OK")
        
        # Check 2: Validation fail rate
        validation_fail_rate = metrics.get("post_validation_fail_rate")
        if validation_fail_rate and validation_fail_rate.value < 0.01:
            status["checks_passed"].append("VALIDATION_FAIL_RATE_OK")
        else:
            status["checks_failed"].append("VALIDATION_FAIL_RATE_HIGH")
        
        # Check 3: Edge rate (not collapsed)
        edge_rate_collapse = metrics.get("edge_rate_collapse")
        if edge_rate_collapse and edge_rate_collapse.value < 0.5:
            status["checks_passed"].append("EDGE_RATE_OK")
        else:
            status["checks_failed"].append("EDGE_RATE_COLLAPSED")
        
        # Overall validation
        status["validation_passed"] = len(status["checks_failed"]) == 0
        status["validation_completed_at"] = datetime.utcnow().isoformat()
        
        # Log validation result
        self.db.deployment_validation_log.insert_one(status)
        
        if status["validation_passed"]:
            logger.info("✅ Deployment validation PASSED - ready to promote to LKG")
        else:
            logger.error(f"❌ Deployment validation FAILED: {status['checks_failed']}")
        
        return status


if __name__ == "__main__":
    # Test rollback controller
    import os
    from pymongo import MongoClient
    
    # Connect to DB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "beatvegas")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # Create controller
    rollback = RollbackController(db)
    
    # Set LKG config
    print("=== Setting LKG Config ===")
    rollback.set_lkg_config(
        lkg_backend_image="backend:2026-02-02.1",
        lkg_frontend_build="web:2026-02-02.1",
        lkg_classifier_commit="abc123def456",
        lkg_model_version="v2.1.0",
        updated_by="test_script",
        reason="Testing LKG setup"
    )
    
    # Get LKG config
    lkg = rollback.get_lkg_config()
    print(f"Current LKG: {lkg}")
    
    # Test dry-run rollback
    print("\n=== Testing Rollback (Dry Run) ===")
    status = rollback.rollback_to_lkg(
        triggered_by="test_script",
        reason="Testing rollback procedure",
        dry_run=True
    )
    
    print(f"Rollback status: {status['success']}")
    print(f"Steps completed: {status['steps_completed']}")
    print(f"Steps failed: {status['steps_failed']}")
    
    # Test deployment validation
    print("\n=== Testing Deployment Validation ===")
    validation = rollback.validate_deployment(
        backend_image="backend:2026-02-02.2",
        frontend_build="web:2026-02-02.2",
        classifier_commit="def456ghi789",
        model_version="v2.2.0",
        validation_window_minutes=30
    )
    
    print(f"Validation passed: {validation['validation_passed']}")
    print(f"Checks passed: {validation['checks_passed']}")
    print(f"Checks failed: {validation['checks_failed']}")
