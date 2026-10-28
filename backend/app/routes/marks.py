from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Mark, ExamSchedule, Enrollment
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, scoped_query,
    linked_student_id, linked_guardian_children_ids,
)

bp = Blueprint("marks", __name__, url_prefix="/api/marks")


@bp.get("")
@permission_required("exams.view")
def list_marks():
    query = scoped_query(Mark)
    # A student sees only their own marks and a parent only their children's. Teachers and exam
    # staff (who hold exams.view without being family accounts) see the whole school as before.
    own = linked_student_id()
    children = linked_guardian_children_ids()
    if own:
        query = query.filter(Mark.student_id == own)
    elif children:
        query = query.filter(Mark.student_id.in_(children))
    schedule_id = request.args.get("exam_schedule_id")
    student_id = request.args.get("student_id")
    if schedule_id:
        query = query.filter_by(exam_schedule_id=schedule_id)
    if student_id:
        query = query.filter_by(student_id=student_id)
    return jsonify([m.to_dict() for m in query.all()])


@bp.post("/bulk")
@permission_required("exams.mark")
def bulk_enter_marks():
    """
    Teacher's mark-entry workflow (spec section 43): pick an exam schedule
    (one subject sitting), enter every student's score in one call.

    Body: {"exam_schedule_id": "...", "entries": [{"student_id": "...", "obtained_marks": 78, "is_absent": false}]}
    """
    data = request.get_json(silent=True) or {}
    if not data.get("exam_schedule_id") or not data.get("entries"):
        return jsonify({"error": "exam_schedule_id and entries are required"}), 400

    schedule = scoped_query(ExamSchedule).filter_by(id=data["exam_schedule_id"]).first_or_404()
    school_id = current_school_id()
    user = current_user()

    # Find the acting teacher's staff record, if any, purely for the audit trail on each mark.
    # Same rule as assignment authorship: derive from the caller's own
    # linked staff record when one exists, rather than trusting whatever
    # the request body says.
    from app.models import Staff as StaffModel
    caller_staff = StaffModel.query.filter_by(user_id=current_user().id, school_id=school_id).first()
    entered_by_staff_id = caller_staff.id if caller_staff else data.get("entered_by_staff_id")

    saved, errors = [], []
    for entry in data["entries"]:
        student_id = entry.get("student_id")
        if not student_id:
            errors.append({"error": "Missing student_id"})
            continue

        from app.models import Student
        if not Student.query.filter_by(id=student_id, school_id=school_id).first():
            errors.append({"student_id": student_id, "error": "student_id does not belong to this school"})
            continue

        obtained = entry.get("obtained_marks")
        if obtained is not None and (obtained < 0 or obtained > schedule.max_marks):
            errors.append({"student_id": student_id, "error": f"obtained_marks must be between 0 and {schedule.max_marks}"})
            continue

        mark = Mark.query.filter_by(exam_schedule_id=schedule.id, student_id=student_id).first()
        if not mark:
            mark = Mark(school_id=school_id, exam_schedule_id=schedule.id, student_id=student_id)
            db.session.add(mark)

        mark.obtained_marks = obtained
        mark.is_absent = entry.get("is_absent", False)
        mark.comment = entry.get("comment")
        mark.entered_by_staff_id = entered_by_staff_id
        saved.append(mark)

    db.session.commit()
    return jsonify({
        "saved": len(saved), "errors": errors, "marks": [m.to_dict() for m in saved],
    }), 201 if not errors else 207
