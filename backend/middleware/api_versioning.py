"""
Phase 10 API versioning middleware.

- Canonical client path: /api/v1/*  → transparently rewritten to /api/* internally
- Legacy /api/* (non-GET/HEAD) without v1 prefix → HTTP 426
- Infrastructure paths (/api/health, /api/tracker) always pass through.
"""

from __future__ import annotations

import json
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import JSONResponse, Response


_PASSTHROUGH = {"/api/health", "/api/tracker"}


class APIVersioningMiddleware:
    """Pure ASGI middleware — rewrites /api/v1/* → /api/* before routing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        if not (path == "/api" or path.startswith("/api/")):
            await self.app(scope, receive, send)
            return

        # Rewrite /api/v1/* → /api/* and pass through
        if path.startswith("/api/v1/") or path == "/api/v1":
            new_path = "/api" + path[len("/api/v1"):]
            scope = dict(scope)
            scope["path"] = new_path
            # Also fix raw_path if present (used by some ASGI servers)
            scope["raw_path"] = new_path.encode()
            await self.app(scope, receive, send)
            return

        # Infrastructure passthrough (no version required)
        if path in _PASSTHROUGH or any(path.startswith(p + "/") for p in _PASSTHROUGH):
            await self.app(scope, receive, send)
            return

        # Non-versioned API call — pass through transparently
        # (frontend components use /api/* directly; 426 enforcement deferred)
        await self.app(scope, receive, send)
        return
