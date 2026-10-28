from datetime import datetime

from flask import Blueprint, request, jsonify

from app.models import Enrollment, Student
from app.extensions import db
from app.utils.tenancy import current_school_id, permission_required, scoped_query

bp = Blueprint("enrollments", __name__, url_prefix="/api/enrollments")


@bp.get("")
@permission_required("enrollment.view")
def list_enrollments():
    query = scoped_query(Enrollment)
    for field in ["academic_year_id", "class_id", "section_id", "student_id"]:
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(Enrollment, field) == value)
    return jsonify([e.to_dict() for e in query.all()])


@bp.post("")
@permission_required("enrollment.manage")
def create_enrollment():
    """
    Enroll a student into a class/section for an academic year. This is the
    record everything else (timetable, attendance, exams) hangs off of
    (spec section 2), a student search or a request that name-checks a
    class only ever resolves through this table, never a duplicated
    "current class" field on the student itself.
    """
    data = request.get_json(silent=True) or {}
    required = ["student_id", "academic_year_id", "class_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    student = scoped_query(Student).filter_by(id=data["student_id"]).first_or_404()

    existing = Enrollment.query.filter_by(
        student_id=student.id, academic_year_id=data["academic_year_id"]
    ).first()
    if existing:
        return jsonify({"error": "Student already enrolled for this academic year"}), 400

    enrollment = Enrollment(
        school_id=current_school_id(),
        student_id=student.id,
        academic_year_id=data["academic_year_id"],
        class_id=data["class_id"],
        section_id=data.get("section_id"),
        enrollment_date=(
            datetime.strptime(data["enrollment_date"], "%Y-%m-%d").date()
            if data.get("enrollment_date") else datetime.utcnow().date()
        ),
    )
    db.session.add(enrollment)
    db.session.commit()
    return jsonify(enrollment.to_dict()), 201


@bp.patch("/<enrollment_id>")
@permission_required("enrollment.manage")
def update_enrollment(enrollment_id):
    """Move a student to a different class/section, or change status (promoted/transferred/withdrawn)."""
    enrollment = scoped_query(Enrollment).filter_by(id=enrollment_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["class_id", "section_id", "status"]:
        if field in data:
            setattr(enrollment, field, data[field])
    db.session.commit()
    return jsonify(enrollment.to_dict())
