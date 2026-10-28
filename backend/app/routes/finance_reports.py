from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Expense, Invoice, Payment
from app.utils.tenancy import (
    current_school_id, permission_required, any_permission_required, scoped_query,
    linked_student_id, linked_guardian_children_ids,
)
from app.utils.ledger import student_ledger

bp = Blueprint("finance_reports", __name__, url_prefix="/api/finance")


# --- Student ledger (spec section 51) --------------------------------------

@bp.get("/ledger/<student_id>")
@permission_required("finance.view")
def get_ledger(student_id):
    """
    Same self-scoping rule as invoices/payments/results: a student or
    guardian account can only ever pull their own (or their own child's)
    ledger, regardless of which student_id is in the URL.
    """
    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()
    if student_scope and student_id != student_scope:
        return jsonify({"error": "Not found"}), 404
    if guardian_children and student_id not in guardian_children:
        return jsonify({"error": "Not found"}), 404

    from app.models import Student, Enrollment, SchoolClass
    data = student_ledger(current_school_id(), student_id)
    student = Student.query.filter_by(id=student_id, school_id=current_school_id()).first_or_404()
    enrollment = Enrollment.query.filter_by(student_id=student_id, status="active").first()
    school_class = SchoolClass.query.get(enrollment.class_id) if enrollment else None
    data.update({
        "student_name": student.full_name, "student_number": student.student_number,
        "class_name": school_class.name if school_class else None,
    })
    return jsonify(data)


# --- Expenses (spec section 48) --------------------------------------------

@bp.get("/expenses")
@any_permission_required("finance.manage", "finance.expenses.manage")
def list_expenses():
    query = scoped_query(Expense)
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if start and end:
        query = query.filter(Expense.expense_date.between(
            datetime.strptime(start, "%Y-%m-%d").date(), datetime.strptime(end, "%Y-%m-%d").date()
        ))
    return jsonify([e.to_dict() for e in query.order_by(Expense.expense_date.desc()).all()])


@bp.post("/expenses")
@permission_required("finance.expenses.manage")
def create_expense():
    data = request.get_json(silent=True) or {}
    required = ["category", "amount", "expense_date"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    expense = Expense(
        school_id=current_school_id(), category=data["category"], description=data.get("description"),
        amount=data["amount"], expense_date=datetime.strptime(data["expense_date"], "%Y-%m-%d").date(),
        recorded_by_staff_id=data.get("recorded_by_staff_id"),
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify(expense.to_dict()), 201


# --- Financial analytics (spec section 112) --------------------------------

@bp.get("/summary")
@permission_required("finance.view")
def financial_summary():
    """
    finance.view is held by school-financial staff (accountant, principal,
    admin) *and* by students/parents (so they can see their own invoices
    and ledger), those are very different audiences for a "financial
    summary". A self-scoped caller (student or parent) gets their own
    billed/paid/outstanding numbers; anyone else holding finance.view at
    all is, by construction, staff, so they get the school-wide totals.
    """
    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()

    if student_scope or guardian_children:
        student_ids = [student_scope] if student_scope else guardian_children
        invoices = scoped_query(Invoice).filter(Invoice.student_id.in_(student_ids)).all()
        payments = (
            scoped_query(Payment).join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(Invoice.student_id.in_(student_ids), Payment.status == "successful").all()
        )
        total_billed = sum(i.amount for i in invoices)
        total_collected = sum(p.amount for p in payments)
        today = datetime.utcnow().date()
        overdue = sum(
            i.amount for i in invoices
            if i.due_date and i.due_date < today and i.status != "paid"
        )
        return jsonify({
            "total_billed": total_billed, "total_collected": total_collected,
            "outstanding": total_billed - total_collected, "overdue": overdue,
            "collection_rate": round((total_collected / total_billed) * 100, 1) if total_billed else None,
            "scope": "self",
        })

    # No additional finance.manage check here: finance.view itself is only
    # ever granted to accountant/principal/admin (oversight/operational
    # staff who should see the school-wide dashboard) or to students/
    # parents (who were already routed to the self-scoped branch above).
    # A principal legitimately has finance.view without finance.manage -
    # they can see the numbers without being the one who creates invoices
    #, and requiring finance.manage here would wrongly lock them out of
    # their own oversight view.
    school_id = current_school_id()
    invoices = scoped_query(Invoice).all()
    payments = scoped_query(Payment).filter_by(status="successful").all()
    expenses = scoped_query(Expense).all()

    total_billed = sum(i.amount for i in invoices)
    total_collected = sum(p.amount for p in payments)
    outstanding = total_billed - total_collected

    today = datetime.utcnow().date()
    overdue = sum(
        i.amount for i in invoices
        if i.due_date and i.due_date < today and i.status != "paid"
    )

    collection_rate = round((total_collected / total_billed) * 100, 1) if total_billed else None
    total_expenses = sum(e.amount for e in expenses)

    return jsonify({
        "total_billed": total_billed, "total_collected": total_collected,
        "outstanding": outstanding, "overdue": overdue, "collection_rate": collection_rate,
        "total_expenses": total_expenses, "net": total_collected - total_expenses, "scope": "school",
    })
