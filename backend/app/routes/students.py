import csv
import io
from datetime import datetime

from flask import Blueprint, request, jsonify, Response

from app.extensions import db
from app.models import School, Student, Guardian, StudentGuardian
from app.utils.tenancy import (
    current_school_id, permission_required, scoped_query, jwt_required_scoped,
    linked_student_id, linked_guardian_children_ids,
)
from app.utils.ids import generate_student_number
from app.utils.audit import record_audit

bp = Blueprint("students", __name__, url_prefix="/api/students")

EXPORT_COLUMNS = [
    "student_number", "first_name", "middle_name", "last_name", "gender",
    "date_of_birth", "nationality", "address", "phone", "email",
    "admission_date", "admission_number", "status",
]


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@bp.get("")
@permission_required("students.view")
def list_students():
    """
    Supports search/filter/pagination per spec sections 15-16 & 126:
    ?q=<name/id/phone>&class_id=&status=&page=&per_page=
    """
    query = scoped_query(Student)

    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Student.first_name.ilike(like),
                Student.last_name.ilike(like),
                Student.student_number.ilike(like),
                Student.phone.ilike(like),
            )
        )

    status = request.args.get("status")
    if status:
        query = query.filter(Student.status == status)

    class_id = request.args.get("class_id")
    if class_id:
        from app.models import Enrollment
        in_class = [e.student_id for e in Enrollment.query.filter_by(class_id=class_id, status="active").all()]
        query = query.filter(Student.id.in_(in_class or [""]))

    query = query.filter(Student.is_deleted.is_(False))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(Student.last_name, Student.first_name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    from app.models import Enrollment, SchoolClass
    class_by_student = {}
    for e in Enrollment.query.filter(
        Enrollment.student_id.in_([s.id for s in pagination.items] or [""]), Enrollment.status == "active"
    ).all():
        class_by_student[e.student_id] = e.class_id
    class_names = {c.id: c.name for c in scoped_query(SchoolClass).all()}
    items = []
    for s in pagination.items:
        d = s.to_dict()
        d["class_id"] = class_by_student.get(s.id)
        d["class_name"] = class_names.get(class_by_student.get(s.id))
        items.append(d)

    return jsonify({
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


@bp.get("/my-children")
@jwt_required_scoped
def my_children():
    """
    A guardian's own linked children, for a child-switcher UI, a parent
    with more than one child needs to be able to say "show me THIS
    child's attendance/results/timetable", not just always see whichever
    child happens to be linked first.
    """
    ids = linked_guardian_children_ids()
    if not ids:
        return jsonify([])
    from app.models import Enrollment, SchoolClass
    students = Student.query.filter(Student.id.in_(ids)).order_by(Student.first_name).all()
    out = []
    for s in students:
        d = s.to_dict()
        enrollment = Enrollment.query.filter_by(student_id=s.id, status="active").first()
        school_class = SchoolClass.query.get(enrollment.class_id) if enrollment else None
        d["class_id"] = school_class.id if school_class else None
        d["class_name"] = school_class.name if school_class else None
        out.append(d)
    return jsonify(out)


@bp.get("/<student_id>")
@jwt_required_scoped
def get_student(student_id):
    """
    Staff with students.view see any student in the school. A student or
    guardian account with no broader permission can still view, but only
    their own (or their own child's) record. Found missing during a
    gap-fix audit: previously a student had no way to see even their own
    profile, since 'students.view' is a staff-only permission.
    """
    from app.utils.tenancy import current_user

    user = current_user()
    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()

    is_self_or_child = student_id == student_scope or student_id in guardian_children
    if not (user.has_permission("students.view") or is_self_or_child):
        return jsonify({"error": "Missing permission: students.view"}), 403

    student = scoped_query(Student).filter_by(id=student_id).first_or_404()
    return jsonify(student.to_dict())


@bp.post("")
@permission_required("students.create")
def create_student():
    data = request.get_json(silent=True) or {}
    required = ["first_name", "last_name"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    school = School.query.get(current_school_id())

    student = Student(
        school_id=school.id,
        student_number=data.get("student_number") or generate_student_number(school),
        first_name=data["first_name"],
        middle_name=data.get("middle_name"),
        last_name=data["last_name"],
        date_of_birth=_parse_date(data.get("date_of_birth")),
        gender=data.get("gender"),
        nationality=data.get("nationality"),
        address=data.get("address"),
        phone=data.get("phone"),
        email=data.get("email"),
        admission_date=_parse_date(data.get("admission_date")) or datetime.utcnow().date(),
        admission_number=data.get("admission_number"),
        emergency_contact_name=data.get("emergency_contact_name"),
        emergency_contact_phone=data.get("emergency_contact_phone"),
        custom_fields=data.get("custom_fields"),
    )
    db.session.add(student)

    # Optional inline guardian linking at creation time
    for g in data.get("guardians", []):
        guardian = None
        if g.get("guardian_id"):
            guardian = scoped_query(Guardian).filter_by(id=g["guardian_id"]).first()
        if not guardian:
            guardian = Guardian(
                school_id=school.id,
                first_name=g.get("first_name", ""),
                last_name=g.get("last_name", ""),
                phone=g.get("phone"),
                email=g.get("email"),
                address=g.get("address"),
                occupation=g.get("occupation"),
            )
            db.session.add(guardian)
            db.session.flush()
        db.session.add(StudentGuardian(
            student=student, guardian=guardian,
            relationship_type=g.get("relationship_type", "parent"),
            is_primary_contact=g.get("is_primary_contact", False),
            is_emergency_contact=g.get("is_emergency_contact", False),
        ))

    db.session.commit()
    record_audit(
        "student.create", "students", "student", student.id,
        after={"student_number": student.student_number, "name": f"{student.first_name} {student.last_name}"},
    )
    db.session.commit()
    return jsonify(student.to_dict()), 201


@bp.patch("/<student_id>")
@permission_required("students.update")
def update_student(student_id):
    student = scoped_query(Student).filter_by(id=student_id).first_or_404()
    data = request.get_json(silent=True) or {}

    editable = [
        "first_name", "middle_name", "last_name", "gender", "nationality",
        "address", "phone", "email", "admission_number",
        "emergency_contact_name", "emergency_contact_phone", "status", "custom_fields", "photo_url",
        "user_id",
    ]
    for field in ("first_name", "last_name"):
        if field in data and not str(data[field] or "").strip():
            return jsonify({"error": f"{field.replace('_', ' ')} cannot be empty"}), 400

    before = {"first_name": student.first_name, "middle_name": student.middle_name, "last_name": student.last_name}
    for field in editable:
        if field in data:
            value = data[field]
            setattr(student, field, value.strip() if isinstance(value, str) and field in ("first_name", "last_name") else value)

    if "date_of_birth" in data:
        student.date_of_birth = _parse_date(data["date_of_birth"])

    after = {"first_name": student.first_name, "middle_name": student.middle_name, "last_name": student.last_name}
    if after != before:
        # The student's login shows the same name as their record; the official name is only ever changed here.
        if student.user_id:
            from app.models import User
            user = User.query.get(student.user_id)
            if user:
                user.first_name, user.last_name = student.first_name, student.last_name
        record_audit("student.name.change", "students", "student", student.id, before=before, after=after)

    db.session.commit()
    return jsonify(student.to_dict())


@bp.delete("/<student_id>")
@permission_required("students.delete")
def delete_student(student_id):
    """Soft delete only, historical preservation (spec section 86)."""
    student = scoped_query(Student).filter_by(id=student_id).first_or_404()
    student.is_deleted = True
    student.status = "inactive"
    db.session.commit()
    record_audit("student.delete", "students", "student", student_id, before={"status": "active"})
    db.session.commit()
    return jsonify({"message": "Student archived"})


# --- Bulk export / import (spec sections 14, 77-79) -----------------------

@bp.get("/export.xlsx")
@permission_required("students.export")
def export_students_xlsx():
    """Excel export of every non-deleted student, respecting the caller's school scope."""
    from app.utils.xlsx_export import export_xlsx

    students = scoped_query(Student).filter(Student.is_deleted.is_(False)).order_by(Student.last_name).all()
    headers = [
        "Student #", "First name", "Middle name", "Last name", "Gender", "Date of birth",
        "Nationality", "Address", "Phone", "Email", "Admission date", "Admission #", "Status",
    ]
    rows = [
        [
            s.student_number, s.first_name, s.middle_name or "", s.last_name, s.gender or "",
            s.date_of_birth.isoformat() if s.date_of_birth else "", s.nationality or "", s.address or "",
            s.phone or "", s.email or "", s.admission_date.isoformat() if s.admission_date else "",
            s.admission_number or "", s.status,
        ]
        for s in students
    ]
    return export_xlsx("students_export.xlsx", "Students", headers, rows)


@bp.get("/import/template")
@permission_required("students.create")
def import_template():
    """Download-a-template step of the import workflow (spec section 78)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    return Response(
        buffer.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=student_import_template.csv"},
    )


@bp.post("/import")
@permission_required("students.create")
def import_students():
    """
    Bulk import from CSV (spec section 78 workflow: template -> fill ->
    upload -> validate -> show errors -> confirm -> create -> report).
    Invalid rows are reported, not silently dropped, valid rows are still
    created even if some rows in the same file fail.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (expected multipart field 'file')"}), 400

    file = request.files["file"]
    try:
        content = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "File must be UTF-8 encoded CSV"}), 400

    reader = csv.DictReader(io.StringIO(content))
    school = School.query.get(current_school_id())

    created, errors = [], []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        if not first_name or not last_name:
            errors.append({"row": i, "error": "first_name and last_name are required"})
            continue

        dob = None
        if row.get("date_of_birth"):
            try:
                dob = datetime.strptime(row["date_of_birth"].strip(), "%Y-%m-%d").date()
            except ValueError:
                errors.append({"row": i, "error": f"Invalid date_of_birth '{row['date_of_birth']}', expected YYYY-MM-DD"})
                continue

        student_number = (row.get("student_number") or "").strip() or generate_student_number(school)
        if Student.query.filter_by(school_id=school.id, student_number=student_number).first():
            errors.append({"row": i, "error": f"student_number '{student_number}' already exists"})
            continue

        student = Student(
            school_id=school.id, student_number=student_number,
            first_name=first_name, middle_name=(row.get("middle_name") or "").strip() or None,
            last_name=last_name, gender=(row.get("gender") or "").strip() or None,
            date_of_birth=dob, nationality=(row.get("nationality") or "").strip() or None,
            address=(row.get("address") or "").strip() or None, phone=(row.get("phone") or "").strip() or None,
            email=(row.get("email") or "").strip() or None,
            admission_number=(row.get("admission_number") or "").strip() or None,
            admission_date=datetime.utcnow().date(),
            status=(row.get("status") or "active").strip(),
        )
        db.session.add(student)
        created.append(student)

    db.session.commit()
    record_audit("students.bulk_import", "students", after={"created_count": len(created), "error_count": len(errors)})
    db.session.commit()

    return jsonify({
        "created": len(created),
        "errors": errors,
        "students": [s.to_dict() for s in created],
    }), 201 if not errors else 207
