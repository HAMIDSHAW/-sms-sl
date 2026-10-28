"""
Shared payroll rules, so the routes, the staff routes and the models all agree on
who may be paid and how a payslip is first filled in.

A person is "payable" only while they are a current employee: not archived/deleted
and not terminated. Anyone else must never end up on a payslip that is still to be
paid, because that would mean paying someone who no longer works here.
"""
from app.extensions import db

PAYABLE_STATUSES = ("active", "on_leave")
DEFAULT_ALLOWANCE_RATE = 0.10
DEFAULT_TAX_RATE = 0.075


def is_payable(staff):
    return bool(staff) and not staff.is_deleted and staff.status in PAYABLE_STATUSES


def payable_staff_query(school_id):
    from app.models import Staff
    return Staff.query.filter(
        Staff.school_id == school_id, Staff.is_deleted.is_(False), Staff.status.in_(PAYABLE_STATUSES)
    )


def suggested_entry(member):
    """
    Draft figures for one staff member's payslip.

    The staff record's own base salary is the standing salary (HR raises or lowers it
    there), so a new run always starts from it. Allowances and tax follow the same
    proportion as the person's last payslip, so a raise flows through to them; fixed
    deductions are carried over unchanged. With no earlier payslip, defaults are used.
    """
    from app.models import Payslip
    last = (
        Payslip.query.filter_by(school_id=member.school_id, staff_id=member.id)
        .order_by(Payslip.created_at.desc()).first()
    )
    base = member.base_salary if member.base_salary is not None else (last.base_salary if last else None)
    if not base:
        return None
    if last and last.base_salary:
        ratio = base / last.base_salary
        allowances, taxes = round(last.allowances * ratio, 2), round(last.taxes * ratio, 2)
        deductions, other = last.deductions, last.other_deductions
    else:
        allowances, taxes = round(base * DEFAULT_ALLOWANCE_RATE, 2), round(base * DEFAULT_TAX_RATE, 2)
        deductions, other = 0, 0
    return {
        "staff_id": member.id, "base_salary": base, "allowances": allowances, "bonuses": 0,
        "deductions": deductions, "taxes": taxes, "other_deductions": other,
    }


def purge_unpaid_payslips(school_id, staff_id):
    """Take a former employee off every payroll run that has not been paid yet. Paid history is kept."""
    from app.models import Payslip, PayrollRun
    removed = 0
    for slip in Payslip.query.filter_by(school_id=school_id, staff_id=staff_id).all():
        run = PayrollRun.query.get(slip.payroll_run_id)
        if run and run.status != "paid":
            db.session.delete(slip)
            removed += 1
    return removed
