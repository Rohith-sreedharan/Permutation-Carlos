"""Decision record persistence for identity-law response rendering.

Persists a canonical GameDecisions bundle once under a deterministic identity key
and returns the persisted payload by record ID.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


from core.market_decision import GameDecisions


class DecisionRecordStore:
    """Append-only decision bundle store with deterministic idempotency key."""

    def __init__(self, collection=None):
        if collection is None:
            from db.mongo import db

            collection = db["decision_records"]
        self.collection = collection

        # Unique identity key guarantees idempotent persist for identical bundles.
        self.collection.create_index("identity_key", unique=True)
        self.collection.create_index("record_id", unique=True)
        self.collection.create_index([("game_id", 1), ("created_at", -1)])

    @staticmethod
    def compute_identity_key(
        league: str,
        game_id: str,
        inputs_hash: str,
        decision_version: str,
    ) -> str:
        base = f"{league}:{game_id}:{inputs_hash}:{decision_version}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def persist_game_decisions(
        self,
        league: str,
        game_id: str,
        odds_event_id: str,
        decisions: GameDecisions,
    ) -> str:
        """Persist once and return stable record_id for this bundle identity."""
        identity_key = self.compute_identity_key(
            league=league,
            game_id=game_id,
            inputs_hash=decisions.inputs_hash,
            decision_version=decisions.decision_version,
        )

        existing = self.collection.find_one({"identity_key": identity_key}, {"record_id": 1})
        if existing:
            return str(existing["record_id"])

        record_id = str(uuid.uuid4())
        payload = decisions.model_dump(mode="json")

        doc = {
            "record_id": record_id,
            "identity_key": identity_key,
            "league": league,
            "game_id": game_id,
            "odds_event_id": odds_event_id,
            "inputs_hash": decisions.inputs_hash,
            "decision_version": decisions.decision_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        try:
            self.collection.insert_one(doc)
            return record_id
        except Exception as exc:
            # Race-safe idempotency for duplicate-key insert races.
            if "duplicate key" in str(exc).lower() or "e11000" in str(exc).lower():
                existing = self.collection.find_one({"identity_key": identity_key}, {"record_id": 1})
                if existing:
                    return str(existing["record_id"])
            raise

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
