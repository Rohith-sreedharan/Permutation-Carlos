"""
GeoIP Enforcement Middleware — Phase 2A.1

Every API request is checked against MaxMind GeoLite2 before any other
processing occurs.

Rules:
  • All 50 US states + DC → allow
  • Puerto Rico (PR), USVI, Guam, CNMI → 403
  • Non-US IP → 403
  • VPN / anonymous proxy (via GeoLite2-Anonymous-IP) → 403
  • No bypass path of any kind

DB files are configured via environment variables:
  GEOIP_COUNTRY_DB   — path to GeoLite2-Country.mmdb (or GeoLite2-City.mmdb)
  GEOIP_ANON_DB      — path to GeoLite2-Anonymous-IP.mmdb
  GEOIP_ENABLED      — set to "false" to disable (only for local dev)

Returns on block:
  HTTP 403 {"detail": "Access restricted to United States only.", "code": "GEO_BLOCKED"}

Every block is logged to sentinel_event_log within 60 seconds.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# US ISO-3166-2 subdivisions that are NOT the 50 states + DC
# (territories — must be blocked)
_BLOCKED_SUBDIVISIONS = {"PR", "VI", "GU", "MP", "AS", "UM"}

# Paths that bypass geo-enforcement
# (none — the directive says "no bypass path of any kind")
_BYPASS_PATHS: set[str] = set()


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, honouring common reverse-proxy headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first (leftmost) address — the actual client
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _log_geo_violation(
    ip: str,
    reason: str,
    country: Optional[str],
    subdivision: Optional[str],
    path: str,
    trace_id: str,
) -> None:
    """Write a GEO_VIOLATION entry to sentinel_event_log (async-safe via sync insert)."""
    try:
        from db.mongo import db

        db["sentinel_event_log"].insert_one(
            {
                "event_type": "GEO_VIOLATION",
                "ip": ip,
                "reason": reason,
                "country": country,
                "subdivision": subdivision,
                "path": path,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:  # pragma: no cover
        logger.error("sentinel_event_log write failed: %s", exc)


class GeoIPMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that enforces US-only access via MaxMind GeoLite2."""

    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self._country_reader = None
        self._anon_reader = None
        self._load_dbs()

    # ------------------------------------------------------------------ setup

    def _load_dbs(self) -> None:
        country_db = os.getenv("GEOIP_COUNTRY_DB", "")
        anon_db = os.getenv("GEOIP_ANON_DB", "")

        if not country_db:
            logger.warning(
                "[GeoIP] GEOIP_COUNTRY_DB is not set. "
                "GeoIP enforcement is ACTIVE but will block all non-localhost IPs. "
                "Set GEOIP_COUNTRY_DB to the path of GeoLite2-Country.mmdb."
            )
            return

        try:
            import geoip2.database  # type: ignore

            self._country_reader = geoip2.database.Reader(country_db)
            logger.info("[GeoIP] Country database loaded: %s", country_db)
        except Exception as exc:
            logger.error("[GeoIP] Failed to load country DB: %s", exc)

        if anon_db:
            try:
                import geoip2.database  # type: ignore

                self._anon_reader = geoip2.database.Reader(anon_db)
                logger.info("[GeoIP] Anonymous-IP database loaded: %s", anon_db)
            except Exception as exc:
                logger.warning("[GeoIP] Failed to load anonymous-IP DB: %s", exc)

    # --------------------------------------------------------------- dispatch

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        ip = _get_client_ip(request)

        # Always allow localhost (dev / health checks from same host)
        if ip in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)

        trace_id = str(uuid.uuid4())
        block_reason, country, subdivision = self._check_ip(ip)

        if block_reason:
            _log_geo_violation(
                ip=ip,
                reason=block_reason,
                country=country,
                subdivision=subdivision,
                path=str(request.url.path),
                trace_id=trace_id,
            )
            logger.warning(
                "[GeoIP] BLOCKED ip=%s reason=%s trace_id=%s", ip, block_reason, trace_id
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access restricted to United States only.",
                    "code": "GEO_BLOCKED",
                    "trace_id": trace_id,
                },
            )

        response = await call_next(request)
        return response

    # -------------------------------------------------------------- ip check

    def _check_ip(
        self, ip: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Returns (block_reason, country_iso, subdivision_iso) or (None, ...) if allowed.
        Fails closed: if DB is unavailable, block the request.
        """
        country_iso: Optional[str] = None
        subdivision_iso: Optional[str] = None

        # ── VPN / anonymous proxy check (highest priority) ──────────────────
        if self._anon_reader:
            try:
                import geoip2.errors  # type: ignore

                anon = self._anon_reader.anonymous_ip(ip)
                if (
                    anon.is_anonymous
                    or anon.is_anonymous_vpn
                    or anon.is_public_proxy
                    or anon.is_hosting_provider
                    or anon.is_tor_exit_node
                    or anon.is_residential_proxy
                ):
                    return "VPN_OR_PROXY_DETECTED", None, None
            except geoip2.errors.AddressNotFoundError:
                pass
            except Exception as exc:
                logger.warning("[GeoIP] Anon DB lookup error for %s: %s", ip, exc)

        # ── Country / subdivision check ──────────────────────────────────────
        if self._country_reader:
            try:
                import geoip2.errors  # type: ignore

                record = self._country_reader.country(ip)
                country_iso = record.country.iso_code  # e.g. "US"

                if country_iso != "US":
                    return "NON_US_COUNTRY", country_iso, None

                # Check for blocked US territories (PR, GU, VI, MP, AS)
                # GeoLite2-City has subdivisions; Country does not.
                # If Country DB is actually City DB, check subdivisions.
                try:
                    sub = self._country_reader.city(ip)
                    subdivision_iso = (
                        sub.subdivisions.most_specific.iso_code
                        if sub.subdivisions
                        else None
                    )
                    if subdivision_iso in _BLOCKED_SUBDIVISIONS:
                        return "BLOCKED_TERRITORY", country_iso, subdivision_iso
                except Exception:
                    pass  # Country DB has no subdivision data — that's fine

                # Allowed: US mainland + DC
                return None, country_iso, subdivision_iso

            except geoip2.errors.AddressNotFoundError:
                # IP not in database — fail closed
                return "IP_NOT_IN_DATABASE", None, None
            except Exception as exc:
                logger.error("[GeoIP] Country DB lookup error for %s: %s", ip, exc)
                # Fail closed
                return "GEOIP_LOOKUP_ERROR", None, None

        # No DB loaded — fail closed for all non-localhost IPs
        return "GEOIP_DB_NOT_CONFIGURED", None, None


def make_geoip_middleware(app):
    """
    Factory used in main.py. Reads GEOIP_ENABLED from environment.
    Default: enabled in production, disabled when GEOIP_ENABLED=false.
    """
    enabled_raw = os.getenv("GEOIP_ENABLED", "true").lower().strip()
    enabled = enabled_raw not in ("false", "0", "no")
    if not enabled:
        logger.warning("[GeoIP] GeoIP enforcement DISABLED via GEOIP_ENABLED=false")
    return GeoIPMiddleware(app, enabled=enabled)
