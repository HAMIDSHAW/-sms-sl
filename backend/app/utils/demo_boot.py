"""
Optional: load the demo school the first time a brand-new deployment starts.

Turned on by setting SEED_DEMO_ON_BOOT=1 (plus a private DEMO_PASSWORD) on the host. It only ever acts on a
database that has no school at all, so it can never touch a live school's data, and a restart after the
first successful seed does nothing. It runs in a background thread so the host's health check passes while
it works; the demo school appears a few minutes after the first start.
"""
import logging
import os
import threading
import time

log = logging.getLogger(__name__)


def seed_demo_in_background(app):
    from app.models import School
    with app.app_context():
        if School.query.count() > 0:
            log.info("SEED_DEMO_ON_BOOT is set, but this database already has a school. Nothing to do.")
            return

    # Imported here, not at the top: seed.py lives beside run.py, outside the app package.
    try:
        import seed
    except ImportError:
        log.error("SEED_DEMO_ON_BOOT is set but seed.py could not be imported. Demo data was not loaded.")
        return
    problem = seed.check_demo_password_for_deployment() if _is_real_deployment() else None
    if problem:
        log.error("Demo data NOT loaded: %s", problem)
        return

    def work():
        started = time.time()
        log.warning("Demo data: seeding started (this can take a few minutes on a free host).")
        try:
            seed.run_seed(app=app, from_boot=True)
            log.warning("Demo data: seeding finished in %.0f seconds.", time.time() - started)
        except BaseException:  # SystemExit from a guard must not kill the host process silently either
            log.exception("Demo data: seeding FAILED. Nothing was saved. Fix the cause and restart to retry.")

    threading.Thread(target=work, name="demo-seed", daemon=True).start()


def _is_real_deployment():
    from app.utils.security import is_deployment
    return is_deployment()
