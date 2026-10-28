"""
Test harness. Builds a throwaway SQLite database seeded with the same demo school the app ships with,
so tests run against real roles and real data and never touch dev.db.

Run from the backend folder:   py -m pytest -q
"""
import os
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")

_tmp = tempfile.mkdtemp(prefix="sms-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["SCHEDULER_ENABLED"] = "0"
os.environ.pop("FLASK_ENV", None)
os.environ.pop("CORS_ORIGINS", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

PASSWORD = "Password123!"
ROLES = ["admin", "principal", "teacher", "teacher2", "accountant", "examofficer",
         "hrofficer", "librarian", "inventory", "transport", "student", "parent"]


@pytest.fixture(scope="session")
def app():
    import seed
    seed.run_seed()
    from app import create_app
    from app.extensions import limiter
    application = create_app()
    application.config["TESTING"] = True
    limiter.enabled = False  # turned on explicitly by the tests that exercise throttling
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def limiter_on(app):
    from app.extensions import limiter
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


class Session:
    def __init__(self, client, email, password=PASSWORD, ip="127.0.0.1"):
        self.client = client
        self.ip = ip
        r = client.post("/api/auth/login", json={"email": email, "password": password}, environ_base={"REMOTE_ADDR": ip})
        assert r.status_code == 200, f"login failed for {email}: {r.status_code}"
        data = r.get_json()
        self.access, self.refresh = data["access_token"], data["refresh_token"]

    @property
    def headers(self):
        return {"Authorization": "Bearer " + self.access}

    def call(self, method, path, **kw):
        r = getattr(self.client, method)(path, headers=self.headers, **kw)
        try:
            return r.status_code, r.get_json()
        except Exception:
            return r.status_code, None


@pytest.fixture()
def as_role(client):
    """as_role('teacher') -> a signed in session for the seeded teacher account."""
    def make(role, **kw):
        return Session(client, f"{role}@kgss.example.sl", **kw)
    return make


@pytest.fixture()
def throwaway(client):
    """throwaway() -> (session, user_id) for a brand new teacher account, so tests that change passwords,
    deactivate accounts or sign out never disturb the seeded demo logins other tests rely on."""
    import uuid
    counter = {"n": 0}

    def make():
        admin = Session(client, "admin@kgss.example.sl")
        email = f"tmp-{uuid.uuid4().hex[:10]}@kgss.example.sl"
        code, body = admin.call("post", "/api/users", json={
            "email": email, "password": "Tmp-Start-Pw-91!", "first_name": "Temp", "last_name": "User", "roles": ["teacher"]})
        assert code == 201, body
        return Session(client, email, password="Tmp-Start-Pw-91!"), body["id"], email

    return make
