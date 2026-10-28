from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import User, Role
import re
import secrets

from app.utils.tenancy import current_school_id, permission_required, scoped_query, has_permission
from app.utils.audit import record_audit
from app.utils.passwords import validate_password

bp = Blueprint("users", __name__, url_prefix="/api/users")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _grants_full_access(role_names):
    """True when any of these roles carries the "*" wildcard (school owner / administrator)."""
    roles = Role.query.filter(Role.school_id == current_school_id(), Role.name.in_(role_names or [])).all()
    return any("*" in r.permission_codes() or getattr(r, "_all_permissions", False) for r in roles)


def _is_full_access_user(user):
    return "*" in user.all_permissions()


@bp.get("")
@permission_required("users.view")
def list_users():
    users = scoped_query(User).order_by(User.last_name).limit(200).all()
    return jsonify([u.to_dict() for u in users])


@bp.post("")
@permission_required("users.create")
def create_user():
    """
    Create a login for a staff member, student, or parent. Typically called
    right after creating the Staff/Student/Guardian record, passing back
    that record's id so the caller can link user_id -> the profile.
    """
    data = request.get_json(silent=True) or {}
    required = ["email", "password", "first_name", "last_name"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    school_id = current_school_id()
    email = str(data["email"]).strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 255:
        return jsonify({"error": "Enter a valid email address"}), 400
    problem = validate_password(data["password"], email)
    if problem:
        return jsonify({"error": problem}), 400
    # Only someone who already has full access may create another full access account.
    if _grants_full_access(data.get("roles")) and not has_permission("*"):
        return jsonify({"error": "Only an administrator can create another administrator"}), 403

    # Login finds an account by email alone, so an email may exist only once across the whole platform.
    if User.query.filter(db.func.lower(User.email) == email).first():
        return jsonify({"error": "A user with this email already exists"}), 400

    user = User(
        school_id=school_id, email=email,
        first_name=data["first_name"], last_name=data["last_name"],
        phone=data.get("phone"), must_change_password=True,
    )
    user.set_password(data["password"])

    role_names = data.get("roles", [])
    if role_names:
        roles = Role.query.filter(Role.school_id == school_id, Role.name.in_(role_names)).all()
        user.roles = roles

    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.post("/<user_id>/roles")
@permission_required("users.assign_role")
def assign_roles(user_id):
    user = scoped_query(User).filter_by(id=user_id).first_or_404()
    data = request.get_json(silent=True) or {}
    before_roles = [r.name for r in user.roles]
    role_names = data.get("roles", [])
    if (_grants_full_access(role_names) or _is_full_access_user(user)) and not has_permission("*"):
        return jsonify({"error": "Only an administrator can change administrator roles"}), 403
    roles = Role.query.filter(Role.school_id == current_school_id(), Role.name.in_(role_names)).all()
    user.roles = roles
    db.session.commit()
    record_audit("user.assign_role", "users", "user", user_id, before={"roles": before_roles}, after={"roles": role_names})
    db.session.commit()
    return jsonify(user.to_dict())


@bp.patch("/<user_id>")
@permission_required("users.update")
def update_user(user_id):
    user = scoped_query(User).filter_by(id=user_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if _is_full_access_user(user) and not has_permission("*"):
        return jsonify({"error": "Only an administrator can change an administrator account"}), 403
    for field in ["first_name", "last_name", "phone", "is_active", "photo_url"]:
        if field in data:
            setattr(user, field, data[field])
    db.session.commit()
    return jsonify(user.to_dict())


@bp.delete("/<user_id>")
@permission_required("users.delete")
def deactivate_user(user_id):
    user = scoped_query(User).filter_by(id=user_id).first_or_404()
    if _is_full_access_user(user) and not has_permission("*"):
        return jsonify({"error": "Only an administrator can deactivate an administrator account"}), 403
    user.is_active = False
    db.session.commit()
    return jsonify({"message": "User deactivated"})


@bp.post("/<user_id>/reset-password")
@permission_required("users.update")
def admin_reset_password(user_id):
    """
    The way a forgotten password is recovered while there is no email delivery: an authorised person
    sets a one time temporary password, hands it to the user in person (or by phone), and the user must
    choose their own at next sign in. The temporary password is shown ONCE in this response and is
    never stored or logged in readable form.
    """
    from app.routes.auth import _revoke_all_sessions
    from app.utils.security import log_security_event
    user = scoped_query(User).filter_by(id=user_id).first_or_404()
    if _is_full_access_user(user) and not has_permission("*"):
        return jsonify({"error": "Only an administrator can reset an administrator password"}), 403
    temporary = secrets.token_urlsafe(9)  # about 12 characters, cryptographically random
    user.set_password(temporary)
    user.must_change_password = True
    _revoke_all_sessions(user)
    user.invalidate_sessions()
    db.session.commit()
    log_security_event("admin_password_reset", target_user_id=user.id)
    return jsonify({"temporary_password": temporary, "email": user.email, "must_change_password": True})
