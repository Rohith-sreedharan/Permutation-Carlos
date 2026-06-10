"""
Phase 9 AC-5 API Response Language Guard

Scans JSON API responses for prohibited wagering language and logs
CRITICAL sentinel events when detected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from config.agent_config import AGENT_CONFIG
from db.mongo import db


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iter_response_chunks(response: Response) -> Iterable[bytes]:
    async def _empty():
        if False:
            yield b""

    iterator = getattr(response, "body_iterator", None)
    if iterator is None:
        body = getattr(response, "body", b"") or b""
        return [body]
    return iterator


class APIResponseLanguageGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.phrases = [
            p.lower()
            for p in AGENT_CONFIG.get("phase7", {}).get("prohibited_phrases", [])
            if isinstance(p, str)
        ]

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        content_type = (response.headers.get("content-type") or "").lower()
        if "application/json" not in content_type:
            return response

        body = b""
        chunks = _iter_response_chunks(response)
        if hasattr(chunks, "__aiter__"):
            async for chunk in chunks:
                body += chunk
        else:
            for chunk in chunks:
                body += chunk

        text = body.decode("utf-8", errors="ignore")
        lower = text.lower()

        violations = []
        for phrase in self.phrases:
            if phrase in lower:
                # Negation exception for sportsbook references.
                if phrase == "sportsbook" and (
                    "not a sportsbook" in lower
                    or "not the sportsbook" in lower
                    or "no sportsbook" in lower
                ):
                    continue
                violations.append(phrase)

        if violations:
            try:
                db["sentinel_event_log"].insert_one(
                    {
                        "event_type": "PROHIBITED_LANGUAGE_API_RESPONSE",
                        "severity": "CRITICAL",
                        "path": request.url.path,
                        "method": request.method,
                        "violations": sorted(list(set(violations))),
                        "timestamp": _utc_now_iso(),
                    }
                )
            except Exception:
                pass

        headers = dict(response.headers)
        if "content-length" in headers:
            headers.pop("content-length")

        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
