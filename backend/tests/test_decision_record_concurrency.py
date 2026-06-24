"""
Concurrency test — Phase 2A.4

Verifies that 10 simultaneous publish attempts with the same inputs_hash
result in exactly 1 document in the collection.

Run:  python -m pytest backend/tests/test_decision_record_concurrency.py -v
"""
from __future__ import annotations

import concurrent.futures
import threading
import uuid
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# ── Minimal stub for GameDecisions ───────────────────────────────────────────

class _FakeGameDecisions:
    def __init__(self, inputs_hash: str, decision_version: str):
        self.inputs_hash = inputs_hash
        self.decision_version = decision_version

    def model_dump(self, mode="json"):
        return {"inputs_hash": self.inputs_hash, "decision_version": self.decision_version}


# ── In-process MongoDB stub using a dict protected by a threading.Lock ───────

class _InMemoryCollection:
    """Thread-safe minimal MongoDB collection stub for concurrency testing."""

    def __init__(self):
        self._docs: dict = {}
        self._lock = threading.Lock()

    def create_index(self, *args, **kwargs):
        pass

    def find_one_and_update(self, filter_, update, *, upsert=False, return_document=None, projection=None):
        from pymongo import ReturnDocument  # type: ignore

        key = list(filter_.values())[0]  # identity_key value
        set_on_insert = update.get("$setOnInsert", {})

        with self._lock:
            if key in self._docs:
                # Document already exists — $setOnInsert is a no-op
                doc = self._docs[key]
            else:
                # First writer wins
                doc = set_on_insert.copy()
                self._docs[key] = doc

        if projection:
            return {k: doc[k] for k in projection if k in doc}
        return doc

    def count_all(self) -> int:
        return len(self._docs)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_store(collection: _InMemoryCollection):
    """Build a DecisionRecordStore pointing at the in-memory collection."""
    # Patch the import inside decision_record_store so it doesn't need real MongoDB
    import sys, importlib, types

    # Provide a minimal core.market_decision stub
    if "core.market_decision" not in sys.modules:
        mod = types.ModuleType("core.market_decision")
        mod.GameDecisions = _FakeGameDecisions  # type: ignore
        sys.modules["core"] = types.ModuleType("core")
        sys.modules["core.market_decision"] = mod

    from db.decision_record_store import DecisionRecordStore

    store = DecisionRecordStore.__new__(DecisionRecordStore)
    store.collection = collection
    return store


# ── The actual concurrency test ───────────────────────────────────────────────

def test_concurrent_publish_exactly_one_record():
    """
    10 threads simultaneously calling persist_game_decisions() with the SAME
    inputs_hash must produce exactly 1 document in the collection.
    """
    collection = _InMemoryCollection()
    store = _build_store(collection)

    decisions = _FakeGameDecisions(
        inputs_hash="abc123fixedhash",
        decision_version="v1.0.0",
    )

    results: List[str] = []
    errors: List[Exception] = []

    def publish():
        try:
            record_id = store.persist_game_decisions(
                league="NBA",
                game_id="game-x",
                odds_event_id="odds-x",
                decisions=decisions,
            )
            results.append(record_id)
        except Exception as exc:
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(publish) for _ in range(10)]
        concurrent.futures.wait(futures)

    assert not errors, f"Unexpected errors: {errors}"
    assert len(results) == 10, f"Expected 10 calls to complete, got {len(results)}"

    # All calls must return the SAME record_id (the one that was actually stored)
    assert len(set(results)) == 1, (
        f"Expected all 10 callers to get the same record_id, got: {set(results)}"
    )

    # Exactly 1 document must exist in the collection
    assert collection.count_all() == 1, (
        f"Expected exactly 1 document, found {collection.count_all()}"
    )


def test_different_inputs_hash_creates_separate_records():
    """Distinct (game_id, inputs_hash, decision_version) tuples → separate records."""
    collection = _InMemoryCollection()
    store = _build_store(collection)

    for i in range(5):
        decisions = _FakeGameDecisions(
            inputs_hash=f"hash-{i}",
            decision_version="v1.0.0",
        )
        store.persist_game_decisions(
            league="NFL",
            game_id=f"game-{i}",
            odds_event_id=f"odds-{i}",
            decisions=decisions,
        )

    assert collection.count_all() == 5, (
        f"Expected 5 distinct records, found {collection.count_all()}"
    )
