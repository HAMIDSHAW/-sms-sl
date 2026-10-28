from datetime import date, timedelta

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import (
    Student, Staff, Enrollment, SchoolClass, Attendance,
    Result, Subject, ExamSchedule, Mark, Invoice, Payment,
)
from app.utils.tenancy import current_school_id, permission_required, scoped_query

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


# --- Dashboard overview (spec section 9: admin dashboard numbers) ----------

@bp.get("/overview")
@permission_required("analytics.view")
def overview():
    """
    One-call summary for a landing dashboard, total students/staff,
    today's attendance percentage, and current fee collection rate. Each
    number is computed live from its source table, same rule as
    everywhere else in this codebase: no cached/duplicated totals that
    could drift.
    """
    total_students = scoped_query(Student).filter_by(is_deleted=False).count()
    total_staff = scoped_query(Staff).filter_by(is_deleted=False).count()

    today = date.today()
    today_records = scoped_query(Attendance).filter(Attendance.date == today, Attendance.subject_id.is_(None)).all()
    present_today = sum(1 for r in today_records if r.status and r.status.counts_as_present)
    attendance_today_pct = round((present_today / len(today_records)) * 100, 1) if today_records else None

    invoices = scoped_query(Invoice).all()
    payments = scoped_query(Payment).filter_by(status="successful").all()
    total_billed = sum(i.amount for i in invoices)
    total_collected = sum(p.amount for p in payments)
    collection_rate = round((total_collected / total_billed) * 100, 1) if total_billed else None

    return jsonify({
        "total_students": total_students,
        "total_staff": total_staff,
        "attendance_today_percentage": attendance_today_pct,
        "fee_collection_rate": collection_rate,
        "outstanding_fees": total_billed - total_collected,
    })


# --- Enrollment trends (spec section 70) -----------------------------------

@bp.get("/enrollment")
@permission_required("analytics.view")
def enrollment_by_class():
    """Current active enrollment count per class, the basic 'how full is each class' view."""
    academic_year_id = request.args.get("academic_year_id")
    query = scoped_query(Enrollment).filter_by(status="active")
    if academic_year_id:
        query = query.filter_by(academic_year_id=academic_year_id)

    counts = {}
    for e in query.all():
        counts[e.class_id] = counts.get(e.class_id, 0) + 1

    classes = scoped_query(SchoolClass).all()
    return jsonify([
        {"class_id": c.id, "class_name": c.name, "enrolled_count": counts.get(c.id, 0)}
        for c in sorted(classes, key=lambda c: c.order_index)
    ])


# --- Attendance trend (spec section 32 aggregated over time) ---------------

@bp.get("/attendance-trend")
@permission_required("analytics.view")
def attendance_trend():
    """School-wide daily attendance percentage over the last N days (default 30)."""
    days = min(int(request.args.get("days", 30)), 180)
    start = date.today() - timedelta(days=days)

    records = scoped_query(Attendance).filter(Attendance.date >= start, Attendance.subject_id.is_(None)).all()
    by_day = {}
    for r in records:
        by_day.setdefault(r.date, []).append(r)

    trend = []
    for day, recs in sorted(by_day.items()):
        present = sum(1 for r in recs if r.status and r.status.counts_as_present)
        trend.append({
            "date": day.isoformat(), "total_marked": len(recs), "present": present,
            "percentage": round((present / len(recs)) * 100, 1) if recs else None,
        })
    return jsonify(trend)


# --- Academic performance (spec sections 109-111) --------------------------

@bp.get("/academic-performance")
@permission_required("analytics.view")
def academic_performance():
    """
    Class and subject-level performance for one examination: average,
    pass rate, highest/lowest score. Class-level numbers reuse Result
    (already computed by the grading engine, including each school's own
    pass/fail band); subject-level numbers come straight from Mark against
    a flat 50% threshold, since a single Mark has no grade-scale lookup of
    its own, only the aggregated Result does.
    """
    examination_id = request.args.get("examination_id")
    if not examination_id:
        return jsonify({"error": "examination_id is required"}), 400

    results = scoped_query(Result).filter_by(
        examination_id=examination_id
    ).filter(Result.average_percentage.isnot(None)).all()

    # Look up each result's class via its student's active enrollment, once.
    student_class = {}
    for r in results:
        enrollment = Enrollment.query.filter_by(student_id=r.student_id, status="active").first()
        student_class[r.student_id] = enrollment.class_id if enrollment else None

    classes_by_id = {c.id: c.name for c in scoped_query(SchoolClass).all()}
    by_class = {}
    for r in results:
        class_id = student_class.get(r.student_id)
        by_class.setdefault(class_id, []).append(r)

    class_performance = []
    for class_id, class_results in by_class.items():
        scores = [r.average_percentage for r in class_results]
        pass_count = sum(1 for r in class_results if r.is_pass)
        class_performance.append({
            "class_id": class_id, "class_name": classes_by_id.get(class_id, "Unknown"),
            "average": round(sum(scores) / len(scores), 1), "highest": max(scores), "lowest": min(scores),
            "student_count": len(scores), "pass_rate": round((pass_count / len(scores)) * 100, 1),
        })

    # Subject-level: pull every Mark tied to this examination's schedules.
    rows = (
        db.session.query(Mark, ExamSchedule, Subject)
        .join(ExamSchedule, Mark.exam_schedule_id == ExamSchedule.id)
        .join(Subject, ExamSchedule.subject_id == Subject.id)
        .filter(ExamSchedule.examination_id == examination_id, Mark.is_absent.is_(False), Mark.obtained_marks.isnot(None))
        .all()
    )
    subject_stats = {}
    for mark, schedule, subject in rows:
        pct = (mark.obtained_marks / schedule.max_marks) * 100 if schedule.max_marks else 0
        subject_stats.setdefault(subject.id, {"name": subject.name, "percentages": []})
        subject_stats[subject.id]["percentages"].append(pct)

    subject_performance = []
    for subject_id, info in subject_stats.items():
        pcts = info["percentages"]
        pass_count = sum(1 for p in pcts if p >= 50)
        subject_performance.append({
            "subject_id": subject_id, "subject_name": info["name"],
            "average_percentage": round(sum(pcts) / len(pcts), 1),
            "highest": round(max(pcts), 1), "lowest": round(min(pcts), 1),
            "entries": len(pcts), "pass_rate": round((pass_count / len(pcts)) * 100, 1),
        })

    return jsonify({"class_performance": class_performance, "subject_performance": subject_performance})
