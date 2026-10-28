from datetime import date, datetime

from flask import Blueprint, jsonify

from app.extensions import db
from app.models import (
    Assignment, AssignmentSubmission, BorrowRecord, DisciplinaryRecord, Enrollment, Invoice, InventoryItem,
    LeaveRequest, Message, PayrollRun, Payment, Result,
)
from app.utils.tenancy import (
    current_school_id, current_user, jwt_required_scoped, scoped_query, has_permission,
    linked_student_id, linked_staff_id, resolve_guardian_selected_child,
)

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _item(key, label, count, link, tone="info"):
    return {"key": key, "label": label, "count": count, "link": link, "tone": tone}


@bp.get("/summary")
@jwt_required_scoped
def summary():
    """
    What genuinely needs this person's attention right now, worked out on the
    server from live data and from what their role is allowed to act on. Nothing
    here is a fixed number, and a role is never shown items it cannot act on.
    """
    school_id = current_school_id()
    user = current_user()
    today = date.today()
    items = []

    unread = Message.query.filter_by(recipient_user_id=user.id, read_at=None).count()
    if unread:
        items.append(_item("messages", f"{unread} unread message{'s' if unread != 1 else ''}", unread, "/messages"))

    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()
    subject_student = student_id or child_id

    if subject_student:
        enrollment = Enrollment.query.filter_by(student_id=subject_student, status="active").first()
        if enrollment:
            open_work = []
            for a in scoped_query(Assignment).filter_by(class_id=enrollment.class_id, status="published").all():
                sub = AssignmentSubmission.query.filter_by(assignment_id=a.id, student_id=subject_student).first()
                if not sub:
                    open_work.append(a)
            overdue = [a for a in open_work if a.due_date and a.due_date < today]
            pending = [a for a in open_work if not a.due_date or a.due_date >= today]
            if pending:
                items.append(_item("assignments_due", f"{len(pending)} assignment{'s' if len(pending) != 1 else ''} not handed in yet", len(pending), "/assignments", "warn"))
            if overdue:
                items.append(_item("assignments_overdue", f"{len(overdue)} overdue assignment{'s' if len(overdue) != 1 else ''}", len(overdue), "/assignments", "danger"))
        balance = 0.0
        for inv in scoped_query(Invoice).filter(Invoice.student_id == subject_student, Invoice.status != "cancelled").all():
            paid = sum(p.amount for p in Payment.query.filter_by(invoice_id=inv.id, status="successful").all())
            balance += max(inv.amount - paid, 0)
        if balance > 0:
            items.append(_item("fees_due", f"Le {balance:,.0f} in fees outstanding", balance, "/finance", "warn"))
        return jsonify({"scope": "student", "student_id": subject_student, "items": items})

    if has_permission("hr.leave.approve"):
        n = scoped_query(LeaveRequest).filter_by(status="pending").count()
        if n:
            items.append(_item("leave_pending", f"{n} leave request{'s' if n != 1 else ''} waiting for a decision", n, "/hr", "warn"))
    if has_permission("hr.payroll.manage"):
        n = scoped_query(PayrollRun).filter(PayrollRun.status != "paid").count()
        if n:
            items.append(_item("payroll_open", f"{n} payroll run{'s' if n != 1 else ''} not marked paid", n, "/hr"))
    if has_permission("finance.manage") or has_permission("finance.payment.create"):
        overdue = 0
        for inv in scoped_query(Invoice).filter(Invoice.status.in_(["unpaid", "partially_paid"])).all():
            if inv.due_date and inv.due_date < today:
                overdue += 1
        if overdue:
            items.append(_item("invoices_overdue", f"{overdue} overdue invoice{'s' if overdue != 1 else ''}", overdue, "/finance", "danger"))
    for code, status, label, link in [
        ("results.review", "teacher_submitted", "result sheet{s} waiting for exam office review", "/exams"),
        ("results.approve", "exam_officer_review", "result sheet{s} waiting for your approval", "/exams"),
        ("results.publish", "principal_approved", "approved result sheet{s} ready to publish", "/exams"),
    ]:
        if has_permission(code):
            n = scoped_query(Result).filter_by(status=status).count()
            if n:
                items.append(_item(f"results_{status}", f"{n} " + label.replace("{s}", "s" if n != 1 else ""), n, link, "warn"))
    if has_permission("discipline.resolve"):
        n = scoped_query(DisciplinaryRecord).filter(DisciplinaryRecord.status != "resolved").count()
        if n:
            items.append(_item("discipline_open", f"{n} open discipline case{'s' if n != 1 else ''}", n, "/discipline", "warn"))
    if has_permission("library.manage"):
        n = scoped_query(BorrowRecord).filter(BorrowRecord.status == "borrowed", BorrowRecord.due_date < today).count()
        if n:
            items.append(_item("library_overdue", f"{n} overdue library loan{'s' if n != 1 else ''}", n, "/library", "danger"))
    if has_permission("inventory.manage"):
        n = scoped_query(InventoryItem).filter_by(status="under_maintenance", is_active=True).count()
        if n:
            items.append(_item("maintenance", f"{n} item{'s' if n != 1 else ''} under maintenance", n, "/inventory"))
    my_staff = linked_staff_id()
    if my_staff and has_permission("assignments.grade"):
        mine = [a.id for a in scoped_query(Assignment).filter_by(staff_id=my_staff).all()]
        n = AssignmentSubmission.query.filter(
            AssignmentSubmission.assignment_id.in_(mine or [""]), AssignmentSubmission.status.in_(["submitted", "late"])
        ).count()
        if n:
            items.append(_item("to_grade", f"{n} submission{'s' if n != 1 else ''} waiting to be graded", n, "/assignments", "warn"))

    return jsonify({"scope": "staff", "items": items})
