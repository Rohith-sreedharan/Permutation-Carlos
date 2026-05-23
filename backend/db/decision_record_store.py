"""Decision record persistence for identity-law response rendering.

Persists a canonical GameDecisions bundle once under a deterministic identity key
and returns the persisted payload by record ID.

Phase 2A.4: Advisory lock via MongoDB atomic findOneAndUpdate ($setOnInsert).
Concurrency guarantee: 10 simultaneous publish attempts → exactly 1 record written.
All duplicate publish attempts are logged to sentinel_event_log.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import ReturnDocument

from core.market_decision import GameDecisions

logger = logging.getLogger(__name__)


class DecisionRecordStore:
    """Append-only decision bundle store with deterministic idempotency key.

    Idempotency is enforced at TWO layers:
      1. MongoDB unique index on identity_key (DB-level constraint)
      2. Atomic findOneAndUpdate with $setOnInsert (advisory lock — prevents
         duplicate writes even under high concurrency without a two-phase check)
    """

    def __init__(self, collection=None):
        if collection is None:
            from db.mongo import db

            collection = db["decision_records"]
        self.collection = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Idempotently create required indexes. Called once at startup."""
        self.collection.create_index("identity_key", unique=True)
        self.collection.create_index("record_id", unique=True)
        self.collection.create_index([("game_id", 1), ("created_at", -1)])
        self.collection.create_index(
            [("event_id", 1), ("inputs_hash", 1), ("decision_version", 1)],
            unique=True,
            name="event_inputs_version_unique",
        )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def compute_identity_key(
        league: str,
        game_id: str,
        inputs_hash: str,
        decision_version: str,
    ) -> str:
        base = f"{league}:{game_id}:{inputs_hash}:{decision_version}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    @staticmethod
    def _log_duplicate_attempt(identity_key: str, existing_record_id: str) -> None:
        """Log a duplicate publish attempt to sentinel_event_log."""
        try:
            from db.mongo import db

            db["sentinel_event_log"].insert_one(
                {
                    "event_type": "DUPLICATE_DECISION_RECORD",
                    "identity_key": identity_key,
                    "existing_record_id": existing_record_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            logger.error("sentinel_event_log write failed: %s", exc)

    # ----------------------------------------------------------------- public

    def persist_game_decisions(
        self,
        league: str,
        game_id: str,
        odds_event_id: str,
        decisions: GameDecisions,
    ) -> str:
        """Persist once and return stable record_id for this bundle identity.

        Uses atomic findOneAndUpdate with $setOnInsert as an advisory lock.
        If the document already exists under identity_key, the $setOnInsert
        is a no-op and the existing record_id is returned. This means even
        10 simultaneous callers will produce exactly 1 record in MongoDB.
        """
        identity_key = self.compute_identity_key(
            league=league,
            game_id=game_id,
            inputs_hash=decisions.inputs_hash,
            decision_version=decisions.decision_version,
        )

        record_id = str(uuid.uuid4())
        payload = decisions.model_dump(mode="json")
        now_iso = datetime.now(timezone.utc).isoformat()

        doc_to_insert = {
            "record_id": record_id,
            "identity_key": identity_key,
            "league": league,
            "game_id": game_id,
            "event_id": game_id,
            "odds_event_id": odds_event_id,
            "inputs_hash": decisions.inputs_hash,
            "decision_version": decisions.decision_version,
            "created_at": now_iso,
            "payload": payload,
        }

        # Atomic advisory lock: $setOnInsert only fires if the document did NOT
        # already exist — MongoDB guarantees this is atomic.
        result = self.collection.find_one_and_update(
            {"identity_key": identity_key},
            {"$setOnInsert": doc_to_insert},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"record_id": 1},
        )

        returned_id = str(result["record_id"])

        if returned_id != record_id:
            # A document already existed — this was a duplicate publish attempt.
            logger.warning(
                "[DecisionRecord] Duplicate publish blocked: identity_key=%s existing=%s",
                identity_key,
                returned_id,
            )
            self._log_duplicate_attempt(identity_key, returned_id)

        return returned_id

    def get_record_payload(self, record_id: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({"record_id": record_id}, {"payload": 1})
        if not doc:
            return None
        return doc.get("payload")


_decision_record_store: Optional[DecisionRecordStore] = None


def get_decision_record_store() -> DecisionRecordStore:
    global _decision_record_store
    if _decision_record_store is None:
        _decision_record_store = DecisionRecordStore()
    return _decision_record_store
