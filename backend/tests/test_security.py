import io
import re

import pytest

from conftest import PASSWORD, ROLES, Session

FAKE = "00000000-0000-0000-0000-000000000000"
REMOTE = {"REMOTE_ADDR": "203.0.113.9"}  # an outside attacker, not the developer's own machine


# --- Authentication -------------------------------------------------------------------------------

def test_every_seeded_role_can_sign_in(as_role):
    for role in ROLES:
        as_role(role)


def test_reset_token_is_never_returned_to_remote_callers(client):
    r = client.post("/api/auth/forgot-password", json={"email": "teacher@kgss.example.sl"}, environ_base=REMOTE)
    assert r.status_code == 200
    body = r.get_json()
    assert "_dev_only_token" not in body and "_dev_only_user_id" not in body


def test_reset_token_hidden_behind_a_proxy_even_from_loopback(client):
    r = client.post("/api/auth/forgot-password", json={"email": "teacher@kgss.example.sl"},
                    headers={"X-Forwarded-For": "198.51.100.4"})
    assert "_dev_only_token" not in r.get_json()


def test_student_cannot_take_over_a_teacher_account(as_role, client):
    student = as_role("student")
    _, contacts = student.call("get", "/api/messages/contacts?q=")
    teacher = next(c for c in contacts if c["email"] == "teacher@kgss.example.sl")
    r = client.post("/api/auth/forgot-password", json={"email": teacher["email"]}, environ_base=REMOTE)
    token = r.get_json().get("_dev_only_token")
    assert token is None
    r = client.post("/api/auth/reset-password",
                    json={"token": "guess", "user_id": teacher["id"], "new_password": "Hacked-Pw-12345!"}, environ_base=REMOTE)
    assert r.status_code == 400


def test_login_error_is_identical_for_unknown_and_wrong_password(client):
    a = client.post("/api/auth/login", json={"email": "nobody@x.example", "password": "abcdefgh"})
    b = client.post("/api/auth/login", json={"email": "librarian@kgss.example.sl", "password": "abcdefgh"})
    assert (a.status_code, a.get_json()) == (b.status_code, b.get_json())


def test_login_throttles_one_account_attacked_from_many_addresses(client, limiter_on):
    codes = [client.post("/api/auth/login", json={"email": "transport@kgss.example.sl", "password": f"wrong-{i}"},
                         environ_base={"REMOTE_ADDR": f"198.51.100.{i}"}).status_code for i in range(1, 13)]
    assert 429 in codes


def test_login_throttles_one_address_trying_many_accounts(client, limiter_on):
    codes = [client.post("/api/auth/login", json={"email": f"nobody{i}@x.example", "password": "abcdefgh"},
                         environ_base={"REMOTE_ADDR": "203.0.113.77"}).status_code for i in range(14)]
    assert 429 in codes


def test_reset_endpoints_are_rate_limited(client, limiter_on):
    codes = [client.post("/api/auth/reset-password", json={"token": "x", "user_id": "y", "new_password": "Abcdefg-123!"},
                         environ_base={"REMOTE_ADDR": "203.0.113.91"}).status_code for _ in range(14)]
    assert 429 in codes


@pytest.mark.parametrize("weak", ["short", "password123", "Password123!", "aaaaaaaaaa", "x" * 200])
def test_weak_passwords_are_rejected(throwaway, weak):
    s, _, _ = throwaway()
    code, _ = s.call("post", "/api/auth/change-password", json={"current_password": "Tmp-Start-Pw-91!", "new_password": weak})
    assert code == 400


def test_logout_kills_that_devices_refresh_token_but_not_the_other_device(throwaway, client):
    d1, _, email = throwaway()
    d2 = Session(client, email, password="Tmp-Start-Pw-91!")
    client.post("/api/auth/logout", headers=d1.headers)
    assert client.get("/api/auth/me", headers=d1.headers).status_code == 401
    assert client.post("/api/auth/refresh", headers={"Authorization": "Bearer " + d1.refresh}).status_code == 401
    assert client.post("/api/auth/refresh", headers={"Authorization": "Bearer " + d2.refresh}).status_code == 200


def test_changing_password_signs_out_other_devices_and_keeps_this_one(throwaway, client):
    here, _, email = throwaway()
    other = Session(client, email, password="Tmp-Start-Pw-91!")
    r = client.post("/api/auth/change-password", headers=here.headers,
                    json={"current_password": "Tmp-Start-Pw-91!", "new_password": "Fresh-Pw-4471!"})
    assert r.status_code == 200
    fresh = {"Authorization": "Bearer " + r.get_json()["access_token"]}
    assert client.get("/api/auth/me", headers=other.headers).status_code == 401
    assert client.post("/api/auth/refresh", headers={"Authorization": "Bearer " + other.refresh}).status_code == 401
    assert client.get("/api/auth/me", headers=here.headers).status_code == 401
    assert client.get("/api/auth/me", headers=fresh).status_code == 200


def test_forged_tokens_are_rejected(as_role, client):
    import base64
    head, payload, sig = as_role("student").access.split(".")
    none_head = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    for token in (f"{none_head}.{payload}.", f"{head}.{payload}.{sig[:-3]}abc"):
        assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code in (401, 422)


def test_refresh_and_access_tokens_are_not_interchangeable(as_role, client):
    s = as_role("student")
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + s.refresh}).status_code in (401, 422)
    assert client.post("/api/auth/refresh", headers=s.headers).status_code in (401, 422)


def test_deactivated_account_loses_access_immediately(as_role, throwaway, client):
    admin = as_role("admin")
    victim, uid, _ = throwaway()
    assert admin.call("patch", f"/api/users/{uid}", json={"is_active": False})[0] == 200
    assert client.get("/api/auth/me", headers=victim.headers).status_code == 401
    assert client.post("/api/auth/refresh", headers={"Authorization": "Bearer " + victim.refresh}).status_code == 401


def test_admin_password_reset_flow(as_role, throwaway, client):
    admin = as_role("admin")
    target, uid, email = throwaway()
    code, data = admin.call("post", f"/api/users/{uid}/reset-password")
    assert code == 200 and len(data["temporary_password"]) >= 10
    assert client.get("/api/auth/me", headers=target.headers).status_code == 401
    r = client.post("/api/auth/login", json={"email": email, "password": data["temporary_password"]})
    assert r.status_code == 200 and r.get_json()["must_change_password"] is True
    forced = {"Authorization": "Bearer " + r.get_json()["access_token"]}
    assert client.get("/api/students", headers=forced).status_code == 403  # must change password first


def test_only_admins_can_reset_passwords_or_create_admins(as_role):
    teacher = as_role("teacher")
    assert teacher.call("post", f"/api/users/{FAKE}/reset-password")[0] == 403
    assert teacher.call("post", "/api/users", json={"email": "z@y.example", "password": "Abcdefg-123!", "first_name": "a",
                                                    "last_name": "b", "roles": ["school_administrator"]})[0] == 403


# --- Authorization --------------------------------------------------------------------------------

def test_parent_cannot_mark_fees_as_paid(as_role):
    accountant, parent = as_role("accountant"), as_role("parent")
    _, kids = parent.call("get", "/api/students/my-children")
    code, inv = accountant.call("post", "/api/invoices", json={"student_id": kids[0]["id"], "description": "TEST fee", "amount": 5000})
    assert code == 201
    code, body = parent.call("post", "/api/payments", json={"invoice_id": inv["id"], "amount": 5000, "payment_method": "cash"})
    assert code == 403
    _, ledger = parent.call("get", f"/api/finance/ledger/{kids[0]['id']}")
    assert any(i["id"] == inv["id"] and i["balance"] == 5000 for i in ledger["invoices"])


def test_student_and_parent_only_see_their_own_marks(as_role):
    for role, limit in (("student", 1), ("parent", 2)):
        _, rows = as_role(role).call("get", "/api/marks")
        rows = rows if isinstance(rows, list) else rows.get("items", [])
        assert len({r["student_id"] for r in rows}) <= limit


def test_students_cannot_read_school_expenses_or_audit_logs(as_role):
    accountant, student = as_role("accountant"), as_role("student")
    accountant.call("post", "/api/finance/expenses", json={"description": "Fuel", "amount": 100, "category": "utilities", "expense_date": "2026-10-01"})
    assert student.call("get", "/api/finance/expenses")[0] == 403
    assert student.call("get", "/api/audit-logs")[0] == 403
    assert student.call("get", "/api/users")[0] == 403


def test_students_cannot_open_each_others_records(as_role):
    admin, student = as_role("admin"), as_role("student")
    _, listing = admin.call("get", "/api/students?per_page=200")
    other = next(s["id"] for s in listing["items"] if s["first_name"] != "Abdul")  # student@ is Abdul
    assert student.call("get", f"/api/students/{other}")[0] in (403, 404)
    assert student.call("get", f"/api/finance/ledger/{other}")[0] in (403, 404)


def test_teacher_only_deletes_their_own_assignments(as_role):
    teacher, other, admin = as_role("teacher"), as_role("teacher2"), as_role("admin")
    _, mine = teacher.call("get", "/api/assignments?mine=1")
    aid = mine[0]["id"]
    assert other.call("delete", f"/api/assignments/{aid}")[0] == 403
    assert admin.call("delete", f"/api/assignments/{aid}")[0] == 403


def test_write_access_by_role_matches_the_job(as_role):
    """Every non admin role is refused the clearly administrative writes."""
    for role in ("teacher", "accountant", "librarian", "student", "parent", "transport", "inventory"):
        s = as_role(role)
        for method, path in (("post", "/api/students"), ("post", "/api/staff"), ("post", "/api/academics/classes"),
                             ("post", "/api/users"), ("post", "/api/hr/payroll/runs"), ("patch", "/api/school")):
            assert s.call(method, path, json={})[0] == 403, f"{role} {method} {path}"


def test_second_school_cannot_see_or_change_the_first_schools_data(as_role, client):
    superadmin = Session(client, "superadmin@platform.example")
    code, _ = superadmin.call("post", "/api/platform/schools", json={
        "name": "Other School", "owner_email": "owner@other.example", "owner_password": "Tmp-Passw0rd!x1"})
    assert code == 201
    r = client.post("/api/auth/login", json={"email": "owner@other.example", "password": "Tmp-Passw0rd!x1"})
    token = r.get_json()["access_token"]
    r = client.post("/api/auth/change-password", headers={"Authorization": "Bearer " + token},
                    json={"current_password": "Tmp-Passw0rd!x1", "new_password": "Brand-New-Pw-77!"})
    outsider = {"Authorization": "Bearer " + r.get_json()["access_token"]}

    admin = as_role("admin")
    _, students = admin.call("get", "/api/students?per_page=5")
    sid = students["items"][0]["id"]
    for method in ("get", "patch", "delete"):
        assert getattr(client, method)(f"/api/students/{sid}", headers=outsider).status_code in (403, 404)
    for path in ("/api/students", "/api/staff", "/api/invoices", "/api/payments", "/api/assignments", "/api/library/books"):
        body = client.get(path, headers=outsider).get_json()
        rows = body if isinstance(body, list) else body.get("items", [])
        assert rows == [], path


def test_email_is_unique_across_schools(as_role):
    admin = as_role("admin")
    code, _ = admin.call("post", "/api/users", json={"email": "TEACHER@kgss.example.sl", "password": "Abcdefg-123!",
                                                     "first_name": "a", "last_name": "b", "roles": ["teacher"]})
    assert code in (400, 409)


# --- Input handling, files, headers ---------------------------------------------------------------

def test_malformed_and_injection_style_queries_never_cause_server_errors(as_role, app):
    admin = as_role("admin")
    routes = [str(r) for r in app.url_map.iter_rules() if str(r).startswith("/api") and "GET" in r.methods
              and "<" not in str(r) and not str(r).startswith(("/api/auth", "/api/health"))]
    payloads = ["q=' OR 1=1--", "q=%27%3B%20DROP%20TABLE%20students%3B--", "page=abc", "per_page=-5", "date=notadate",
                "student_id=' OR '1'='1", "limit=1e999", "per_page=999999999"]
    for path in routes:
        for payload in payloads:
            assert admin.client.get(f"{path}?{payload}", headers=admin.headers).status_code < 500, f"{path}?{payload}"
    assert admin.call("get", "/api/students?per_page=1")[1]["total"] == 180


def test_list_endpoints_cap_page_size(as_role):
    _, body = as_role("admin").call("get", "/api/students?per_page=999999")
    assert len(body["items"]) <= 200


def _upload(session, name, content, kind="document"):
    return session.client.post(f"/api/uploads?kind={kind}", headers=session.headers,
                               data={"file": (io.BytesIO(content), name)}, content_type="multipart/form-data")


def test_upload_accepts_real_files_and_rejects_disguised_ones(as_role):
    teacher = as_role("teacher")
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    assert _upload(teacher, "a.png", png, "image").status_code == 201
    assert _upload(teacher, "evil.png", b"<html><script>alert(1)</script></html>", "image").status_code == 400
    assert _upload(teacher, "evil.pdf", b"<?php system($_GET['c']); ?>").status_code == 400
    for name, body in (("x.html", b"<h1>x</h1>"), ("x.svg", b"<svg onload=alert(1)/>"), ("x.exe", b"MZ" + b"0" * 50)):
        assert _upload(teacher, name, body).status_code == 400, name


def test_uploaded_files_are_served_safely_and_traversal_is_blocked(as_role, client):
    teacher = as_role("teacher")
    url = _upload(teacher, "a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50, "image").get_json()["url"]
    _, school_id, filename = url.rsplit("/", 2)
    r = client.get(f"/uploads/{school_id}/{filename}")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff" and "sandbox" in r.headers["Content-Security-Policy"]
    for probe in ("/uploads/%2e%2e/x", "/uploads/../x.png", "/uploads/abc/..%2fsecret", "/uploads/abc/notahash.txt"):
        assert client.get(probe).status_code == 404, probe


def test_oversized_request_body_is_refused(client):
    assert client.post("/api/auth/login", data=b"x" * (11 * 1024 * 1024), content_type="application/json").status_code == 413


def test_security_headers_and_cors(as_role, client):
    r = as_role("student").call("get", "/api/school")  # noqa: F841
    r = client.get("/api/school", headers=as_role("student").headers)
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert "max-age" in client.get("/api/school", headers=as_role("student").headers, base_url="https://localhost").headers["Strict-Transport-Security"]
    evil = client.options("/api/auth/login", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "Access-Control-Allow-Origin" not in evil.headers
    good = client.options("/api/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert good.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"


def test_attendance_list_is_bounded(as_role):
    code, rows = as_role("admin").call("get", "/api/attendance")
    assert code == 200 and len(rows) <= 500


# --- Activity log ---------------------------------------------------------------------------------

def test_important_actions_land_in_the_activity_log(as_role):
    accountant, admin = as_role("accountant"), as_role("admin")
    _, kids = as_role("parent").call("get", "/api/students/my-children")
    accountant.call("post", "/api/invoices", json={"student_id": kids[0]["id"], "description": "Log test", "amount": 10})
    _, logs = admin.call("get", "/api/audit-logs?per_page=20")
    assert any("invoice" in (l.get("summary") or "").lower() for l in logs["items"])
