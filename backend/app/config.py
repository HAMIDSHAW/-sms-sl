import os
from datetime import timedelta


def normalize_database_url(url):
    """
    Accept the Postgres address however a dashboard prints it. SQLAlchemy rejects the old
    "postgres://" spelling outright, and "postgresql://" would pick a driver by accident, so both
    are rewritten to name the driver this project installs (psycopg2).
    """
    url = (url or "").strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def database_url_from_env():
    return normalize_database_url(os.environ.get("DATABASE_URL")) or (
        "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev.db")
    )


class Config:
    """
    Base configuration.

    Reads everything from environment variables so the same codebase runs
    unchanged on Render (backend) while pointing at Supabase Postgres.
    Nothing here is hard-coded, since infra tends to move (free-tier now,
    upgraded later).
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # --- Database -----------------------------------------------------
    # Supabase Postgres, via the +psycopg2 driver. Example (use the
    # "Connection pooling" URI from Supabase, not the direct one):
    #   postgresql+psycopg2://postgres.xxxxx:PASSWORD@aws-0-xx.pooler.supabase.com:6543/postgres
    # For local dev without that set, fall back to SQLite so the app is
    # still runnable end-to-end with zero setup.
    SQLALCHEMY_DATABASE_URI = database_url_from_env()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Reject any request body over 10 MB (uploads are capped at 8 MB by the upload route itself).
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Auth -----------------------------------------------------------
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    # Short lived access token (the frontend refreshes it silently), so a changed role, a
    # deactivated account or a stolen token stops working within the hour, not after 8 hours.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "60")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = ["access", "refresh"]

    # --- File storage -----------------------------------------------------
    # See app/utils/storage.py for the actual env vars (UPLOAD_S3_ENDPOINT,
    # UPLOAD_S3_BUCKET, UPLOAD_S3_ACCESS_KEY, UPLOAD_S3_SECRET_KEY,
    # UPLOAD_PUBLIC_BASE_URL), read directly from os.environ there rather
    # than mirrored here, since storage.py needs to tell "none of these are
    # set, use local disk" apart from "these are set but something's
    # missing/wrong", which a single Config class attribute can't express.

    # --- Misc -----------------------------------------------------------
    DEFAULT_TIMEZONE = "Africa/Freetown"
    DEFAULT_CURRENCY = "SLE"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
