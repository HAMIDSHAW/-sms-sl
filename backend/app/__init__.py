import os

from flask import Flask, jsonify, request

from app.config import CONFIG_MAP
from app.extensions import db, bcrypt, jwt, cors, limiter


def create_app(config_name=None):
    app = Flask(__name__)
    config_name = config_name or os.environ.get("FLASK_ENV", "production")
    app.config.from_object(CONFIG_MAP.get(config_name, CONFIG_MAP["production"]))

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    from app.utils.security import validate_config, init_security, cors_origins
    validate_config(app)
    init_security(app)
    # Explicit origins only (never "*"). Local development defaults to the Vite dev server.
    cors.init_app(app, resources={r"/api/*": {"origins": cors_origins()}})
    limiter.init_app(app)

    # Import models so SQLAlchemy knows about every table before create_all
    # / migrations run.
    from app import models  # noqa: F401

    @jwt.token_in_blocklist_loader
    def check_if_revoked(jwt_header, jwt_payload):
        from app.models import RevokedToken, User
        if RevokedToken.query.filter_by(jti=jwt_payload["jti"]).first() is not None:
            return True
        # A deactivated account, or a token issued before the password was last changed, is dead
        # immediately rather than when it eventually expires.
        user = User.query.get(jwt_payload.get("sub"))
        if user is None or not user.is_active:
            return True
        if jwt_payload.get("tv", "0") != user.token_version():
            return True
        return False

    from app.routes import register_blueprints
    register_blueprints(app)

    from app.utils import activity_log
    activity_log.register(app)

    # Sync every school's role permissions against the current code's
    # DEFAULT_ROLES on every app startup, not just when seed.py runs.
    # Without this, a permission fix shipped in an update would silently
    # never reach an already-running installation until someone thought
    # to wipe the database, which isn't realistic to expect. Cheap (a
    # handful of upserts) and safe to run every time.
    with app.app_context():
        try:
            from app.models import School
            from app.utils.rbac_seed import ensure_system_roles, ensure_super_admin_role
            from app.utils.auto_migrate import run_auto_migration
            # A brand-new database (a fresh Supabase project, say) has no tables at all, so create every
            # table that is missing. This never alters or drops anything that already exists.
            db.create_all()
            # Add any columns a model has gained since this database was created, before anything else
            # touches it, since a stale schema would 500 on literally the next query.
            run_auto_migration(db)
            ensure_super_admin_role()
            for school in School.query.all():
                ensure_system_roles(school)
            if os.environ.get("SEED_DEMO_ON_BOOT") == "1":
                from app.utils.demo_boot import seed_demo_in_background
                seed_demo_in_background(app)
        except Exception as exc:
            # Tables may not exist yet on a brand-new database before the
            # first `db.create_all()` / seed run, that's fine, seed.py
            # will call these directly the first time. Anything else is
            # logged so a failed migration is never silent.
            import logging
            logging.getLogger(__name__).warning("Startup schema/role sync skipped: %s", exc)

    # Background job: ping a teacher and their students'/guardians' about
    # to a period starting in ~5 minutes. Skipped entirely under pytest
    # and disabled via SCHEDULER_ENABLED=0 for any process that shouldn't
    # run it (e.g. a second gunicorn worker, only one process needs to
    # own this, otherwise every worker fires the same reminder).
    if os.environ.get("SCHEDULER_ENABLED", "1") == "1" and not app.config.get("TESTING"):
        try:
            from app.utils.period_reminders import start_period_reminder_scheduler
            start_period_reminder_scheduler(app)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Could not start period-reminder scheduler")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/health/db")
    def health_db():
        """Like /api/health but also proves the database answers. Safe for an uptime monitor to call
        every few minutes: it reads nothing private and costs one trivial query."""
        import logging
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "ok"})
        except Exception:
            logging.getLogger(__name__).exception("Database health check failed")
            return jsonify({"status": "degraded", "database": "unreachable"}), 503

    # Serve files saved by app/routes/uploads.py. Public/unauthenticated by
    # design (the same way a photo hosted on any CDN would be), the URL
    # itself (a random uuid filename under the school's own folder) is the
    # only thing gating access, which is an acceptable tradeoff for
    # non-sensitive assets like profile photos, a school logo, and
    # assignment attachments. Don't reuse this for anything that needs real
    # access control (e.g. a signed payslip).
    @app.get("/uploads/<school_id>/<filename>")
    def uploaded_file(school_id, filename):
        import re
        from flask import send_from_directory
        # Only names this app itself generates are served: a school id (uuid-like) and a
        # 32 hex character filename. Anything else, including "..", is a plain 404.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", school_id) or not re.fullmatch(r"[0-9a-f]{32}\.[a-z0-9]{2,5}", filename):
            return jsonify({"error": "Not found"}), 404
        folder = os.path.join(app.instance_path, "uploads", school_id)
        response = send_from_directory(folder, filename)
        # Uploaded files are untrusted: never let a browser run or sandbox-escape them.
        response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; sandbox"
        if not filename.rsplit(".", 1)[-1] in ("png", "jpg", "jpeg", "gif", "webp"):
            response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "Request is too large"}), 413

    @app.errorhandler(429)
    def rate_limited(e):
        from app.utils.security import log_security_event
        log_security_event("rate_limited", path=request.path)
        return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429

    @app.errorhandler(ValueError)
    def bad_value(e):
        # A malformed number or date in a query string or body is the caller's mistake (400), not a server fault.
        return jsonify({"error": "Invalid value in request"}), 400

    @app.errorhandler(500)
    def server_error(e):
        # Never leak internals to the client (spec section 96), log
        # server-side, return a generic message to the caller.
        app.logger.exception(e)
        return jsonify({"error": "Internal server error"}), 500

    return app
