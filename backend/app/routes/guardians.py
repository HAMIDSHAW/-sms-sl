from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Guardian, Student, StudentGuardian
from app.utils.tenancy import (
    current_school_id, permission_required, scoped_query, jwt_required_scoped, has_permission, class_master_class_ids,
)

bp = Blueprint("guardians", __name__, url_prefix="/api/guardians")


def _class_master_guardian_ids():
    """Guardian ids linked to students in the classes the caller is class master of."""
    from app.models import Enrollment
    class_ids = class_master_class_ids()
    if not class_ids:
        return []
    student_ids = [e.student_id for e in Enrollment.query.filter(
        Enrollment.class_id.in_(class_ids), Enrollment.status == "active").all()]
    return [sg.guardian_id for sg in StudentGuardian.query.filter(StudentGuardian.student_id.in_(student_ids or [""])).all()]


@bp.get("")
@jwt_required_scoped
def list_guardians():
    """Everyone with parents.view sees all guardians. A class master, who has no such permission,
    sees only the guardians of the children in their own class(es)."""
    query = scoped_query(Guardian)
    if not has_permission("parents.view"):
        allowed = _class_master_guardian_ids()
        if not allowed:
            return jsonify({"error": "Missing permission: parents.view"}), 403
        query = query.filter(Guardian.id.in_(allowed))
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Guardian.first_name.ilike(like), Guardian.last_name.ilike(like), Guardian.phone.ilike(like)))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(Guardian.last_name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [g.to_dict() for g in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.get("/<guardian_id>")
@jwt_required_scoped
def get_guardian(guardian_id):
    guardian = scoped_query(Guardian).filter_by(id=guardian_id).first_or_404()
    if not has_permission("parents.view") and guardian.id not in _class_master_guardian_ids():
        return jsonify({"error": "Missing permission: parents.view"}), 403
    data = guardian.to_dict()
    data["children"] = [sg.student.to_dict() for sg in guardian.students]
    return jsonify(data)


@bp.post("")
@permission_required("parents.create")
def create_guardian():
    data = request.get_json(silent=True) or {}
    if not data.get("first_name") or not data.get("last_name"):
        return jsonify({"error": "first_name and last_name are required"}), 400

    guardian = Guardian(
        school_id=current_school_id(),
        first_name=data["first_name"], last_name=data["last_name"],
        phone=data.get("phone"), email=data.get("email"),
        address=data.get("address"), occupation=data.get("occupation"),
    )
    db.session.add(guardian)
    db.session.commit()
    return jsonify(guardian.to_dict()), 201


@bp.patch("/<guardian_id>")
@permission_required("parents.update")
def update_guardian(guardian_id):
    guardian = scoped_query(Guardian).filter_by(id=guardian_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ("first_name", "last_name"):
        if field in data and not str(data[field] or "").strip():
            return jsonify({"error": f"{field.replace('_', ' ')} cannot be empty"}), 400
    before = {"first_name": guardian.first_name, "last_name": guardian.last_name}
    for field in ["first_name", "last_name", "phone", "email", "address", "occupation", "is_active", "photo_url", "user_id"]:
        if field in data:
            value = data[field]
            setattr(guardian, field, value.strip() if isinstance(value, str) and field in ("first_name", "last_name") else value)
    after = {"first_name": guardian.first_name, "last_name": guardian.last_name}
    if after != before:
        if guardian.user_id:
            from app.models import User
            user = User.query.get(guardian.user_id)
            if user:
                user.first_name, user.last_name = guardian.first_name, guardian.last_name
        from app.utils.audit import record_audit
        record_audit("guardian.name.change", "guardians", "guardian", guardian.id, before=before, after=after)
    db.session.commit()
    return jsonify(guardian.to_dict())


@bp.post("/<guardian_id>/link-student/<student_id>")
@permission_required("parents.update")
def link_student(guardian_id, student_id):
    guardian = scoped_query(Guardian).filter_by(id=guardian_id).first_or_404()
    student = scoped_query(Student).filter_by(id=student_id).first_or_404()
    data = request.get_json(silent=True) or {}

    existing = StudentGuardian.query.filter_by(guardian_id=guardian.id, student_id=student.id).first()
    if existing:
        return jsonify({"error": "Already linked"}), 400

    link = StudentGuardian(
        guardian=guardian, student=student,
        relationship_type=data.get("relationship_type", "parent"),
        is_primary_contact=data.get("is_primary_contact", False),
        is_emergency_contact=data.get("is_emergency_contact", False),
    )
    db.session.add(link)
    db.session.commit()
    return jsonify({"message": "Linked"}), 201
