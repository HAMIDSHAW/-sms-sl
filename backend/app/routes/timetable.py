from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import TimetableEntry, DAYS_OF_WEEK
from app.utils.tenancy import (
    current_school_id, permission_required, scoped_query,
    linked_student_id, resolve_guardian_selected_child, linked_staff_id,
)

bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")


def _t(value):
    return datetime.strptime(value, "%H:%M").time()


def _overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def find_conflicts(school_id, day_of_week, start_time, end_time, staff_id, class_id, section_id, room,
                    academic_year_id, exclude_id=None):
    """
    Returns a list of human-readable conflict descriptions, or an empty list
    if the slot is clear. Checks, per spec section 34:
      - Teacher conflicts (same staff_id double-booked)
      - Room conflicts (same room double-booked)
      - Class/section conflicts (same class+section double-booked)
    all restricted to the same day_of_week + academic_year, with a genuine
    time overlap (not just same start time).
    """
    candidates = TimetableEntry.query.filter_by(
        school_id=school_id, day_of_week=day_of_week, academic_year_id=academic_year_id
    )
    if exclude_id:
        candidates = candidates.filter(TimetableEntry.id != exclude_id)

    conflicts = []
    for entry in candidates.all():
        if not _overlaps(start_time, end_time, entry.start_time, entry.end_time):
            continue

        if entry.staff_id == staff_id:
            conflicts.append(
                f"Teacher already scheduled {entry.start_time.strftime('%H:%M')}-"
                f"{entry.end_time.strftime('%H:%M')} on {day_of_week}"
            )
        if room and entry.room and entry.room == room:
            conflicts.append(
                f"Room '{room}' already booked {entry.start_time.strftime('%H:%M')}-"
                f"{entry.end_time.strftime('%H:%M')} on {day_of_week}"
            )
        if entry.class_id == class_id and (section_id is None or entry.section_id == section_id):
            conflicts.append(
                f"Class/section already has a period {entry.start_time.strftime('%H:%M')}-"
                f"{entry.end_time.strftime('%H:%M')} on {day_of_week}"
            )

    return conflicts


@bp.get("/mine")
@permission_required("attendance.create")
def my_periods_today():
    """
    A teacher's own timetable periods for a given day (defaults to
    today), the entry point for the real per-period attendance
    workflow: pick which of YOUR OWN periods you're marking, rather than
    picking any class off a general list. Also flags which of these
    classes you're the class master for, since that unlocks the
    additional whole-day attendance check.
    """
    from app.models import SchoolClass, Subject

    staff_id = linked_staff_id()
    if not staff_id:
        return jsonify([])

    day = request.args.get("day") or datetime.now().strftime("%A").lower()
    entries = scoped_query(TimetableEntry).filter_by(staff_id=staff_id, day_of_week=day).order_by(TimetableEntry.start_time).all()

    master_class_ids = {c.id for c in scoped_query(SchoolClass).filter_by(class_master_staff_id=staff_id).all()}
    subjects_by_id = {s.id: s.name for s in scoped_query(Subject).all()}
    classes_by_id = {c.id: c.name for c in scoped_query(SchoolClass).all()}

    return jsonify([
        {
            **e.to_dict(),
            "subject_name": subjects_by_id.get(e.subject_id),
            "class_name": classes_by_id.get(e.class_id),
            "is_class_master_here": e.class_id in master_class_ids,
        }
        for e in entries
    ])


@bp.get("/mine/summary")
@permission_required("attendance.create")
def my_teaching_summary():
    """
    Two numbers a teacher wants at a glance on their dashboard: how many
    distinct classes they teach across the whole week, and how many
    periods they have today specifically. /mine already answers the
    "today" half (day-scoped by design, for the attendance-marking flow)
    but has no sense of the whole week, so this is kept as its own small
    endpoint rather than making /mine do two different jobs.
    """
    staff_id = linked_staff_id()
    if not staff_id:
        return jsonify({"classes_taught": 0, "periods_today": 0})

    today = datetime.now().strftime("%A").lower()
    all_entries = scoped_query(TimetableEntry).filter_by(staff_id=staff_id).all()
    periods_today = sum(1 for e in all_entries if e.day_of_week == today)
    classes_taught = len({e.class_id for e in all_entries})

    return jsonify({"classes_taught": classes_taught, "periods_today": periods_today})


@bp.get("")
@permission_required("timetable.view")
def list_timetable():
    """
    Filter by class_id, section_id, staff_id (teacher timetable), or
    day_of_week, matches the class/teacher/student timetable views in
    spec section 33.

    Self-scoping: a linked student or guardian account always gets the
    student's own enrolled class/section timetable, regardless of what
    class_id is passed in the query string, a student should never be
    able to browse another class's schedule. Found missing during
    testing (timetable.view was granted broadly in an earlier phase, but
    unlike attendance/results/invoices, this endpoint was never actually
    restricted to the caller's own class).
    """
    from app.models import Enrollment

    query = scoped_query(TimetableEntry)

    student_scope = linked_student_id()
    self_scoped_student_id = student_scope or resolve_guardian_selected_child()

    if self_scoped_student_id:
        enrollment = (
            Enrollment.query.filter_by(student_id=self_scoped_student_id, status="active")
            .order_by(Enrollment.enrollment_date.desc())
            .first()
        )
        if not enrollment:
            return jsonify([])
        query = query.filter(TimetableEntry.class_id == enrollment.class_id)
        if enrollment.section_id:
            query = query.filter(
                (TimetableEntry.section_id == enrollment.section_id) | (TimetableEntry.section_id.is_(None))
            )
    else:
        for field in ["class_id", "section_id", "staff_id", "academic_year_id", "day_of_week"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(TimetableEntry, field) == value)

    entries = query.all()
    return jsonify([e.to_dict() for e in entries])


@bp.post("")
@permission_required("timetable.manage")
def create_entry():
    data = request.get_json(silent=True) or {}
    required = ["academic_year_id", "class_id", "subject_id", "staff_id", "day_of_week", "start_time", "end_time"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    day = data["day_of_week"].lower()
    if day not in DAYS_OF_WEEK:
        return jsonify({"error": f"day_of_week must be one of {DAYS_OF_WEEK}"}), 400

    start_time, end_time = _t(data["start_time"]), _t(data["end_time"])
    if start_time >= end_time:
        return jsonify({"error": "start_time must be before end_time"}), 400

    school_id = current_school_id()
    conflicts = find_conflicts(
        school_id, day, start_time, end_time,
        staff_id=data["staff_id"], class_id=data["class_id"], section_id=data.get("section_id"),
        room=data.get("room"), academic_year_id=data["academic_year_id"],
    )
    if conflicts:
        return jsonify({"error": "Scheduling conflict", "conflicts": conflicts}), 409

    entry = TimetableEntry(
        school_id=school_id,
        academic_year_id=data["academic_year_id"], class_id=data["class_id"],
        section_id=data.get("section_id"), subject_id=data["subject_id"], staff_id=data["staff_id"],
        day_of_week=day, start_time=start_time, end_time=end_time, room=data.get("room"),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


@bp.patch("/<entry_id>")
@permission_required("timetable.manage")
def update_entry(entry_id):
    entry = scoped_query(TimetableEntry).filter_by(id=entry_id).first_or_404()
    data = request.get_json(silent=True) or {}

    day = data.get("day_of_week", entry.day_of_week).lower()
    start_time = _t(data["start_time"]) if "start_time" in data else entry.start_time
    end_time = _t(data["end_time"]) if "end_time" in data else entry.end_time
    staff_id = data.get("staff_id", entry.staff_id)
    class_id = data.get("class_id", entry.class_id)
    section_id = data.get("section_id", entry.section_id)
    room = data.get("room", entry.room)

    if start_time >= end_time:
        return jsonify({"error": "start_time must be before end_time"}), 400

    conflicts = find_conflicts(
        current_school_id(), day, start_time, end_time,
        staff_id=staff_id, class_id=class_id, section_id=section_id, room=room,
        academic_year_id=entry.academic_year_id, exclude_id=entry.id,
    )
    if conflicts:
        return jsonify({"error": "Scheduling conflict", "conflicts": conflicts}), 409

    entry.day_of_week, entry.start_time, entry.end_time = day, start_time, end_time
    entry.staff_id, entry.class_id, entry.section_id, entry.room = staff_id, class_id, section_id, room
    if "subject_id" in data:
        entry.subject_id = data["subject_id"]

    db.session.commit()
    return jsonify(entry.to_dict())


@bp.delete("/<entry_id>")
@permission_required("timetable.manage")
def delete_entry(entry_id):
    entry = scoped_query(TimetableEntry).filter_by(id=entry_id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"message": "Timetable entry removed"})
