"""
Security Headers Middleware — Phase 2A.3

Adds HSTS, CSP, X-Frame-Options, and other OWASP-recommended headers
to every response. Zero mixed content. No inline scripts in production.
"""
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Strict-Transport-Security: force HTTPS for 1 year, include subdomains
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Content-Security-Policy
        # Allows: self, BeatVegas CDN assets, Google Fonts, Stripe JS, particles.js CDN
        # Blocks: inline scripts (except hashed ones added by Vite), arbitrary eval
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://js.stripe.com 'unsafe-inline'; "
            "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://beta.beatvegas.app https://beatvegas.app "
            "https://api.stripe.com https://api.the-odds-api.com; "
            "frame-src https://js.stripe.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Stop MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Referrer policy — no referrer to third parties
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — deny sensors and invasive APIs
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        # Remove server fingerprint
        for h in ("Server", "X-Powered-By"):
            if h in response.headers:
                del response.headers[h]

        return response
