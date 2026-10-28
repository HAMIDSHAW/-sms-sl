"""
Deployment hardening that does not change any business logic:

  * refuse to start a real deployment with guessable secrets or open CORS
  * make client IPs correct behind a reverse proxy (rate limits and audit use them)
  * security headers, request ids and a security event log

"Real deployment" means FLASK_ENV=production is set explicitly, or DATABASE_URL points
at something other than SQLite. A developer running `py -m flask run` locally with the
default SQLite file is not a deployment, so local use keeps working with no setup
(it gets a warning about the default secret instead).
"""
import logging
import os
import uuid

from flask import g, request

DEFAULT_SECRET = "change-me-in-production"
DEV_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

security_log = logging.getLogger("security")


def is_deployment():
    explicit = os.environ.get("FLASK_ENV", "").lower() == "production"
    url = os.environ.get("DATABASE_URL", "")
    return explicit or (bool(url) and not url.startswith("sqlite"))


def cors_origins():
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return DEV_CORS_ORIGINS.split(",")
    return [o.strip() for o in raw.split(",") if o.strip()]


def validate_config(app):
    """Fail fast on an unsafe production configuration; warn about the same things in local dev."""
    problems = []
    secret = app.config.get("SECRET_KEY") or ""
    jwt_secret = app.config.get("JWT_SECRET_KEY") or ""
    for name, value in (("SECRET_KEY", secret), ("JWT_SECRET_KEY", jwt_secret)):
        if value == DEFAULT_SECRET or len(value) < 32:
            problems.append(f"{name} is the built-in default or shorter than 32 characters")
    if "*" in cors_origins():
        problems.append("CORS_ORIGINS must list your frontend origin explicitly, not *")
    if is_deployment() and not os.environ.get("CORS_ORIGINS", "").strip():
        problems.append("CORS_ORIGINS is not set (set it to your frontend URL, e.g. https://school.example.com)")
    # A missing or misspelled DATABASE_URL would quietly fall back to a SQLite file on the host's disk,
    # which hosts like Render erase on every redeploy and restart: every student record would vanish.
    if (is_deployment() and str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("sqlite")
            and os.environ.get("ALLOW_SQLITE_IN_PRODUCTION") != "1"):
        problems.append("DATABASE_URL is not set to a real database, so the app would use a throwaway SQLite file "
                        "that is erased on every redeploy (set DATABASE_URL to your Supabase connection string)")

    if not problems:
        return
    if is_deployment():
        raise RuntimeError(
            "Refusing to start with an unsafe production configuration: " + "; ".join(problems)
            + ". Set strong random values in the host's environment variables."
        )
    security_log.warning("Local development config is not safe to deploy: %s", "; ".join(problems))


def init_security(app):
    """Proxy awareness, request ids and security headers."""
    proxies = int(os.environ.get("TRUST_PROXY_COUNT", "0") or 0)
    if proxies > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)

    @app.before_request
    def _request_id():
        g.request_id = request.headers.get("X-Request-ID", "")[:64] or uuid.uuid4().hex[:16]

    @app.after_request
    def _security_headers(response):
        h = response.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "same-origin"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        h["X-Request-ID"] = getattr(g, "request_id", "")
        if request.path.startswith("/api"):
            # Responses hold private school data: never let a browser or proxy cache them.
            h["Cache-Control"] = "no-store"
            h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.is_secure:
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def log_security_event(event, **fields):
    """One structured line per security relevant event. Never pass passwords, tokens or reset codes."""
    safe = " ".join(f"{k}={v}" for k, v in fields.items())
    security_log.warning("security_event=%s request_id=%s ip=%s %s", event, getattr(g, "request_id", "-"), request.remote_addr, safe)


def dev_tokens_allowed():
    """
    forgot-password and send-verification have no email provider behind them yet. For local testing
    they may include the token in the response, but ONLY for a direct request from this same machine
    in a non-production setup. Behind any proxy, in production, or from any other address the token is
    never returned (otherwise anyone could take over any account by asking for a reset).
    """
    if is_deployment() or os.environ.get("EXPOSE_DEV_TOKENS", "1") == "0":
        return False
    forwarded = request.headers.get("X-Forwarded-For") or request.headers.get("Forwarded")
    return request.remote_addr in ("127.0.0.1", "::1") and not forwarded
