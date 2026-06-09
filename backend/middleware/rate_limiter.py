"""
Rate Limiting Middleware — Phase 2A.3

Per-tenant and per-user rate limiting at the API gateway level (not service layer).
All thresholds live in agent_config — zero hardcoded values here.

Strategy:
  - Per-user:   sliding window based on authenticated user_id from JWT
  - Per-tenant: sliding window based on API key or IP for unauthenticated requests
  - Storage:    Redis (distributed, survives restarts); falls back to in-memory
                (single-process only — warns on startup)

On breach:
  - Returns HTTP 429 with Retry-After header
  - Writes RATE_LIMIT_BREACH event to sentinel_event_log
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Default thresholds (overridden by agent_config) ──────────────────────────
_DEFAULT_CONFIG = {
    "rate_limit_per_user_rpm": 120,      # requests per minute per authenticated user
    "rate_limit_per_ip_rpm": 60,         # requests per minute per IP (unauthenticated)
    "rate_limit_burst_multiplier": 1.5,  # short burst allowance
    "rate_limit_window_seconds": 60,
}


def _get_config() -> dict:
    try:
        from config.agent_config import AGENT_CONFIG
        return {**_DEFAULT_CONFIG, **AGENT_CONFIG.get("rate_limiting", {})}
    except Exception:
        return _DEFAULT_CONFIG


def _log_rate_breach(identifier: str, identifier_type: str, path: str, trace_id: str) -> None:
    try:
        from db.mongo import db
        db["sentinel_event_log"].insert_one({
            "event_type": "RATE_LIMIT_BREACH",
            "identifier": identifier,
            "identifier_type": identifier_type,
            "path": path,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.error("sentinel_event_log write failed: %s", exc)


def _extract_user_id_from_token(authorization: Optional[str]) -> Optional[str]:
    """Extract user_id from Bearer token (JWT or legacy user:<id>)."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    # JWT format
    if token.count(".") == 2:
        try:
            import base64, json as _json
            payload_b64 = token.split(".")[1]
            # Add padding
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("sub")
        except Exception:
            pass
    # Legacy format user:<id>
    if token.startswith("user:"):
        return token.split(":", 1)[1]
    return None


def _resolve_tenant(request: Request, user_id: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
    tenant_id = request.headers.get("X-Tenant-ID")
    try:
        from db.mongo import db
        if tenant_id:
            tenant = db["tenants"].find_one({"tenant_id": tenant_id})
            return tenant_id, tenant

        if user_id:
            tenant = db["tenants"].find_one({"tenant_id": user_id})
            if tenant:
                return user_id, tenant
    except Exception:
        pass
    return None, None


def _resolve_tenant_limit(tenant_doc: Optional[dict], fallback_limit: int) -> int:
    if not tenant_doc:
        return fallback_limit
    custom = tenant_doc.get("custom_thresholds", {}) or {}
    value = custom.get("rate_limit_per_minute")
    try:
        return int(value) if value is not None else fallback_limit
    except Exception:
        return fallback_limit


class _InMemoryStore:
    """Single-process sliding-window store. Thread-safe for asyncio (GIL)."""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check_and_record(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """
        Returns (allowed, current_count).
        Prunes old timestamps and adds current if within limit.
        """
        now = time.time()
        cutoff = now - window_seconds
        timestamps = self._windows[key]
        # Prune outside window
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        count = len(timestamps)
        if count >= limit:
            return False, count
        timestamps.append(now)
        return True, count + 1


class _RedisStore:
    def __init__(self, redis_client):
        self._r = redis_client

    def check_and_record(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        pipe = self._r.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.zadd(key, {str(uuid.uuid4()): now})
        pipe.expire(key, window_seconds + 1)
        results = pipe.execute()
        count_before = results[1]
        if count_before >= limit:
            # Roll back the add — we already wrote it, remove the newest
            self._r.zpopmax(key)
            return False, count_before
        return True, count_before + 1


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API-gateway-level rate limiter. Registered before route handlers."""

    def __init__(self, app):
        super().__init__(app)
        self._store = self._init_store()

    def _init_store(self):
        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            try:
                import redis  # type: ignore
                client = redis.from_url(redis_url, decode_responses=True)
                client.ping()
                logger.info("[RateLimit] Using Redis store: %s", redis_url)
                return _RedisStore(client)
            except Exception as exc:
                logger.warning("[RateLimit] Redis unavailable (%s); using in-memory store", exc)
        else:
            logger.warning(
                "[RateLimit] REDIS_URL not set — using in-memory rate limit store. "
                "This will NOT work correctly across multiple workers."
            )
        return _InMemoryStore()

    async def dispatch(self, request: Request, call_next):
        config = _get_config()
        window = int(config["rate_limit_window_seconds"])

        auth_header = request.headers.get("Authorization")
        user_id = _extract_user_id_from_token(auth_header)
        tenant_id, tenant_doc = _resolve_tenant(request, user_id)

        if user_id:
            limit = int(config["rate_limit_per_user_rpm"])
            limit = _resolve_tenant_limit(tenant_doc, limit)
            tenant_scope = tenant_id or user_id
            rate_key = f"rl:user:{tenant_scope}:{user_id}"
            identifier = user_id
            identifier_type = "user"
        else:
            limit = int(config["rate_limit_per_ip_rpm"])
            limit = _resolve_tenant_limit(tenant_doc, limit)
            ip = request.client.host if request.client else "unknown"
            if tenant_id:
                rate_key = f"rl:tenant:{tenant_id}:ip:{ip}"
                identifier = tenant_id
                identifier_type = "tenant"
            else:
                rate_key = f"rl:ip:{ip}"
                identifier = ip
                identifier_type = "ip"

        allowed, count = self._store.check_and_record(rate_key, limit, window)

        if not allowed:
            trace_id = str(uuid.uuid4())
            _log_rate_breach(identifier, identifier_type, str(request.url.path), trace_id)
            logger.warning(
                "[RateLimit] BLOCKED identifier=%s type=%s count=%d limit=%d trace_id=%s",
                identifier, identifier_type, count, limit, trace_id,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down.",
                    "code": "RATE_LIMITED",
                    "retry_after": window,
                },
                headers={"Retry-After": str(window)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response
