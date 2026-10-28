from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import DisciplinaryRecord, Student
from app.utils.tenancy import current_school_id, current_user, permission_required, scoped_query

bp = Blueprint("discipline", __name__, url_prefix="/api/discipline")


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _caller_staff():
    from app.models import Staff
    user = current_user()
    return Staff.query.filter_by(user_id=user.id, school_id=current_school_id()).first()


def _notify_parents(student, record, headline):
    from app.utils.notify import notify_guardians_of_student
    body = f"{record.category.replace('_', ' ').title()}: {record.description}"
    if record.action_taken:
        body += f" Action taken: {record.action_taken}"
    notify_guardians_of_student(
        current_school_id(), student.id, "discipline", f"{headline}: {student.full_name}", body,
        related_entity_type="discipline", related_entity_id=record.id,
    )


@bp.get("")
@permission_required("discipline.view")
def list_records():
    """
    Staff-only (see backend README for why student/parent self-view isn't
    wired up here, a deliberate scope decision, not an oversight).
    Filterable by student, category, or status.
    """
    query = scoped_query(DisciplinaryRecord)
    for field in ["student_id", "category", "status"]:
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(DisciplinaryRecord, field) == value)
    class_id = request.args.get("class_id")
    if class_id:
        from app.models import Enrollment
        ids = [e.student_id for e in Enrollment.query.filter_by(class_id=class_id, status="active").all()]
        query = query.filter(DisciplinaryRecord.student_id.in_(ids or [""]))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(DisciplinaryRecord.date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [r.to_dict() for r in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.post("")
@permission_required("discipline.create")
def create_record():
    data = request.get_json(silent=True) or {}
    required = ["student_id", "category", "description"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    school_id = current_school_id()
    student = Student.query.filter_by(id=data["student_id"], school_id=school_id).first()
    if not student:
        return jsonify({"error": "student_id does not belong to this school"}), 404

    caller_staff = _caller_staff()

    record = DisciplinaryRecord(
        school_id=school_id, student_id=student.id,
        reported_by_staff_id=caller_staff.id if caller_staff else data.get("reported_by_staff_id"),
        date=_d(data["date"]) if data.get("date") else datetime.utcnow().date(),
        category=data["category"], severity=data.get("severity"),
        description=data["description"], action_taken=data.get("action_taken"),
        status=data.get("status", "open"),
    )
    db.session.add(record)
    db.session.flush()
    if data.get("notify_guardians"):
        _notify_parents(student, record, "Discipline report")
    db.session.commit()
    return jsonify(record.to_dict()), 201


@bp.patch("/<record_id>")
@permission_required("discipline.update")
def update_record(record_id):
    record = scoped_query(DisciplinaryRecord).filter_by(id=record_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["category", "severity", "description", "action_taken", "status"]:
        if field in data:
            setattr(record, field, data[field])
    if data.get("notify_guardians"):
        student = Student.query.get(record.student_id)
        if student:
            _notify_parents(student, record, "Discipline update")
    db.session.commit()
    return jsonify(record.to_dict())


@bp.post("/<record_id>/resolve")
@permission_required("discipline.resolve")
def resolve_record(record_id):
    """Close out a record with a follow-up note, separate from a plain edit, since it marks a specific lifecycle event."""
    record = scoped_query(DisciplinaryRecord).filter_by(id=record_id).first_or_404()
    data = request.get_json(silent=True) or {}
    caller_staff = _caller_staff()

    record.status = "resolved"
    record.follow_up_note = data.get("follow_up_note")
    record.follow_up_by_staff_id = caller_staff.id if caller_staff else None
    record.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(record.to_dict())
