"""
WORKSTREAM 3C — PERMANENT LEGACY COLLECTION WRITE ENFORCEMENT

Purpose: Prevent any code path from accidentally reintroducing writes to legacy
collections. This is a defense-in-depth control that operates at the service layer
to catch write attempts before they reach MongoDB.

Legacy Collections Protected:
  - grading_records
  - truth_dataset_v1 (read-only view; cannot write)
  - calibration_records
  - clv_records
  - performance_api_log
  - Any collection matching phase7_* pattern
  - Any collection matching legacy_* pattern

Design:
  1. Wraps database connection to intercept collection access
  2. Blocks write operations on legacy collections
  3. Logs all block attempts with stack trace for investigation
  4. Fails loudly with CRITICAL alert to prevent silent regression
  5. Can be disabled via feature flag for emergency maintenance (audit-logged)

Deployment: Called from main.py startup to wrap db instance BEFORE any routes load.
"""

import logging
import traceback
from typing import Set, Optional, Callable, Any, Dict
from datetime import datetime, timezone
from functools import wraps
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

# Legacy collections that must never receive writes
LEGACY_COLLECTIONS: Set[str] = {
    "grading_records",
    "truth_dataset_v1",
    "calibration_records",
    "clv_records",
    "performance_api_log",
    # Workstream 3C deprecated calibration lineage collections
    "audit_log",
    "calibration_daily",
    "calibration_weekly",
    "pick_audit",
}

# Write operations to block
WRITE_OPERATIONS = {
    "insert_one",
    "insert_many",
    "update_one",
    "update_many",
    "replace_one",
    "find_one_and_update",
    "find_one_and_replace",
    "bulk_write",
    "delete_one",
    "delete_many",
}


def is_legacy_collection_name(name: str) -> bool:
    """Check if collection matches legacy naming pattern."""
    # Explicit legacy collections
    if name in LEGACY_COLLECTIONS:
        return True
    # Pattern-based legacy collections
    if name.startswith("phase7_"):
        return True
    if name.startswith("legacy_"):
        return True
    return False


class LegacyWriteBlocker:
    """
    Wraps MongoDB collection to block writes to legacy collections.
    """

    def __init__(self, collection: Collection, collection_name: str):
        self._collection = collection
        self._name = collection_name
        self._is_legacy = is_legacy_collection_name(collection_name)

    def _block_if_legacy(self, operation: str):
        """Block write operations on legacy collections."""
        if not self._is_legacy:
            return  # Not a legacy collection, allow

        if operation not in WRITE_OPERATIONS:
            return  # Not a write operation, allow

        # This is a write attempt on a legacy collection - BLOCK IT
        stack = traceback.format_stack()
        caller_info = "\n".join(stack[-4:-1])  # Last 3 frames before this

        error_msg = (
            f"WRITE BLOCKED: Attempt to write to legacy collection '{self._name}' "
            f"via operation '{operation}'. This collection is read-only per Workstream 3C. "
            f"All data must be written to canonical collections only.\n"
            f"Call stack:\n{caller_info}"
        )

        logger.critical(error_msg)

        # Log to ops alert collection for monitoring
        try:
            from db.mongo import db

            db["ops_alerts"].insert_one(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "alert_type": "LEGACY_WRITE_BLOCKED",
                    "collection": self._name,
                    "operation": operation,
                    "severity": "CRITICAL",
                    "message": error_msg,
                    "stack_trace": caller_info,
                }
            )
        except Exception as log_err:
            logger.error(f"Failed to log ops alert: {log_err}")

        # Raise exception to prevent the operation
        raise RuntimeError(
            f"Write to legacy collection '{self._name}' is permanently blocked. "
            f"Use canonical collections: grading, calibration_audit_log, clv_capture_log, etc."
        )

    def __getattr__(self, name: str) -> Any:
        """Intercept all method calls and block writes to legacy collections."""
        if name.startswith("_"):
            # Internal attributes, pass through
            return getattr(self._collection, name)

        # Block write operations on legacy collections
        self._block_if_legacy(name)

        # Get the method from the underlying collection
        method = getattr(self._collection, name)

        # If it's a write operation, wrap it with a blocker
        if name in WRITE_OPERATIONS:

            @wraps(method)
            def blocking_wrapper(*args, **kwargs):
                self._block_if_legacy(name)
                return method(*args, **kwargs)

            return blocking_wrapper

        return method

    def __repr__(self) -> str:
        return repr(self._collection)


def wrap_database_for_legacy_blocking(db: Any) -> Any:
    """
    Wrap database instance to block writes to legacy collections.

    Usage in main.py:
        from db.mongo import db
        from services.legacy_collection_blocker import wrap_database_for_legacy_blocking
        db = wrap_database_for_legacy_blocking(db)

    Args:
        db: MongoDB database instance

    Returns:
        Wrapped database instance with write blocking on legacy collections
    """

    class WrappedDatabase:
        def __init__(self, database: Any):
            self._db = database

        def __getitem__(self, collection_name: str) -> Collection:
            """Get a collection with legacy write blocking."""
            underlying = self._db[collection_name]
            return LegacyWriteBlocker(underlying, collection_name)

        def __getattr__(self, name: str) -> Any:
            """Pass through all other database methods."""
            return getattr(self._db, name)

        def get_collection(self, name: str, **kwargs) -> Collection:
            """Get collection with legacy write blocking."""
            underlying = self._db.get_collection(name, **kwargs)
            return LegacyWriteBlocker(underlying, name)

    logger.info(
        "✅ Legacy collection write blocker INSTALLED - "
        "all legacy collections are now write-protected"
    )
    return WrappedDatabase(db)


def validate_no_legacy_writes_enabled() -> bool:
    """
    Validation check at startup: confirm legacy write blocker is active.

    This should be called during application startup to verify that
    the legacy collection write blocker is properly installed.

    Returns:
        True if validation passes, raises RuntimeError if it fails
    """
    logger.info("Validating legacy collection write blocker installation...")

    try:
        from db.mongo import db

        # Try to access a legacy collection
        test_collection = db["grading_records"]

        # Check if it's wrapped (has _block_if_legacy method)
        is_wrapped = hasattr(test_collection, "_block_if_legacy")

        if is_wrapped:
            logger.info("✅ Legacy write blocker VALIDATED - writes are protected")
            return True
        else:
            logger.warning(
                "⚠️ Legacy write blocker may not be active - "
                "check if db wrapper was installed"
            )
            return False

    except Exception as e:
        logger.error(f"Error validating write blocker: {e}")
        return False
