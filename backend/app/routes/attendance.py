from datetime import datetime

from flask import Blueprint, request, jsonify
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Attendance, AttendanceStatus, DEFAULT_ATTENDANCE_STATUSES,
    Enrollment, Student,
)
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, scoped_query,
    linked_student_id, linked_guardian_children_ids, linked_staff_id, resolve_guardian_selected_child,
)
from app.utils.notify import notify_guardians_of_student

bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


# --- Statuses (spec section 30: schools can configure additional ones) ---

@bp.get("/statuses")
@permission_required("attendance.view")
def list_statuses():
    school_id = current_school_id()
    if not AttendanceStatus.query.filter_by(school_id=school_id).first():
        for s in DEFAULT_ATTENDANCE_STATUSES:
            db.session.add(AttendanceStatus(school_id=school_id, **s))
        db.session.commit()
    statuses = scoped_query(AttendanceStatus).filter_by(is_active=True).all()
    return jsonify([s.to_dict() for s in statuses])


@bp.post("/statuses")
@permission_required("attendance.settings.manage")
def create_status():
    data = request.get_json(silent=True) or {}
    if not data.get("code") or not data.get("label"):
        return jsonify({"error": "code and label are required"}), 400
    status = AttendanceStatus(
        school_id=current_school_id(), code=data["code"], label=data["label"],
        counts_as_present=data.get("counts_as_present", True),
    )
    db.session.add(status)
    db.session.commit()
    return jsonify(status.to_dict()), 201


# --- Marking attendance ---------------------------------------------------

@bp.get("")
@permission_required("attendance.view")
def list_attendance():
    """
    Query attendance for a class/section on a date, or for one student
    across a date range, whichever filters are supplied.

    Same self-scoping rule as invoices/results/assignments: a linked
    student or guardian account can only ever pull their own (or their
    child's) attendance, regardless of what student_id is passed in the
    query string, this was found missing during a gap-fix audit (the
    attendance.view permission was granted to the student role in Phase 2,
    but this endpoint never restricted which student's rows came back).
    """
    query = scoped_query(Attendance)

    student_scope = linked_student_id()
    child_id = None if student_scope else resolve_guardian_selected_child()

    if student_scope or child_id:
        query = query.filter(Attendance.student_id == (student_scope or child_id))
    else:
        for field in ["class_id", "section_id", "student_id", "subject_id", "academic_year_id"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Attendance, field) == value)

    date_str = request.args.get("date")
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if date_str:
        query = query.filter(Attendance.date == _d(date_str))
    elif start and end:
        query = query.filter(Attendance.date.between(_d(start), _d(end)))

    # Never return the whole history: take the most recent rows (500 by default, 2000 at most), then put
    # them back in date order so the response looks exactly as before. A class on one date, or one
    # student, is always far below this.
    limit = max(1, min(int(request.args.get("limit", 500)), 2000))
    rows = query.order_by(Attendance.date.desc()).limit(limit).all()
    rows.reverse()
    return jsonify([a.to_dict() for a in rows])


@bp.post("/bulk")
@permission_required("attendance.create")
def bulk_mark_attendance():
    """
    Teacher's main attendance workflow (spec section 31): pick a class/
    section/date/subject, load the enrolled students, submit statuses for
    all of them in one call.

    Body:
    {
      "class_id": "...", "section_id": "...", "subject_id": null,
      "academic_year_id": "...", "term_id": "...", "date": "2026-09-10",
      "entries": [{"student_id": "...", "status_code": "present", "note": null}, ...]
    }
    """
    data = request.get_json(silent=True) or {}
    required = ["class_id", "academic_year_id", "date", "entries"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    school_id = current_school_id()
    date_val = _d(data["date"])
    subject_id = data.get("subject_id")

    statuses_by_code = {s.code: s for s in scoped_query(AttendanceStatus).all()}
    if not statuses_by_code:
        for s in DEFAULT_ATTENDANCE_STATUSES:
            obj = AttendanceStatus(school_id=school_id, **s)
            db.session.add(obj)
            statuses_by_code[obj.code] = obj
        db.session.flush()

    user = current_user()
    # Who actually marked this: always the caller's own linked staff record.
    # A client-supplied marked_by_staff_id is only honored for wildcard
    # (admin) callers making a correction on someone else's behalf, never
    # trusted blindly, or any teacher could attribute their marking to
    # someone else.
    caller_staff_id = linked_staff_id()
    requested_marked_by = data.get("marked_by_staff_id")
    if caller_staff_id:
        marked_by_staff_id = caller_staff_id
    elif requested_marked_by and user and user.has_permission("*"):
        marked_by_staff_id = requested_marked_by
    else:
        marked_by_staff_id = None

    results = []
    errors = []
    for entry in data["entries"]:
        student_id = entry.get("student_id")
        status_code = entry.get("status_code")
        if not student_id or status_code not in statuses_by_code:
            errors.append({"student_id": student_id, "error": "Missing student_id or unknown status_code"})
            continue

        if not Student.query.filter_by(id=student_id, school_id=school_id).first():
            errors.append({"student_id": student_id, "error": "student_id does not belong to this school"})
            continue

        existing = Attendance.query.filter_by(
            student_id=student_id, date=date_val, subject_id=subject_id
        ).first()
        if existing:
            existing.status_id = statuses_by_code[status_code].id
            existing.note = entry.get("note")
            record = existing
        else:
            record = Attendance(
                school_id=school_id,
                student_id=student_id,
                class_id=data["class_id"],
                section_id=data.get("section_id"),
                subject_id=subject_id,
                academic_year_id=data["academic_year_id"],
                term_id=data.get("term_id"),
                date=date_val,
                status_id=statuses_by_code[status_code].id,
                marked_by_staff_id=marked_by_staff_id,
                note=entry.get("note"),
            )
            db.session.add(record)
        db.session.flush()  # need record.id before we can attach a notification to it
        results.append(record)

        # Only tell a guardian about statuses that don't "count as present"
        # (absent, sick, suspended, etc.), a present/late mark isn't
        # something a parent needs pinged about every single day.
        status_obj = statuses_by_code[status_code]
        if not status_obj.counts_as_present:
            notify_guardians_of_student(
                school_id, student_id, "attendance_absent",
                f"Marked {status_obj.label.lower()} on {date_val}",
                entry.get("note"), related_entity_type="attendance", related_entity_id=record.id,
            )

    db.session.commit()
    return jsonify({
        "saved": len(results),
        "errors": errors,
        "records": [r.to_dict() for r in results],
    }), 201 if not errors else 207


# --- Reports (spec section 32) -------------------------------------------

@bp.get("/reports/student/<student_id>")
@permission_required("attendance.view")
def student_attendance_report(student_id):
    """Attendance percentage for a student, optionally within a date range."""
    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()
    if student_scope and student_id != student_scope:
        return jsonify({"error": "Not found"}), 404
    if guardian_children and student_id not in guardian_children:
        return jsonify({"error": "Not found"}), 404

    query = scoped_query(Attendance).filter_by(student_id=student_id)
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if start and end:
        query = query.filter(Attendance.date.between(_d(start), _d(end)))

    records = query.all()
    total = len(records)
    present = sum(1 for r in records if r.status and r.status.counts_as_present)
    percentage = round((present / total) * 100, 1) if total else None

    return jsonify({
        "student_id": student_id, "total_days": total, "present_days": present,
        "attendance_percentage": percentage,
    })


@bp.get("/reports/class/<class_id>")
@permission_required("attendance.view")
def class_attendance_report(class_id):
    """Class-wide attendance percentage for a given date (defaults to today).
    Not available to self-scoped student/guardian accounts, a class-wide
    aggregate isn't something they have a legitimate need to see, and it's
    not their own data to view."""
    if linked_student_id() or linked_guardian_children_ids():
        return jsonify({"error": "Not found"}), 404

    date_str = request.args.get("date")
    date_val = _d(date_str) if date_str else datetime.utcnow().date()

    records = scoped_query(Attendance).filter_by(class_id=class_id, date=date_val).all()
    total = len(records)
    present = sum(1 for r in records if r.status and r.status.counts_as_present)
    percentage = round((present / total) * 100, 1) if total else None

    return jsonify({
        "class_id": class_id, "date": date_val.isoformat(),
        "total_marked": total, "present": present, "attendance_percentage": percentage,
    })


# --- Dashboard figures + staff overview -------------------------------------

def _is_self_scoped():
    return bool(linked_student_id() or linked_guardian_children_ids())


def _whole_day_stats(school_id, date_val, class_id=None):
    """School (or class) wide whole-day figures, computed from real records, never hardcoded."""
    enroll_q = Enrollment.query.filter_by(school_id=school_id, status="active")
    if class_id:
        enroll_q = enroll_q.filter_by(class_id=class_id)
    enrolled_ids = {e.student_id for e in enroll_q.all()}

    rows = scoped_query(Attendance).filter(Attendance.date == date_val, Attendance.subject_id.is_(None)).all()
    rows = [r for r in rows if r.student_id in enrolled_ids]
    present = sum(1 for r in rows if r.status and r.status.counts_as_present)
    late = sum(1 for r in rows if r.status and r.status.code == "late")
    absent = len(rows) - present
    return {
        "enrolled": len(enrolled_ids), "marked": len(rows), "present": present, "late": late,
        "absent": absent, "not_marked": max(len(enrolled_ids) - len(rows), 0),
        "percentage": round(present / len(rows) * 100, 1) if rows else None,
    }


@bp.get("/summary")
@permission_required("attendance.view")
def attendance_summary():
    """
    Whole-day attendance for a date (default today), school wide with a per class
    breakdown. Student/parent accounts get only their own (or the selected
    child's) record for that day instead, so nobody sees a school aggregate
    that is not theirs.
    """
    from app.models import SchoolClass
    date_str = request.args.get("date")
    date_val = _d(date_str) if date_str else datetime.now().date()
    school_id = current_school_id()

    if _is_self_scoped():
        student_id = linked_student_id() or resolve_guardian_selected_child()
        rows = scoped_query(Attendance).filter_by(student_id=student_id, date=date_val).all()
        whole = next((r for r in rows if r.subject_id is None), None)
        return jsonify({
            "date": date_val.isoformat(), "scope": "self", "student_id": student_id,
            "whole_day": whole.to_dict() if whole else None,
            "periods": [r.to_dict() for r in rows if r.subject_id],
        })

    data = _whole_day_stats(school_id, date_val)
    classes = []
    for c in scoped_query(SchoolClass).order_by(SchoolClass.name).all():
        stats = _whole_day_stats(school_id, date_val, c.id)
        stats.update({"class_id": c.id, "class_name": c.name})
        classes.append(stats)
    data.update({"date": date_val.isoformat(), "scope": "school", "classes": classes})
    return jsonify(data)


@bp.get("/overview")
@permission_required("attendance.view")
def attendance_overview():
    """
    One class on one date: every student with their whole-day status and each
    period's status (with the subject), plus counts per status category.
    """
    if _is_self_scoped():
        return jsonify({"error": "Not found"}), 404
    class_id = request.args.get("class_id")
    if not class_id:
        return jsonify({"error": "class_id is required"}), 400
    date_str = request.args.get("date")
    date_val = _d(date_str) if date_str else datetime.now().date()
    school_id = current_school_id()

    enrollments = Enrollment.query.filter_by(school_id=school_id, class_id=class_id, status="active").all()
    students = {s.id: s for s in Student.query.filter(Student.id.in_([e.student_id for e in enrollments] or [""])).all()}
    records = scoped_query(Attendance).filter(Attendance.class_id == class_id, Attendance.date == date_val).all()

    by_student = {}
    for r in records:
        by_student.setdefault(r.student_id, []).append(r)

    rows, category_counts = [], {}
    for sid, student in sorted(students.items(), key=lambda kv: (kv[1].last_name, kv[1].first_name)):
        recs = by_student.get(sid, [])
        whole = next((r for r in recs if r.subject_id is None), None)
        periods = [r.to_dict() for r in recs if r.subject_id]
        label = whole.status.label if whole and whole.status else "Not marked"
        category_counts[label] = category_counts.get(label, 0) + 1
        rows.append({
            "student_id": sid, "student_name": student.full_name, "student_number": student.student_number,
            "photo_url": student.photo_url, "whole_day": whole.to_dict() if whole else None,
            "whole_day_label": label, "periods": periods,
        })
    return jsonify({
        "class_id": class_id, "date": date_val.isoformat(), "students": rows, "counts": category_counts,
        "stats": _whole_day_stats(school_id, date_val, class_id),
    })
