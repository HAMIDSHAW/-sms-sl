from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Result, Enrollment, Student
from app.utils.tenancy import (
    current_school_id, permission_required, scoped_query,
    linked_student_id, linked_guardian_children_ids,
)
from app.utils.grading import compute_results, compute_class_positions

bp = Blueprint("results", __name__, url_prefix="/api/results")


@bp.post("/compute")
@permission_required("results.submit")
def compute():
    """
    Recompute results for every student enrolled in a class, for one
    examination, from their current Marks (spec section 45). Safe to
    re-run after a mark correction, it's a full recompute, not an
    increment. Also (re)computes class positions in the same call.
    """
    data = request.get_json(silent=True) or {}
    examination_id = data.get("examination_id")
    class_id = data.get("class_id")
    if not examination_id or not class_id:
        return jsonify({"error": "examination_id and class_id are required"}), 400

    school_id = current_school_id()
    enrollments = Enrollment.query.filter_by(class_id=class_id, status="active").all()

    computed = []
    for e in enrollments:
        result = compute_results(school_id, examination_id, e.student_id)
        if result:
            computed.append(result)

    db.session.commit()
    compute_class_positions(school_id, examination_id, class_id)
    db.session.commit()

    return jsonify({"computed": len(computed), "results": [r.to_dict() for r in computed]})


@bp.get("")
@permission_required("results.view")
def list_results():
    """
    Admins/teachers/exam-officers see everything for an examination/class.
    Students only ever see their own PUBLISHED result. Parents only see
    their own children's PUBLISHED results. This is enforced here, not
    left to the frontend to hide (spec section 46: "Once published,
    results become visible to students and parents according to
    permissions").
    """
    query = scoped_query(Result)

    student_id = linked_student_id()
    guardian_children = linked_guardian_children_ids()

    if student_id:
        query = query.filter(Result.student_id == student_id, Result.status == "published")
    elif guardian_children:
        query = query.filter(Result.student_id.in_(guardian_children), Result.status == "published")
    else:
        for field in ["examination_id", "student_id", "status"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Result, field) == value)

    return jsonify([r.to_dict() for r in query.all()])


# --- Approval workflow (spec section 46) -----------------------------------
# draft -> teacher_submitted -> exam_officer_review -> principal_approved -> published

@bp.post("/<result_id>/submit")
@permission_required("results.submit")
def submit_result(result_id):
    """Teacher submits a computed result for review."""
    result = scoped_query(Result).filter_by(id=result_id).first_or_404()
    if result.status != "draft":
        return jsonify({"error": f"Cannot submit a result in status '{result.status}'"}), 409
    result.status = "teacher_submitted"
    db.session.commit()
    return jsonify(result.to_dict())


@bp.post("/<result_id>/review")
@permission_required("results.review")
def review_result(result_id):
    """Exam officer reviews a submitted result, optionally adding a remark, and forwards it to the principal."""
    result = scoped_query(Result).filter_by(id=result_id).first_or_404()
    if result.status != "teacher_submitted":
        return jsonify({"error": f"Cannot review a result in status '{result.status}'"}), 409
    data = request.get_json(silent=True) or {}
    if "teacher_remark" in data:
        result.teacher_remark = data["teacher_remark"]
    result.status = "exam_officer_review"
    db.session.commit()
    return jsonify(result.to_dict())


@bp.post("/<result_id>/approve")
@permission_required("results.approve")
def approve_result(result_id):
    """Principal approves the reviewed result."""
    result = scoped_query(Result).filter_by(id=result_id).first_or_404()
    if result.status != "exam_officer_review":
        return jsonify({"error": f"Cannot approve a result in status '{result.status}'"}), 409
    data = request.get_json(silent=True) or {}
    if "principal_remark" in data:
        result.principal_remark = data["principal_remark"]
    result.status = "principal_approved"
    db.session.commit()
    return jsonify(result.to_dict())


@bp.post("/<result_id>/publish")
@permission_required("results.publish")
def publish_result(result_id):
    """Publish, this is the step that makes it visible to students/parents."""
    result = scoped_query(Result).filter_by(id=result_id).first_or_404()
    if result.status != "principal_approved":
        return jsonify({"error": f"Cannot publish a result in status '{result.status}'"}), 409
    result.status = "published"
    db.session.commit()

    from app.utils.notify import notify_guardians_of_student
    notify_guardians_of_student(
        current_school_id(), result.student_id, "result_published", "Exam result published",
        f"Grade: {result.overall_grade}", related_entity_type="result", related_entity_id=result.id,
    )
    db.session.commit()
    return jsonify(result.to_dict())


@bp.get("/report-card/<student_id>/<examination_id>")
@permission_required("results.view")
def report_card(student_id, examination_id):
    """
    Assembles everything spec section 47 asks a report card to contain:
    student identity, per-subject marks/grades, and the overall result
    summary. Returns structured JSON, a frontend renders this into the
    printable layout; PDF generation is a follow-up task (see README).

    Same visibility gate as list_results: a student/parent can only ever
    pull their own (published) report card.
    """
    from app.models import (
        School, Mark, ExamSchedule, Subject, Examination, Term,
        Enrollment, SchoolClass, Staff, TeacherAssignment, Attendance, AttendanceStatus,
    )

    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()
    if student_scope and student_id != student_scope:
        return jsonify({"error": "Not found"}), 404
    if guardian_children and student_id not in guardian_children:
        return jsonify({"error": "Not found"}), 404

    result = scoped_query(Result).filter_by(student_id=student_id, examination_id=examination_id).first()
    if not result:
        return jsonify({"error": "No result found for this student/examination"}), 404
    if (student_scope or guardian_children) and result.status != "published":
        return jsonify({"error": "Result not yet published"}), 404

    student = scoped_query(Student).filter_by(id=student_id).first_or_404()
    examination = scoped_query(Examination).filter_by(id=examination_id).first_or_404()
    school = School.query.get(current_school_id())
    term = Term.query.get(examination.term_id)

    enrollment = Enrollment.query.filter_by(
        student_id=student_id, academic_year_id=examination.academic_year_id, status="active",
    ).first()
    school_class = SchoolClass.query.get(enrollment.class_id) if enrollment else None

    class_teacher_name = None
    if school_class and school_class.class_master_staff_id:
        class_teacher = Staff.query.get(school_class.class_master_staff_id)
        class_teacher_name = class_teacher.full_name if class_teacher else None

    # Every subject actually taught to this class, not only the ones this
    # student happens to have a Mark row for, a subject with no mark yet
    # entered still belongs on the report card (as "not examined") rather
    # than silently vanishing from it.
    class_subjects = {}
    if school_class:
        for ta, subject in (
            db.session.query(TeacherAssignment, Subject)
            .join(Subject, TeacherAssignment.subject_id == Subject.id)
            .filter(TeacherAssignment.class_id == school_class.id)
            .all()
        ):
            class_subjects[subject.id] = subject

    rows = (
        db.session.query(Mark, ExamSchedule, Subject)
        .join(ExamSchedule, Mark.exam_schedule_id == ExamSchedule.id)
        .join(Subject, ExamSchedule.subject_id == Subject.id)
        .filter(ExamSchedule.examination_id == examination_id, Mark.student_id == student_id)
        .all()
    )
    marked_subject_ids = {subject.id for _, _, subject in rows}

    subjects = []
    for mark, schedule, subject in rows:
        percentage = (
            round((mark.obtained_marks / schedule.max_marks) * 100, 1)
            if mark.obtained_marks is not None and schedule.max_marks else None
        )
        subjects.append({
            "subject": subject.name, "code": subject.code,
            "obtained_marks": mark.obtained_marks, "max_marks": schedule.max_marks,
            "percentage": percentage, "is_absent": mark.is_absent, "remark": _grade_remark(percentage),
        })
    # Subjects the class takes but this student has no mark for yet.
    for subject_id, subject in class_subjects.items():
        if subject_id not in marked_subject_ids:
            subjects.append({
                "subject": subject.name, "code": subject.code,
                "obtained_marks": None, "max_marks": None,
                "percentage": None, "is_absent": False, "remark": "Not examined",
            })
    subjects.sort(key=lambda s: s["subject"])

    # Class-wide context: how many students, and the class average, both
    # meaningless to compute per-subject here (that already happens in
    # compute_class_positions at publish time), so this is specifically the
    # cohort's *overall* average for the same examination, for comparison.
    class_size = None
    class_average = None
    position = None
    ranked_count = None
    if school_class:
        class_student_ids = [
            e.student_id for e in Enrollment.query.filter_by(
                class_id=school_class.id, academic_year_id=examination.academic_year_id, status="active",
            ).all()
        ]
        class_size = len(class_student_ids)
        class_results = scoped_query(Result).filter(
            Result.examination_id == examination_id, Result.student_id.in_(class_student_ids),
            Result.average_percentage.isnot(None),
        ).all()
        if class_results:
            class_average = round(sum(r.average_percentage for r in class_results) / len(class_results), 1)
            # Position is worked out live from the class's results (ties share a rank), so it is
            # always shown and always matches the numbers on the card, even if positions were never stored.
            if result.average_percentage is not None:
                position = 1 + sum(1 for r in class_results if r.average_percentage > result.average_percentage)
                ranked_count = len(class_results)

    # Attendance for the term this examination belongs to.
    attendance_summary = None
    if term:
        att_rows = (
            db.session.query(Attendance, AttendanceStatus)
            .join(AttendanceStatus, Attendance.status_id == AttendanceStatus.id)
            .filter(
                Attendance.student_id == student_id,
                Attendance.date >= term.start_date, Attendance.date <= term.end_date,
            ).all()
        )
        total_days = len(att_rows)
        present_days = sum(1 for _, status in att_rows if status.counts_as_present)
        attendance_summary = {
            "total_days": total_days, "present_days": present_days,
            "absent_days": total_days - present_days,
            "attendance_rate": round((present_days / total_days) * 100, 1) if total_days else None,
        }

    return jsonify({
        "school": {"name": school.name, "logo_url": school.logo_url, "address": school.address},
        "student": {
            "full_name": student.full_name, "student_number": student.student_number,
            "photo_url": student.photo_url,
        },
        "class": {"name": school_class.name if school_class else None, "class_teacher_name": class_teacher_name, "class_size": class_size},
        "examination": {"name": examination.name, "term_name": term.name if term else None},
        "subjects": subjects,
        "summary": {**result.to_dict(), "overall_position": position or result.overall_position},
        "position": position or result.overall_position,
        "ranked_count": ranked_count,
        "class_average": class_average,
        "attendance": attendance_summary,
    })


def _grade_remark(percentage):
    if percentage is None:
        return None
    if percentage >= 80:
        return "Excellent"
    if percentage >= 70:
        return "Very Good"
    if percentage >= 60:
        return "Good"
    if percentage >= 50:
        return "Credit"
    if percentage >= 40:
        return "Pass"
    return "Fail"
@permission_required("results.publish")
def bulk_publish():
    """Publish every principal_approved result for an examination/class in one call."""
    data = request.get_json(silent=True) or {}
    examination_id = data.get("examination_id")
    class_id = data.get("class_id")
    if not examination_id or not class_id:
        return jsonify({"error": "examination_id and class_id are required"}), 400

    student_ids = [e.student_id for e in Enrollment.query.filter_by(class_id=class_id, status="active").all()]
    results = scoped_query(Result).filter(
        Result.examination_id == examination_id,
        Result.student_id.in_(student_ids),
        Result.status == "principal_approved",
    ).all()
    for r in results:
        r.status = "published"
    db.session.commit()
    return jsonify({"published": len(results)})
