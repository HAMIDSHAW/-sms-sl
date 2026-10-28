"""Startup safety rules, each checked in a fresh process because they run at app creation."""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRONG = "x" * 48


def _start(env):
    clean = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT", "TEMP", "TMP")}
    clean.update(env)
    clean["SCHEDULER_ENABLED"] = "0"
    code = f"import warnings;warnings.filterwarnings('ignore');import sys;sys.path.insert(0,{BACKEND!r});from app import create_app;create_app();print('STARTED')"
    r = subprocess.run([sys.executable, "-c", code], env=clean, capture_output=True, text=True, cwd=BACKEND)
    return "STARTED" in r.stdout, r.stderr


def test_local_default_still_starts(tmp_path):
    assert _start({"DATABASE_URL": "sqlite:///" + str(tmp_path / "cfg.db").replace("\\", "/")})[0]


def test_production_refuses_default_secrets():
    started, err = _start({"FLASK_ENV": "production"})
    assert not started and "unsafe production configuration" in err


def test_production_refuses_wildcard_cors():
    assert not _start({"FLASK_ENV": "production", "SECRET_KEY": STRONG, "JWT_SECRET_KEY": STRONG + "j", "CORS_ORIGINS": "*"})[0]


def test_production_requires_explicit_cors_origin():
    assert not _start({"FLASK_ENV": "production", "SECRET_KEY": STRONG, "JWT_SECRET_KEY": STRONG + "j"})[0]


def test_production_refuses_to_run_on_throwaway_sqlite(tmp_path):
    base = {"FLASK_ENV": "production", "SECRET_KEY": STRONG, "JWT_SECRET_KEY": STRONG + "j", "CORS_ORIGINS": "https://x.example"}
    started, err = _start({**base, "DATABASE_URL": "sqlite:///" + str(tmp_path / "t.db").replace("\\", "/")})
    assert not started and "DATABASE_URL" in err
    started, _ = _start({**base, "DATABASE_URL": "sqlite:///" + str(tmp_path / "t.db").replace("\\", "/"), "ALLOW_SQLITE_IN_PRODUCTION": "1"})
    assert started


def test_production_with_proper_settings_starts(tmp_path):
    assert _start({"FLASK_ENV": "production", "SECRET_KEY": STRONG, "JWT_SECRET_KEY": STRONG + "j", "ALLOW_SQLITE_IN_PRODUCTION": "1",
                   "CORS_ORIGINS": "https://school.example.com",
                   "DATABASE_URL": "sqlite:///" + str(tmp_path / "cfg.db").replace("\\", "/")})[0]


def test_demo_seed_refuses_to_run_in_production():
    clean = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT")}
    clean.update({"FLASK_ENV": "production", "SECRET_KEY": STRONG, "JWT_SECRET_KEY": STRONG + "j", "CORS_ORIGINS": "https://x.example"})
    r = subprocess.run([sys.executable, "seed.py"], env=clean, capture_output=True, text=True, cwd=BACKEND)
    assert r.returncode != 0 and "Refusing to seed demo data" in (r.stderr + r.stdout)


def _run(code, env):
    clean = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT", "TEMP", "TMP")}
    clean.update(env)
    clean["SCHEDULER_ENABLED"] = "0"
    return subprocess.run([sys.executable, "-c", code], env=clean, capture_output=True, text=True, cwd=BACKEND)


def test_a_new_empty_database_gets_its_tables_when_the_app_starts(tmp_path):
    db_file = str(tmp_path / "fresh.db").replace("\\", "/")
    code = (f"import warnings;warnings.filterwarnings('ignore');import sys;sys.path.insert(0,{BACKEND!r});"
            "from app import create_app;from app.extensions import db;app=create_app();"
            "app.app_context().push();from sqlalchemy import inspect;"
            "print('TABLES', len(inspect(db.engine).get_table_names()))")
    r = _run(code, {"DATABASE_URL": "sqlite:///" + db_file})
    count = int(r.stdout.split("TABLES")[1].split()[0])
    assert count > 40, r.stderr


def _seed_in_production(extra, tmp_path):
    env = {"FLASK_ENV": "production", "SECRET_KEY": STRONG, "JWT_SECRET_KEY": STRONG + "j",
           "CORS_ORIGINS": "https://x.example", "ALLOW_SQLITE_IN_PRODUCTION": "1",
           "DATABASE_URL": "sqlite:///" + str(tmp_path / "seed.db").replace("\\", "/")}
    env.update(extra)
    return _run(f"import warnings;warnings.filterwarnings('ignore');import sys;sys.path.insert(0,{BACKEND!r});import seed;seed.run_seed()", env)


def test_demo_seed_in_production_needs_a_private_password(tmp_path):
    for extra in ({}, {"ALLOW_DEMO_SEED": "1"}, {"ALLOW_DEMO_SEED": "1", "DEMO_PASSWORD": "Password123!"},
                  {"ALLOW_DEMO_SEED": "1", "DEMO_PASSWORD": "password"}):
        r = _seed_in_production(extra, tmp_path)
        assert "Refusing to seed" in (r.stderr + r.stdout), extra
        assert "Seeded" not in r.stdout
