from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Staff
from app.utils.tenancy import current_school_id, permission_required, scoped_query, has_permission
from app.utils.audit import record_audit
from app.utils.payroll import purge_unpaid_payslips

bp = Blueprint("staff", __name__, url_prefix="/api/staff")


def _next_employee_number(school_id):
    count = scoped_query(Staff).count()
    return f"EMP-{count + 1:05d}"


@bp.get("")
@permission_required("staff.view")
def list_staff():
    query = scoped_query(Staff).filter(Staff.is_deleted.is_(False))
    staff_type = request.args.get("staff_type")
    if staff_type:
        query = query.filter(Staff.staff_type == staff_type)
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Staff.first_name.ilike(like), Staff.last_name.ilike(like)))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(Staff.last_name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [s.to_dict() for s in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.get("/export.xlsx")
@permission_required("staff.view")
def export_staff_xlsx():
    from app.utils.xlsx_export import export_xlsx

    staff = scoped_query(Staff).order_by(Staff.last_name).all()
    headers = ["Title", "First name", "Last name", "Employee #", "Type", "Department", "Position", "Phone", "Email", "Address", "Status"]
    rows = [
        [s.title or "", s.first_name, s.last_name, s.employee_number, s.staff_type, s.department or "",
         s.position or "", s.phone or "", s.email or "", s.address or "", s.status]
        for s in staff
    ]
    return export_xlsx("staff_export.xlsx", "Staff", headers, rows)


@bp.get("/<staff_id>")
@permission_required("staff.view")
def get_staff(staff_id):
    staff = scoped_query(Staff).filter_by(id=staff_id).first_or_404()
    return jsonify(staff.to_dict(include_salary=has_permission("hr.payroll.view")))


@bp.post("")
@permission_required("staff.create")
def create_staff():
    data = request.get_json(silent=True) or {}
    if not data.get("first_name") or not data.get("last_name"):
        return jsonify({"error": "first_name and last_name are required"}), 400

    school_id = current_school_id()
    staff = Staff(
        school_id=school_id,
        employee_number=data.get("employee_number") or _next_employee_number(school_id),
        first_name=data["first_name"], last_name=data["last_name"],
        phone=data.get("phone"), email=data.get("email"),
        staff_type=data.get("staff_type", "teacher"),
        department=data.get("department"), position=data.get("position"),
        qualifications=data.get("qualifications"), title=data.get("title"), address=data.get("address"),
        base_salary=data.get("base_salary") if has_permission("hr.payroll.manage") else None,
        employment_date=(
            datetime.strptime(data["employment_date"], "%Y-%m-%d").date()
            if data.get("employment_date") else None
        ),
    )
    db.session.add(staff)
    db.session.commit()
    return jsonify(staff.to_dict()), 201


@bp.patch("/<staff_id>")
@permission_required("staff.update")
def update_staff(staff_id):
    staff = scoped_query(Staff).filter_by(id=staff_id).first_or_404()
    data = request.get_json(silent=True) or {}

    for field in ("first_name", "last_name"):
        if field in data and not str(data[field] or "").strip():
            return jsonify({"error": f"{field.replace('_', ' ')} cannot be empty"}), 400

    new_salary = None
    if "base_salary" in data and has_permission("hr.payroll.manage"):
        try:
            new_salary = None if data["base_salary"] in (None, "") else float(data["base_salary"])
        except (TypeError, ValueError):
            return jsonify({"error": "base salary must be a number"}), 400
        if new_salary is not None and (new_salary < 0 or new_salary != new_salary or new_salary == float("inf")):
            return jsonify({"error": "base salary cannot be negative"}), 400

    before = {"first_name": staff.first_name, "last_name": staff.last_name, "title": staff.title}
    for field in ["first_name", "last_name", "phone", "email", "staff_type", "department", "position", "qualifications", "status", "user_id", "title", "address"]:
        if field in data:
            value = data[field]
            setattr(staff, field, value.strip() if isinstance(value, str) and field in ("first_name", "last_name") else value)

    if "base_salary" in data and has_permission("hr.payroll.manage") and new_salary != staff.base_salary:
        record_audit("staff.salary.change", "hr", "staff", staff.id, before={"base_salary": staff.base_salary}, after={"base_salary": new_salary})
        staff.base_salary = new_salary

    # The person's login shows the same name as their staff record.
    if staff.user_id and any(f in data for f in ("first_name", "last_name")):
        from app.models import User
        user = User.query.get(staff.user_id)
        if user:
            user.first_name, user.last_name = staff.first_name, staff.last_name
    if before != {"first_name": staff.first_name, "last_name": staff.last_name, "title": staff.title}:
        record_audit("staff.name.change", "staff", "staff", staff.id, before=before,
                     after={"first_name": staff.first_name, "last_name": staff.last_name, "title": staff.title})

    # Someone who has left must not stay on a payroll run that is still waiting to be paid.
    if staff.status == "terminated":
        purge_unpaid_payslips(staff.school_id, staff.id)
    db.session.commit()
    return jsonify(staff.to_dict(include_salary=has_permission("hr.payroll.view")))


@bp.delete("/<staff_id>")
@permission_required("staff.delete")
def delete_staff(staff_id):
    staff = scoped_query(Staff).filter_by(id=staff_id).first_or_404()
    staff.is_deleted = True
    staff.status = "terminated"
    purge_unpaid_payslips(staff.school_id, staff.id)
    db.session.commit()
    record_audit("staff.delete", "staff", "staff", staff_id)
    db.session.commit()
    return jsonify({"message": "Staff archived"})
