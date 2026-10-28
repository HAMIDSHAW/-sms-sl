"""
Super-admin / platform-level endpoints (spec section 4.1).

The super admin is not a school employee. These routes create the school
"shell" and its first school_owner login; from that point on, the school's
own admin manages everything about their school (name, logo, address, etc.)
through app/routes/schools.py, nothing about a specific school is
hard-coded here or anywhere else.
"""

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import School, User, Role
from app.utils.tenancy import super_admin_required
from app.utils.rbac_seed import ensure_system_roles

bp = Blueprint("platform", __name__, url_prefix="/api/platform")


@bp.get("/schools")
@super_admin_required
def list_schools():
    schools = School.query.order_by(School.name).all()
    return jsonify([s.to_dict() for s in schools])


@bp.post("/schools")
@super_admin_required
def create_school():
    """
    Create a new tenant school + its first school_owner user. Every field
    besides name/email is optional here, the school's own admin fills in
    the rest (logo, address, terminology, etc.) via the setup wizard.
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    owner_email = (data.get("owner_email") or "").strip().lower()
    owner_password = data.get("owner_password") or ""
    owner_first_name = data.get("owner_first_name") or "School"
    owner_last_name = data.get("owner_last_name") or "Owner"

    if not name or not owner_email or not owner_password:
        return jsonify({"error": "name, owner_email, and owner_password are required"}), 400
    from app.utils.passwords import validate_password
    problem = validate_password(owner_password, owner_email)
    if problem:
        return jsonify({"error": problem}), 400
    # Login looks an account up by email alone, so an email must belong to exactly one account platform wide.
    if User.query.filter(db.func.lower(User.email) == owner_email).first():
        return jsonify({"error": "That email already has an account"}), 409

    school = School(name=name, short_name=data.get("short_name"))
    db.session.add(school)
    db.session.flush()  # get school.id before creating roles/users

    roles_by_name = ensure_system_roles(school)

    owner = User(
        school_id=school.id,
        email=owner_email,
        first_name=owner_first_name,
        last_name=owner_last_name,
        must_change_password=True,
    )
    owner.set_password(owner_password)
    owner.roles.append(roles_by_name["school_owner"])
    db.session.add(owner)
    db.session.commit()

    return jsonify({"school": school.to_dict(), "owner": owner.to_dict()}), 201


@bp.patch("/schools/<school_id>/status")
@super_admin_required
def set_school_status(school_id):
    school = School.query.get_or_404(school_id)
    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        school.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify(school.to_dict())
