import math
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import PayrollRun, Payslip, Staff
from app.utils.audit import record_audit
from app.utils.payroll import is_payable, payable_staff_query, suggested_entry
from app.utils.tenancy import current_school_id, current_user, permission_required, scoped_query, jwt_required_scoped

bp = Blueprint("payroll", __name__, url_prefix="/api/hr/payroll")

MONEY_FIELDS = ["base_salary", "allowances", "bonuses", "deductions", "taxes", "other_deductions"]


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _caller_staff():
    user = current_user()
    return Staff.query.filter_by(user_id=user.id, school_id=current_school_id()).first()


def _money(data, fields):
    """Pull the money fields present in data, as non-negative finite numbers. Returns (values, error)."""
    values = {}
    for field in fields:
        if field not in data:
            continue
        try:
            number = float(data[field])
        except (TypeError, ValueError):
            return None, f"{field.replace('_', ' ')} must be a number"
        if not math.isfinite(number) or number < 0:
            return None, f"{field.replace('_', ' ')} cannot be negative"
        values[field] = number
    return values, None


def _net(values):
    return (values["base_salary"] + values["allowances"] + values["bonuses"]
            - values["deductions"] - values["taxes"] - values["other_deductions"])


def _fill_run(run, entries=None):
    """
    Add a draft payslip for every current employee who is not on this run yet. Returns
    (created payslips, names with no salary on record, skipped entries). Never adds
    someone who has left, and never touches a payslip that already exists.
    """
    school_id = current_school_id()
    created, no_salary, skipped = [], [], []
    on_run = {p.staff_id for p in Payslip.query.filter_by(payroll_run_id=run.id).all()}

    if entries:
        planned = []
        for entry in entries:
            staff_id = entry.get("staff_id")
            member = Staff.query.filter_by(id=staff_id, school_id=school_id).first() if staff_id else None
            if not member:
                skipped.append({"staff_id": staff_id, "error": "staff_id does not belong to this school"})
            elif not is_payable(member):
                skipped.append({"staff_id": staff_id, "error": f"{member.full_name} is no longer an employee"})
            else:
                planned.append((member, entry))
    else:
        planned = []
        for member in payable_staff_query(school_id).order_by(Staff.last_name, Staff.first_name).all():
            entry = suggested_entry(member)
            if entry is None:
                if member.id not in on_run:
                    no_salary.append(member.full_name)
                continue
            planned.append((member, entry))

    for member, entry in planned:
        if member.id in on_run:
            continue
        slip = Payslip(
            school_id=school_id, payroll_run_id=run.id, staff_id=member.id,
            **{f: float(entry.get(f, 0) or 0) for f in MONEY_FIELDS},
        )
        db.session.add(slip)
        on_run.add(member.id)
        created.append(slip)

    if created and run.status == "draft":
        run.status = "processed"
        run.processed_at = datetime.now(timezone.utc)
    return created, no_salary, skipped


def _editable_slip(payslip_id):
    """Fetch a payslip that may still be changed, or return (None, response) explaining why not."""
    slip = scoped_query(Payslip).filter_by(id=payslip_id).first_or_404()
    run = PayrollRun.query.get(slip.payroll_run_id)
    if slip.status == "paid" or (run and run.status == "paid"):
        return None, (jsonify({"error": "This payroll run has already been paid, so its payslips can no longer be changed"}), 409)
    return slip, None


@bp.get("/runs")
@permission_required("hr.payroll.view")
def list_runs():
    return jsonify([r.to_dict() for r in scoped_query(PayrollRun).order_by(PayrollRun.period_start.desc()).all()])


@bp.post("/runs")
@permission_required("hr.payroll.manage")
def create_run():
    """
    Start a payroll run. One draft payslip per current employee is created straight
    away, filled from their standing salary, so the run shows its staff and total
    immediately. Everything can then be edited, and anyone removed, until it is paid.
    """
    data = request.get_json(silent=True) or {}
    required = ["period_label", "period_start", "period_end"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    try:
        start, end = _d(data["period_start"]), _d(data["period_end"])
    except (TypeError, ValueError):
        return jsonify({"error": "Dates must look like 2027-01-31"}), 400
    if end < start:
        return jsonify({"error": "The end date cannot be before the start date"}), 400

    run = PayrollRun(
        school_id=current_school_id(), period_label=str(data["period_label"]).strip(),
        period_start=start, period_end=end,
    )
    db.session.add(run)
    db.session.flush()
    created, no_salary, _ = _fill_run(run)
    record_audit("payroll.run.create", "hr", "payroll_run", run.id, after={"period": run.period_label, "payslips": len(created)})
    db.session.commit()
    body = run.to_dict()
    body["created"] = len(created)
    body["missing_salary"] = no_salary
    return jsonify(body), 201


@bp.post("/runs/<run_id>/generate")
@permission_required("hr.payroll.manage")
def generate_payslips(run_id):
    """Add payslips for any current employee not yet on this run (safe to repeat). Unpaid runs only."""
    run = scoped_query(PayrollRun).filter_by(id=run_id).first_or_404()
    if run.status == "paid":
        return jsonify({"error": "This payroll run has already been paid"}), 409
    data = request.get_json(silent=True) or {}
    created, no_salary, skipped = _fill_run(run, data.get("entries") or None)
    db.session.commit()
    return jsonify({
        "created": len(created), "skipped": skipped, "missing_salary": no_salary,
        "payslips": [p.to_dict() for p in created],
    }), 201


@bp.post("/runs/<run_id>/payslips")
@permission_required("hr.payroll.manage")
def add_staff_to_run(run_id):
    """Put one employee (back) on an unpaid run, e.g. after removing them by mistake."""
    run = scoped_query(PayrollRun).filter_by(id=run_id).first_or_404()
    if run.status == "paid":
        return jsonify({"error": "This payroll run has already been paid"}), 409
    data = request.get_json(silent=True) or {}
    member = Staff.query.filter_by(id=data.get("staff_id"), school_id=current_school_id()).first()
    if not member:
        return jsonify({"error": "staff_id does not belong to this school"}), 404
    if not is_payable(member):
        return jsonify({"error": f"{member.full_name} is no longer an employee and cannot be paid"}), 409
    if Payslip.query.filter_by(payroll_run_id=run.id, staff_id=member.id).first():
        return jsonify({"error": f"{member.full_name} is already on this run"}), 409

    entry = suggested_entry(member) or {}
    values, error = _money(data, MONEY_FIELDS)
    if error:
        return jsonify({"error": error}), 400
    entry.update(values)
    if not entry.get("base_salary"):
        return jsonify({"error": f"No salary on record for {member.full_name}. Enter a base salary."}), 400

    slip = Payslip(school_id=current_school_id(), payroll_run_id=run.id, staff_id=member.id,
                   **{f: float(entry.get(f, 0) or 0) for f in MONEY_FIELDS})
    db.session.add(slip)
    if run.status == "draft":
        run.status = "processed"
        run.processed_at = datetime.now(timezone.utc)
    record_audit("payslip.add", "hr", "payslip", slip.id, after={"staff": member.full_name, "run": run.period_label})
    db.session.commit()
    return jsonify(slip.to_dict()), 201


@bp.get("/payslips")
@jwt_required_scoped
def list_payslips():
    """
    HR/admin sees everyone's (filterable), but never a payslip still waiting to be paid for
    someone who has left. A staff member sees only their own, and only once it has been paid.
    """
    user = current_user()
    query = scoped_query(Payslip)

    if user.has_permission("hr.payroll.view"):
        for field in ["payroll_run_id", "staff_id"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Payslip, field) == value)
        run_status = {r.id: r.status for r in scoped_query(PayrollRun).all()}
        staff_by_id = {s.id: s for s in Staff.query.filter_by(school_id=current_school_id()).all()}
        slips = [p for p in query.all() if run_status.get(p.payroll_run_id) == "paid" or is_payable(staff_by_id.get(p.staff_id))]
        slips.sort(key=lambda p: (staff_by_id[p.staff_id].last_name if p.staff_id in staff_by_id else "", p.created_at))
        return jsonify([p.to_dict() for p in slips])

    caller_staff = _caller_staff()
    if not caller_staff:
        return jsonify({"error": "No staff record linked to this account"}), 403
    return jsonify([p.to_dict() for p in query.filter_by(staff_id=caller_staff.id, status="paid").all()])


@bp.patch("/payslips/<payslip_id>")
@permission_required("hr.payroll.manage")
def update_payslip(payslip_id):
    """
    Correct one payslip before the run is paid. Pass update_standing_salary=true together with a
    new base_salary to also make that the person's salary from now on (a raise or a cut), not
    just for this month.
    """
    slip, blocked = _editable_slip(payslip_id)
    if blocked:
        return blocked
    data = request.get_json(silent=True) or {}
    values, error = _money(data, MONEY_FIELDS)
    if error:
        return jsonify({"error": error}), 400

    merged = {f: values.get(f, getattr(slip, f)) for f in MONEY_FIELDS}
    if _net(merged) < 0:
        return jsonify({"error": "Deductions and taxes are larger than the pay, so the net would be negative"}), 400
    before = {f: getattr(slip, f) for f in MONEY_FIELDS}
    for field, value in values.items():
        setattr(slip, field, value)

    member = Staff.query.get(slip.staff_id)
    if data.get("update_standing_salary") and "base_salary" in values and member:
        old = member.base_salary
        member.base_salary = values["base_salary"]
        record_audit("staff.salary.change", "hr", "staff", member.id, before={"base_salary": old}, after={"base_salary": member.base_salary})
    record_audit("payslip.update", "hr", "payslip", slip.id, before=before, after={f: getattr(slip, f) for f in MONEY_FIELDS})
    db.session.commit()
    return jsonify(slip.to_dict())


@bp.delete("/payslips/<payslip_id>")
@permission_required("hr.payroll.manage")
def remove_payslip(payslip_id):
    """Take one person off this month's payment. Their standing salary and other months are untouched."""
    slip, blocked = _editable_slip(payslip_id)
    if blocked:
        return blocked
    member = Staff.query.get(slip.staff_id)
    run = PayrollRun.query.get(slip.payroll_run_id)
    record_audit("payslip.remove", "hr", "payslip", slip.id, before={"staff": member.full_name if member else None, "run": run.period_label if run else None})
    db.session.delete(slip)
    db.session.commit()
    return jsonify({"message": "Removed from this payroll run"})


@bp.post("/runs/<run_id>/mark-paid")
@permission_required("hr.payroll.manage")
def mark_run_paid(run_id):
    run = scoped_query(PayrollRun).filter_by(id=run_id).first_or_404()
    if run.status == "paid":
        return jsonify({"error": "This payroll run has already been paid"}), 409
    if run.status not in ("draft", "processed"):
        return jsonify({"error": f"Cannot mark a run '{run.status}' as paid"}), 409

    # Last safety net: anyone who stopped being an employee since the run was made comes off it now.
    removed = []
    for slip in Payslip.query.filter_by(payroll_run_id=run.id).all():
        member = Staff.query.get(slip.staff_id)
        if not is_payable(member):
            removed.append(member.full_name if member else "Unknown (deleted) staff member")
            db.session.delete(slip)
    db.session.flush()

    slips = Payslip.query.filter_by(payroll_run_id=run.id).all()
    if not slips:
        db.session.rollback()
        return jsonify({"error": "There is nobody left on this run to pay"}), 409

    run.status = "paid"
    from app.utils.notify import notify
    for slip in slips:
        slip.status = "paid"
        member = Staff.query.get(slip.staff_id)
        if member and member.user_id:
            notify(current_school_id(), member.user_id, "payslip_paid", f"Salary paid: {run.period_label}",
                   "Your payslip is ready to view.", related_entity_type="payslip", related_entity_id=slip.id)
    record_audit("payroll.run.paid", "hr", "payroll_run", run.id, after={"period": run.period_label, "paid": len(slips), "removed_former_staff": removed})
    db.session.commit()
    body = run.to_dict()
    body["removed_former_staff"] = removed
    return jsonify(body)
