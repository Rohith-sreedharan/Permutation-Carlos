"""
conftest.py — pytest session fixtures

Sets BEATVEGAS_ENV=test before any test module is imported so that
DeterministicReplayCache activates its in-memory fallback when MongoDB is
unavailable. In production (BEATVEGAS_ENV unset or "production") the cache
always fails closed — never returns stale in-memory data.
"""
import os

# Must be set before any test module is imported (session-scoped)
os.environ.setdefault("BEATVEGAS_ENV", "test")
