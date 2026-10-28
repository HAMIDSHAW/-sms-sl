from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Examination, ExamSchedule
from app.utils.tenancy import current_school_id, permission_required, scoped_query

bp = Blueprint("exams", __name__, url_prefix="/api/exams")


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _t(value):
    return datetime.strptime(value, "%H:%M").time()


@bp.get("")
@permission_required("exams.view")
def list_examinations():
    query = scoped_query(Examination)
    for field in ["academic_year_id", "term_id", "status"]:
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(Examination, field) == value)
    return jsonify([e.to_dict() for e in query.order_by(Examination.start_date.desc()).all()])


@bp.post("")
@permission_required("exams.create")
def create_examination():
    data = request.get_json(silent=True) or {}
    required = ["name", "academic_year_id", "term_id", "start_date", "end_date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    exam = Examination(
        school_id=current_school_id(), name=data["name"],
        academic_year_id=data["academic_year_id"], term_id=data["term_id"],
        start_date=_d(data["start_date"]), end_date=_d(data["end_date"]),
        instructions=data.get("instructions"), status=data.get("status", "draft"),
    )
    db.session.add(exam)
    db.session.commit()
    return jsonify(exam.to_dict()), 201


@bp.patch("/<exam_id>")
@permission_required("exams.update")
def update_examination(exam_id):
    exam = scoped_query(Examination).filter_by(id=exam_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["name", "instructions", "status"]:
        if field in data:
            setattr(exam, field, data[field])
    if "start_date" in data:
        exam.start_date = _d(data["start_date"])
    if "end_date" in data:
        exam.end_date = _d(data["end_date"])
    db.session.commit()
    return jsonify(exam.to_dict())


# --- Exam schedules (spec section 42) --------------------------------------

@bp.get("/<exam_id>/schedules")
@permission_required("exams.view")
def list_schedules(exam_id):
    schedules = scoped_query(ExamSchedule).filter_by(examination_id=exam_id).order_by(ExamSchedule.date).all()
    return jsonify([s.to_dict() for s in schedules])


@bp.post("/<exam_id>/schedules")
@permission_required("exams.schedule")
def create_schedule(exam_id):
    data = request.get_json(silent=True) or {}
    required = ["subject_id", "class_id", "date", "start_time", "end_time"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    schedule = ExamSchedule(
        school_id=current_school_id(), examination_id=exam_id,
        subject_id=data["subject_id"], class_id=data["class_id"], section_id=data.get("section_id"),
        date=_d(data["date"]), start_time=_t(data["start_time"]), end_time=_t(data["end_time"]),
        room=data.get("room"), invigilator_staff_id=data.get("invigilator_staff_id"),
        max_marks=data.get("max_marks", 100),
    )
    db.session.add(schedule)
    db.session.commit()
    return jsonify(schedule.to_dict()), 201


@bp.patch("/schedules/<schedule_id>")
@permission_required("exams.schedule")
def update_schedule(schedule_id):
    schedule = scoped_query(ExamSchedule).filter_by(id=schedule_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["room", "invigilator_staff_id", "max_marks"]:
        if field in data:
            setattr(schedule, field, data[field])
    if "date" in data:
        schedule.date = _d(data["date"])
    if "start_time" in data:
        schedule.start_time = _t(data["start_time"])
    if "end_time" in data:
        schedule.end_time = _t(data["end_time"])
    db.session.commit()
    return jsonify(schedule.to_dict())
