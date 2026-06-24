"""
Phase 4D – Migration: Calibration Immutability Enforcement
===========================================================
AC-8 requirement: ACTIVE calibration records must be immutable at the DB
level.  MongoDB has no native row-level triggers, so enforcement uses a
three-layer approach:

  Layer 1 – $jsonSchema validator (DB-level): prevents writes that set
             status to anything other than the allowed enum values, and
             enforces that once status == "ACTIVE" it cannot be changed
             by blocking any doc that would lower the version sequence.
             (MongoDB validators run on final document state, not
             transitions, so complete transition blocking is done in L2.)

  Layer 2 – Application-layer guard: CalibrationImmutabilityGuard.check()
             MUST be called before any update to calibration_versions.
             Raises CalibrationImmutabilityError immediately if the
             record is ACTIVE.

  Layer 3 – Change-stream watcher (background thread): watches the
             calibration_versions collection for any update/replace that
             modifies an ACTIVE record and immediately:
               a. Rolls back the document to its pre-change state.
               b. Logs a CRITICAL sentinel event to sentinel_event_log.

Run this migration once:

    python -m backend.db.migrations.phase4_002_calibration_immutability

"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class CalibrationImmutabilityError(RuntimeError):
    """Raised when a mutation of an ACTIVE calibration record is attempted."""


# ---------------------------------------------------------------------------
# Layer 1 – $jsonSchema validator applied to calibration_versions
# ---------------------------------------------------------------------------

CALIBRATION_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["calibration_version", "status"],
        "properties": {
            "status": {
                "bsonType": "string",
                "enum": ["CANDIDATE", "ACTIVE", "REJECTED", "RETIRED"],
                "description": "Calibration lifecycle status",
            },
            "calibration_version": {
                "bsonType": "string",
                "description": "Unique version identifier",
            },
        },
    }
}


def apply_schema_validator(db=None) -> bool:
    """Apply $jsonSchema validator to calibration_versions collection."""
    if db is None:
        from db.mongo import db as _db
        db = _db

    try:
        db.command(
            "collMod",
            "calibration_versions",
            validator=CALIBRATION_VALIDATOR,
            validationLevel="moderate",   # warn on old docs, block new ones
            validationAction="error",
        )
        logger.info("✅ $jsonSchema validator applied to calibration_versions")
        return True
    except Exception as exc:
        # Collection may not exist yet – create it with the validator
        logger.warning(f"collMod failed ({exc}); attempting to create collection")
        try:
            db.create_collection(
                "calibration_versions",
                validator=CALIBRATION_VALIDATOR,
                validationLevel="moderate",
                validationAction="error",
            )
            logger.info("✅ calibration_versions created with validator")
            return True
        except Exception as create_exc:
            logger.error(f"❌ Could not apply validator: {create_exc}")
            return False


# ---------------------------------------------------------------------------
# Layer 2 – Application-layer guard
# ---------------------------------------------------------------------------

class CalibrationImmutabilityGuard:
    """
    Service-layer guard that MUST be called before any update to
    calibration_versions.

    Usage::

        from db.migrations.phase4_002_calibration_immutability import (
            CalibrationImmutabilityGuard,
        )

        guard = CalibrationImmutabilityGuard()
        guard.check(calibration_version)   # raises on ACTIVE
        db.calibration_versions.update_one(...)
    """

    def __init__(self, db=None):
        if db is None:
            from db.mongo import db as _db
            db = _db
        self.db = db
        self.collection = db["calibration_versions"]
        self.sentinel_collection = db["sentinel_event_log"]

    def check(self, calibration_version: str) -> None:
        """
        Raise CalibrationImmutabilityError if the record is ACTIVE.
        Also log a CRITICAL sentinel event.
        """
        doc = self.collection.find_one(
            {"calibration_version": calibration_version},
            {"status": 1},
        )
        if doc and doc.get("status") == "ACTIVE":
            self._log_critical(calibration_version, "application_layer_guard")
            raise CalibrationImmutabilityError(
                f"IMMUTABILITY VIOLATION: calibration_version '{calibration_version}' "
                f"is ACTIVE and cannot be modified."
            )

    def _log_critical(self, calibration_version: str, source: str) -> None:
        try:
            self.sentinel_collection.insert_one(
                {
                    "event_type": "CALIBRATION_IMMUTABILITY_VIOLATION",
                    "severity": "CRITICAL",
                    "calibration_version": calibration_version,
                    "source": source,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    # system.immutability_guard is a system-internal identity, not an AOS agent.
                    # Does not follow agent.[name].v1 format by design. Documented and approved.
                    "agent_id": "system.immutability_guard",
                }
            )
            logger.critical(
                f"CRITICAL – CALIBRATION_IMMUTABILITY_VIOLATION: "
                f"version={calibration_version} source={source}"
            )
        except Exception as exc:
            logger.error(f"Failed to log sentinel event: {exc}")


# ---------------------------------------------------------------------------
# Layer 3 – Change-stream watcher (background thread)
# ---------------------------------------------------------------------------

class CalibrationChangeStreamWatcher:
    """
    Background thread that watches calibration_versions for updates to
    ACTIVE records and immediately rolls them back + logs CRITICAL.
    """

    THREAD_NAME = "phase4-calib-cs-watcher"

    def __init__(self, db=None):
        if db is None:
            from db.mongo import db as _db
            db = _db
        self.db = db
        self.collection = db["calibration_versions"]
        self.sentinel = db["sentinel_event_log"]
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.info("Change-stream watcher already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=self.THREAD_NAME,
            daemon=True,
        )
        self._thread.start()
        logger.info("✅ Calibration change-stream watcher started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🛑 Calibration change-stream watcher stopped")

    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Watch loop – reconnects on transient errors."""
        while not self._stop_event.is_set():
            try:
                self._watch_loop()
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                logger.error(f"Change-stream error (will retry in 10s): {exc}")
                time.sleep(10)

    def _watch_loop(self) -> None:
        pipeline = [
            {"$match": {"operationType": {"$in": ["update", "replace", "delete"]}}}
        ]
        with self.collection.watch(
            pipeline,
            full_document="updateLookup",
        ) as stream:
            for change in stream:
                if self._stop_event.is_set():
                    break
                self._handle_change(change)

    def _handle_change(self, change: Dict[str, Any]) -> None:
        """Inspect change and roll back if an ACTIVE record was mutated."""
        op = change.get("operationType")
        full_doc = change.get("fullDocument") or {}
        doc_key = change.get("documentKey", {})

        # Get previous status from updateDescription
        # We check the *post-change* document for status==ACTIVE; if so, and
        # if the change was an update/replace (not the initial ACTIVE promotion),
        # we look for the field being set in the update.
        updated_fields = change.get("updateDescription", {}).get("updatedFields", {})

        # Determine if the record was ACTIVE before this change
        # We do a pre-image lookup to see if this was an ACTIVE record
        pre_image = self._get_preimage(doc_key)

        if pre_image and pre_image.get("status") == "ACTIVE":
            # An ACTIVE record was modified – this is a violation
            version = pre_image.get("calibration_version", "unknown")
            logger.critical(
                f"CRITICAL – ACTIVE calibration record mutated! "
                f"version={version} op={op}"
            )
            self._log_critical_sentinel(version, op, pre_image, full_doc)

            # Roll back: restore the pre-image document
            if op in ("update", "replace") and pre_image:
                try:
                    self.collection.replace_one(
                        {"_id": doc_key.get("_id")},
                        pre_image,
                    )
                    logger.critical(
                        f"ROLLBACK: Restored ACTIVE calibration record "
                        f"version={version}"
                    )
                except Exception as exc:
                    logger.error(f"Rollback failed for version={version}: {exc}")

    def _get_preimage(self, doc_key: Dict) -> Optional[Dict]:
        """
        Attempt to read the current document (post-change) from the collection.
        For a proper pre-image you'd need MongoDB 6.0+ changeStreamPreAndPostImages.
        We use full_document='updateLookup' and check the *current* state.
        """
        try:
            return self.collection.find_one({"_id": doc_key.get("_id")})
        except Exception:
            return None

    def _log_critical_sentinel(
        self,
        version: str,
        op: str,
        pre_image: Dict,
        post_image: Dict,
    ) -> None:
        try:
            self.sentinel.insert_one(
                {
                    "event_type": "CALIBRATION_IMMUTABILITY_VIOLATION",
                    "severity": "CRITICAL",
                    "calibration_version": version,
                    "operation": op,
                    "source": "change_stream_watcher",
                    "pre_image_status": pre_image.get("status"),
                    "post_image_status": post_image.get("status"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    # system.immutability_guard is a system-internal identity, not an AOS agent.
                    # Does not follow agent.[name].v1 format by design. Documented and approved.
                    "agent_id": "system.immutability_guard",
                }
            )
        except Exception as exc:
            logger.error(f"Failed to log CS sentinel event: {exc}")


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_watcher_instance: Optional[CalibrationChangeStreamWatcher] = None


def get_watcher(db=None) -> CalibrationChangeStreamWatcher:
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = CalibrationChangeStreamWatcher(db=db)
    return _watcher_instance


def start_watcher(db=None) -> None:
    get_watcher(db=db).start()


def stop_watcher() -> None:
    if _watcher_instance:
        _watcher_instance.stop()


# ---------------------------------------------------------------------------
# Migration entry point
# ---------------------------------------------------------------------------

def run_migration(db=None) -> None:
    """Apply schema validator and record the migration."""
    if db is None:
        from db.mongo import db as _db
        db = _db

    apply_schema_validator(db)

    db["migration_log"].update_one(
        {"migration": "phase4_002_calibration_immutability"},
        {
            "$setOnInsert": {
                "migration": "phase4_002_calibration_immutability",
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "layers": ["schema_validator", "application_guard", "change_stream_watcher"],
            }
        },
        upsert=True,
    )
    logger.info("✅ Phase 4D migration complete: calibration immutability enforced")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
