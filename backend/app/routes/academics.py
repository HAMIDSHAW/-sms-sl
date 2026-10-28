from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import AcademicYear, Term, SchoolClass, Section, Subject, TeacherAssignment
from app.utils.tenancy import current_school_id, permission_required, scoped_query

bp = Blueprint("academics", __name__, url_prefix="/api/academics")


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


# --- Academic Years --------------------------------------------------

@bp.get("/years")
@permission_required("academics.view")
def list_years():
    years = scoped_query(AcademicYear).order_by(AcademicYear.start_date.desc()).all()
    return jsonify([y.to_dict() for y in years])


@bp.post("/years")
@permission_required("academics.manage")
def create_year():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("start_date") or not data.get("end_date"):
        return jsonify({"error": "name, start_date, end_date are required"}), 400

    if data.get("is_current"):
        scoped_query(AcademicYear).update({"is_current": False})

    year = AcademicYear(
        school_id=current_school_id(), name=data["name"],
        start_date=_d(data["start_date"]), end_date=_d(data["end_date"]),
        is_current=bool(data.get("is_current", False)),
    )
    db.session.add(year)
    db.session.commit()
    return jsonify(year.to_dict()), 201


# --- Terms -------------------------------------------------------------

@bp.get("/years/<year_id>/terms")
@permission_required("academics.view")
def list_terms(year_id):
    terms = scoped_query(Term).filter_by(academic_year_id=year_id).order_by(Term.start_date).all()
    return jsonify([t.to_dict() for t in terms])


@bp.post("/years/<year_id>/terms")
@permission_required("academics.manage")
def create_term(year_id):
    """year_id comes from the URL, validated here (same gap-audit pattern as create_section)."""
    year = scoped_query(AcademicYear).filter_by(id=year_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("start_date") or not data.get("end_date"):
        return jsonify({"error": "name, start_date, end_date are required"}), 400

    if data.get("is_current"):
        scoped_query(Term).filter_by(academic_year_id=year.id).update({"is_current": False})

    term = Term(
        school_id=current_school_id(), academic_year_id=year.id, name=data["name"],
        start_date=_d(data["start_date"]), end_date=_d(data["end_date"]),
        is_current=bool(data.get("is_current", False)),
    )
    db.session.add(term)
    db.session.commit()
    return jsonify(term.to_dict()), 201


# --- Classes -------------------------------------------------------------

@bp.get("/classes")
@permission_required("academics.view")
def list_classes():
    classes = scoped_query(SchoolClass).order_by(SchoolClass.order_index).all()
    return jsonify([c.to_dict() for c in classes])


@bp.post("/classes")
@permission_required("academics.manage")
def create_class():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    school_class = SchoolClass(
        school_id=current_school_id(), name=data["name"], order_index=data.get("order_index", 0),
    )
    db.session.add(school_class)
    db.session.commit()
    return jsonify(school_class.to_dict()), 201


@bp.patch("/classes/<class_id>")
@permission_required("academics.manage")
def update_class(class_id):
    school_class = scoped_query(SchoolClass).filter_by(id=class_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "class_master_staff_id" in data and data["class_master_staff_id"]:
        from app.models import Staff
        if not Staff.query.filter_by(id=data["class_master_staff_id"], school_id=current_school_id()).first():
            return jsonify({"error": "class_master_staff_id does not belong to this school"}), 404
    for field in ["name", "order_index", "is_active", "class_master_staff_id"]:
        if field in data:
            setattr(school_class, field, data[field])
    db.session.commit()
    return jsonify(school_class.to_dict())


# --- Sections -------------------------------------------------------------

@bp.get("/classes/<class_id>/sections")
@permission_required("academics.view")
def list_sections(class_id):
    sections = scoped_query(Section).filter_by(class_id=class_id).order_by(Section.name).all()
    return jsonify([s.to_dict() for s in sections])


@bp.post("/classes/<class_id>/sections")
@permission_required("academics.manage")
def create_section(class_id):
    """class_id comes from the URL, not validated until now, found during a gap audit. Without this check, a
    section could be created attached to a class from a different school entirely."""
    school_class = scoped_query(SchoolClass).filter_by(id=class_id).first_or_404()
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    section = Section(
        school_id=current_school_id(), class_id=school_class.id, name=data["name"],
        capacity=data.get("capacity"), class_teacher_staff_id=data.get("class_teacher_staff_id"),
    )
    db.session.add(section)
    db.session.commit()
    return jsonify(section.to_dict()), 201


# --- Subjects -------------------------------------------------------------

@bp.get("/subjects")
@permission_required("academics.view")
def list_subjects():
    subjects = scoped_query(Subject).order_by(Subject.name).all()
    return jsonify([s.to_dict() for s in subjects])


@bp.post("/subjects")
@permission_required("academics.manage")
def create_subject():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    subject = Subject(
        school_id=current_school_id(), name=data["name"], code=data.get("code"),
        department=data.get("department"), max_marks=data.get("max_marks", 100),
        pass_mark=data.get("pass_mark", 50),
    )
    db.session.add(subject)
    db.session.commit()
    return jsonify(subject.to_dict()), 201


@bp.patch("/subjects/<subject_id>")
@permission_required("academics.manage")
def update_subject(subject_id):
    subject = scoped_query(Subject).filter_by(id=subject_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["name", "code", "department", "max_marks", "pass_mark", "is_active"]:
        if field in data:
            setattr(subject, field, data[field])
    db.session.commit()
    return jsonify(subject.to_dict())


# --- Teacher-subject assignment (spec section 28) --------------------------
# Was previously a model with no route, the messaging relationship rule
# (spec section 56, which teacher can message which guardian) depends on
# this existing, so it was found and added during the Phase 6 gap check.

@bp.get("/teacher-assignments")
@permission_required("academics.view")
def list_teacher_assignments():
    query = scoped_query(TeacherAssignment)
    for field in ["staff_id", "class_id", "subject_id", "academic_year_id"]:
        value = request.args.get(field)
        if value:
            query = query.filter(getattr(TeacherAssignment, field) == value)
    return jsonify([{
        "id": a.id, "staff_id": a.staff_id, "subject_id": a.subject_id,
        "class_id": a.class_id, "section_id": a.section_id, "academic_year_id": a.academic_year_id,
    } for a in query.all()])


@bp.post("/teacher-assignments")
@permission_required("academics.manage")
def create_teacher_assignment():
    """
    The system must prevent invalid or conflicting assignments (spec
    section 28), enforced here via the model's unique constraint
    (staff+subject+class+section+year can't repeat), not just a soft
    convention.
    """
    data = request.get_json(silent=True) or {}
    required = ["staff_id", "subject_id", "class_id", "academic_year_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    existing = TeacherAssignment.query.filter_by(
        staff_id=data["staff_id"], subject_id=data["subject_id"], class_id=data["class_id"],
        section_id=data.get("section_id"), academic_year_id=data["academic_year_id"],
    ).first()
    if existing:
        return jsonify({"error": "This teacher is already assigned to this subject/class/section/year"}), 400

    assignment = TeacherAssignment(
        school_id=current_school_id(), staff_id=data["staff_id"], subject_id=data["subject_id"],
        class_id=data["class_id"], section_id=data.get("section_id"), academic_year_id=data["academic_year_id"],
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({
        "id": assignment.id, "staff_id": assignment.staff_id, "subject_id": assignment.subject_id,
        "class_id": assignment.class_id, "section_id": assignment.section_id,
        "academic_year_id": assignment.academic_year_id,
    }), 201


@bp.delete("/teacher-assignments/<assignment_id>")
@permission_required("academics.manage")
def delete_teacher_assignment(assignment_id):
    assignment = scoped_query(TeacherAssignment).filter_by(id=assignment_id).first_or_404()
    db.session.delete(assignment)
    db.session.commit()
    return jsonify({"message": "Teacher assignment removed"})
