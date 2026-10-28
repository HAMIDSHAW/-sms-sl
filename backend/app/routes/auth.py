import secrets
import uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt,
)

from app.extensions import db, limiter
from app.models import User, PasswordResetToken, RevokedToken, UserSession, EmailVerificationToken
from app.utils.passwords import validate_password
from app.utils.security import dev_tokens_allowed, log_security_event

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _build_claims(user: User):
    """
    Bake school_id + a flattened permission list into the JWT so every
    downstream request can authorize without extra DB round-trips.
    Wildcard roles (school_owner, school_administrator) get "*".
    """
    perms = user.all_permissions()
    return {
        "school_id": user.school_id,
        "permissions": ["*"] if "*" in perms else sorted(perms),
        "roles": [r.name for r in user.roles],
        "tv": user.token_version(),
    }


def _email_from_body():
    """Rate limit key for login: the account being attacked, so one account cannot be hammered from many IPs."""
    data = request.get_json(silent=True) or {}
    return "login:" + (str(data.get("email") or "").strip().lower() or "none")


_dummy_hash_cache = []


def _dummy_hash():
    """A real bcrypt hash of a throwaway string, built once. Checked when the email is unknown so a
    missing account and a wrong password take the same time (otherwise timing reveals which emails exist)."""
    if not _dummy_hash_cache:
        from app.extensions import bcrypt
        _dummy_hash_cache.append(bcrypt.generate_password_hash(uuid.uuid4().hex).decode("utf-8"))
    return _dummy_hash_cache[0]


def _issue_session(user):
    """Create a login session and its token pair. Both tokens carry the session id (sid) so that
    logging out revokes exactly this session's refresh token."""
    from flask_jwt_extended import decode_token
    sid = str(uuid.uuid4())
    claims = {**_build_claims(user), "sid": sid}
    access_token = create_access_token(identity=user.id, additional_claims=claims)
    refresh_token = create_refresh_token(identity=user.id, additional_claims=claims)
    db.session.add(UserSession(
        id=sid, user_id=user.id, refresh_jti=decode_token(refresh_token)["jti"],
        user_agent=(request.headers.get("User-Agent") or "")[:255], ip_address=request.remote_addr,
    ))
    return access_token, refresh_token


@bp.post("/login")
@limiter.limit("10 per minute")
@limiter.limit("8 per minute", key_func=_email_from_body)
def login():
    """
    Login does NOT reveal whether a given email/username exists (spec
    section 5), invalid credentials always return the same generic error.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password or not isinstance(password, str) or len(password) > 256:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter(db.func.lower(User.email) == email).first()

    if not user:
        from app.extensions import bcrypt
        bcrypt.check_password_hash(_dummy_hash(), password)  # equalise timing
        log_security_event("login_failed", reason="unknown_account")
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.check_password(password) or not user.is_active:
        log_security_event("login_failed", reason="bad_credentials_or_inactive", user_id=user.id)
        return jsonify({"error": "Invalid email or password"}), 401

    # A suspended school (platform.schools.manage / Platform Admin "suspend"
    # action) should actually lock its users out, found during testing that
    # suspending a school set the flag but login never checked it, so every
    # account at a "suspended" school could still log in with full access.
    if user.school_id:
        from app.models import School
        school = School.query.get(user.school_id)
        if school and not school.is_active:
            return jsonify({"error": "This school's account is currently suspended. Contact the platform administrator."}), 403

    user.last_login_at = datetime.now(timezone.utc)
    access_token, refresh_token = _issue_session(user)
    db.session.commit()

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
        "must_change_password": user.must_change_password,
    })


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({"error": "Account not found or inactive"}), 401
    if user.school_id:
        from app.models import School
        school = School.query.get(user.school_id)
        if school and not school.is_active:
            return jsonify({"error": "This school's account is currently suspended."}), 403
    claims = _build_claims(user)
    sid = get_jwt().get("sid")
    if sid:
        claims["sid"] = sid
    return jsonify({"access_token": create_access_token(identity=user.id, additional_claims=claims)})


@bp.get("/me")
@jwt_required()
def me():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_with_profile_extras(user))


def _with_profile_extras(user):
    """user.to_dict() plus things the UI needs to decide what to show: staff link, address, class master duty."""
    from app.models import Staff, Student, Guardian, SchoolClass
    data = user.to_dict()
    staff = Staff.query.filter_by(user_id=user.id).first()
    data["staff_id"] = staff.id if staff else None
    data["address"] = None
    if staff:
        data["address"] = staff.address
        data["staff_title"] = staff.title
        data["staff_position"] = staff.position
        data["employee_number"] = staff.employee_number
        masters = SchoolClass.query.filter_by(class_master_staff_id=staff.id).all()
        data["class_master_of"] = [{"id": c.id, "name": c.name} for c in masters]
    else:
        for Model in (Student, Guardian):
            linked = Model.query.filter_by(user_id=user.id).first()
            if linked and hasattr(linked, "address"):
                data["address"] = linked.address
                break
        data["class_master_of"] = []
    data["is_class_master"] = bool(data["class_master_of"])
    return data


@bp.patch("/me")
@jwt_required()
def update_me():
    """
    Self-service profile update, deliberately limited to phone and photo.
    Names are NOT self-editable: a student's official/academic name must
    stay exactly what the school's records say, never a nickname or a
    self-chosen variant, so report cards, results, and official
    correspondence always match the login. Changing a name is an admin
    action only, via PATCH /api/users/<id> (login account) and PATCH
    /api/students/<id> or /api/staff/<id> (the academic/official record).
    """
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    for field in ["phone", "photo_url"]:
        if field in data:
            setattr(user, field, data[field])

    # Home address: kept on the person's own directory record (staff, student or guardian)
    # so the school can see where its staff live.
    if "address" in data:
        from app.models import Staff, Student, Guardian
        address = (data["address"] or "").strip() or None
        if address and len(address) > 500:
            return jsonify({"error": "Address is too long (500 characters at most)"}), 400
        for Model in (Staff, Student, Guardian):
            linked = Model.query.filter_by(user_id=user.id).first()
            if linked and hasattr(linked, "address"):
                linked.address = address
                break

    # User.photo_url (the login account) and Staff/Student/Guardian.photo_url
    # (the people-directory record rendered on the Students/Staff/Guardians
    # list pages) are separate columns. Without this, uploading your own
    # photo only ever showed up on your own Profile page and the sidebar -
    # never on the list row everyone else sees you by.
    if "photo_url" in data:
        from app.models import Staff, Student, Guardian
        for Model in (Staff, Student, Guardian):
            linked = Model.query.filter_by(user_id=user.id).first()
            if linked:
                linked.photo_url = data["photo_url"]

    db.session.commit()
    return jsonify(_with_profile_extras(user))


@bp.post("/change-password")
@jwt_required()
@limiter.limit("10 per minute")
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""

    user = User.query.get(get_jwt_identity())
    if not user or not isinstance(current, str) or not user.check_password(current):
        log_security_event("change_password_failed", user_id=get_jwt_identity())
        return jsonify({"error": "Current password is incorrect"}), 400
    problem = validate_password(new, user.email)
    if problem:
        return jsonify({"error": problem}), 400
    if new == current:
        return jsonify({"error": "Choose a password different from your current one"}), 400

    user.set_password(new)
    user.must_change_password = False
    _revoke_all_sessions(user)
    user.invalidate_sessions()
    # This device stays signed in: it gets a fresh session, every other device is signed out.
    access_token, refresh_token = _issue_session(user)
    db.session.commit()
    return jsonify({"message": "Password updated", "access_token": access_token, "refresh_token": refresh_token})


def _revoke_all_sessions(user):
    """Block every refresh token this user has outstanding."""
    now = datetime.now(timezone.utc)
    for session in UserSession.query.filter_by(user_id=user.id, revoked_at=None).all():
        session.revoked_at = now
        if not RevokedToken.query.get(session.refresh_jti):
            db.session.add(RevokedToken(jti=session.refresh_jti))


@bp.post("/forgot-password")
@limiter.limit("5 per minute")
def forgot_password():
    """
    Spec section 5. Deliberately does not reveal whether the email exists
    (same generic response either way), matches the "invalid credentials
    should not reveal whether a particular email exists" rule from login.

    No email/SMS provider is wired up yet (see README "honest gaps"), the
    raw token is returned in the response ONLY so this is testable end to
    end right now. Before going anywhere near real users, wire this to
    actually send the token via email/SMS instead of returning it.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    school_id = data.get("school_id")  # required to disambiguate which school's account, if multi-school

    generic_response = {"message": "If an account with that email exists, a reset link has been sent."}

    if not email:
        return jsonify(generic_response)

    query = User.query.filter(db.func.lower(User.email) == email)
    if school_id:
        query = query.filter(User.school_id == school_id)
    user = query.first()

    if not user or not user.is_active:
        return jsonify(generic_response)

    raw_token = secrets.token_urlsafe(32)
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=PasswordResetToken.hash_token(raw_token),
        expires_at=PasswordResetToken.default_expiry(),
    )
    db.session.add(reset)
    db.session.commit()

    log_security_event("password_reset_requested", user_id=user.id)
    response = dict(generic_response)
    # No email/SMS provider is wired up yet, so nobody is actually sent this token. It is returned
    # only for local testing on this machine (see dev_tokens_allowed), never in production.
    if dev_tokens_allowed():
        response["_dev_only_token"] = raw_token
        response["_dev_only_user_id"] = user.id
    return jsonify(response)


@bp.post("/reset-password")
@limiter.limit("10 per minute")
def reset_password():
    """Complete a forgot-password flow using the token from /forgot-password."""
    data = request.get_json(silent=True) or {}
    token = data.get("token") or ""
    new_password = data.get("new_password") or ""
    user_id = data.get("user_id")  # returned alongside the token in a real email deep-link

    if not token or not new_password or not user_id:
        return jsonify({"error": "token, user_id, and new_password are required"}), 400
    if not isinstance(token, str) or not isinstance(user_id, str):
        return jsonify({"error": "Invalid or expired reset token"}), 400

    user = User.query.get(user_id)
    candidates = PasswordResetToken.query.filter_by(user_id=user_id, used_at=None).all()
    matching = next((t for t in candidates if t.is_valid(token)), None)
    if not matching or not user or not user.is_active:
        log_security_event("password_reset_failed", user_id=user_id)
        return jsonify({"error": "Invalid or expired reset token"}), 400
    problem = validate_password(new_password, user.email)
    if problem:
        return jsonify({"error": problem}), 400

    user.set_password(new_password)
    user.must_change_password = False
    matching.used_at = datetime.now(timezone.utc)
    # Every other outstanding reset token for this user is now worthless too.
    for other in candidates:
        other.used_at = other.used_at or datetime.now(timezone.utc)
    _revoke_all_sessions(user)
    user.invalidate_sessions()
    db.session.commit()
    log_security_event("password_reset_completed", user_id=user.id)

    return jsonify({"message": "Password has been reset. You can now log in."})


# --- Logout / session management (spec section 5 + 71) --------------------

@bp.post("/logout")
@jwt_required(refresh=False)
def logout():
    """Revoke the current access token immediately, and its paired session's refresh token."""
    claims = get_jwt()
    db.session.add(RevokedToken(jti=claims["jti"]))

    user_id = get_jwt_identity()
    # Revoke the session THIS token belongs to (its sid), so the paired refresh token can't mint
    # new access tokens. Tokens from before sessions carried an sid fall back to the newest session.
    sid = claims.get("sid")
    if sid:
        session = UserSession.query.filter_by(id=sid, user_id=user_id, revoked_at=None).first()
    else:
        session = UserSession.query.filter_by(user_id=user_id, revoked_at=None).order_by(
            UserSession.created_at.desc()
        ).first()
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        if not RevokedToken.query.get(session.refresh_jti):
            db.session.add(RevokedToken(jti=session.refresh_jti))

    db.session.commit()
    return jsonify({"message": "Logged out"})


@bp.get("/sessions")
@jwt_required()
def list_sessions():
    """View active sessions (spec section 71: 'View sessions')."""
    sessions = UserSession.query.filter_by(
        user_id=get_jwt_identity(), revoked_at=None
    ).order_by(UserSession.created_at.desc()).all()
    return jsonify([s.to_dict() for s in sessions])


@bp.post("/sessions/<session_id>/revoke")
@jwt_required()
def revoke_session(session_id):
    """Force logout a specific session, e.g. 'log out my other devices' (spec section 71)."""
    session = UserSession.query.filter_by(id=session_id, user_id=get_jwt_identity()).first_or_404()
    session.revoked_at = datetime.now(timezone.utc)
    db.session.add(RevokedToken(jti=session.refresh_jti))
    db.session.commit()
    return jsonify({"message": "Session revoked"})


# --- Email verification (spec section 5) -----------------------------------

@bp.post("/send-verification")
@jwt_required()
def send_verification():
    """
    Issues a verification token for the logged-in user's own email.
    Same "no real delivery yet" caveat as forgot-password, see README.
    """
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({"error": "Not found"}), 404
    if user.is_email_verified:
        return jsonify({"message": "Email already verified"})

    raw_token = secrets.token_urlsafe(32)
    verification = EmailVerificationToken(
        user_id=user.id, token_hash=EmailVerificationToken.hash_token(raw_token),
        expires_at=EmailVerificationToken.default_expiry(),
    )
    db.session.add(verification)
    db.session.commit()
    response = {"message": "Verification token created"}
    if dev_tokens_allowed():  # no email provider yet; local testing only, never in production
        response["_dev_only_token"] = raw_token
    return jsonify(response)


@bp.post("/verify-email")
@limiter.limit("10 per minute")
def verify_email():
    data = request.get_json(silent=True) or {}
    token = data.get("token") or ""
    user_id = data.get("user_id")
    if not token or not user_id:
        return jsonify({"error": "token and user_id are required"}), 400

    candidates = EmailVerificationToken.query.filter_by(user_id=user_id, used_at=None).all()
    matching = next((t for t in candidates if t.is_valid(token)), None)
    if not matching:
        return jsonify({"error": "Invalid or expired verification token"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Invalid or expired verification token"}), 400
    user.is_email_verified = True
    matching.used_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Email verified"})
