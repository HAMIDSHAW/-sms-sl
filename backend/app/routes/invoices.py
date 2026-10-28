from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Invoice, FeeStructure, Enrollment
from app.utils.tenancy import (
    current_school_id, permission_required, scoped_query,
    linked_student_id, resolve_guardian_selected_child,
)
from app.utils.notify import notify_guardians_of_student

bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")


def _next_invoice_number(school_id):
    count = Invoice.query.filter_by(school_id=school_id).count()
    return f"INV-{count + 1:06d}"


@bp.get("")
@permission_required("finance.view")
def list_invoices():
    """
    Admins/accountants see everything (filterable). Students/parents only
    ever see their own (or their children's) invoices, same self-scoping
    pattern used for assignments and results, so a student can't view a
    classmate's billing by changing a student_id in the URL.
    """
    query = scoped_query(Invoice)

    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()

    if student_id or child_id:
        query = query.filter(Invoice.student_id == (student_id or child_id))
    else:
        for field in ["student_id", "status"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Invoice, field) == value)
        class_id = request.args.get("class_id")
        if class_id:
            ids = [e.student_id for e in Enrollment.query.filter_by(class_id=class_id, status="active").all()]
            query = query.filter(Invoice.student_id.in_(ids or [""]))
        q = (request.args.get("q") or "").strip()
        if q:
            from app.models import Student
            like = f"%{q}%"
            matches = Student.query.filter(
                Student.school_id == current_school_id(),
                db.or_(Student.first_name.ilike(like), Student.last_name.ilike(like), Student.student_number.ilike(like)),
            ).all()
            query = query.filter(db.or_(
                Invoice.student_id.in_([m.id for m in matches] or [""]), Invoice.invoice_number.ilike(like),
                Invoice.description.ilike(like),
            ))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(Invoice.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [i.to_dict() for i in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.post("")
@permission_required("finance.manage")
def create_invoice():
    data = request.get_json(silent=True) or {}
    required = ["student_id", "description", "amount"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    from app.models import Student
    school_id = current_school_id()
    student = Student.query.filter_by(id=data["student_id"], school_id=school_id).first()
    if not student:
        return jsonify({"error": "student_id does not belong to this school"}), 404

    invoice = Invoice(
        school_id=school_id, invoice_number=_next_invoice_number(school_id),
        student_id=student.id, fee_structure_id=data.get("fee_structure_id"),
        description=data["description"], amount=data["amount"],
        due_date=datetime.strptime(data["due_date"], "%Y-%m-%d").date() if data.get("due_date") else None,
    )
    db.session.add(invoice)
    db.session.flush()
    notify_guardians_of_student(
        school_id, student.id, "invoice_created", f"New invoice: {invoice.description}",
        f"Le {invoice.amount:,.2f} due" + (f" by {invoice.due_date}" if invoice.due_date else ""),
        related_entity_type="invoice", related_entity_id=invoice.id,
    )
    db.session.commit()
    return jsonify(invoice.to_dict()), 201


@bp.post("/bill-class")
@permission_required("finance.manage")
def bill_class():
    """
    Bill every student in ANY class of the school in one action, without
    needing a saved fee structure first. Students who already have an
    invoice with the same description are skipped, so pressing the button
    twice never double bills anyone.
    """
    from app.models import SchoolClass
    data = request.get_json(silent=True) or {}
    class_id, description = data.get("class_id"), (data.get("description") or "").strip()
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "A numeric amount is required"}), 400
    if not class_id or not description or amount <= 0:
        return jsonify({"error": "class_id, description and a positive amount are required"}), 400

    school_id = current_school_id()
    school_class = SchoolClass.query.filter_by(id=class_id, school_id=school_id).first()
    if not school_class:
        return jsonify({"error": "class_id does not belong to this school"}), 404

    due = datetime.strptime(data["due_date"], "%Y-%m-%d").date() if data.get("due_date") else None
    created, skipped = 0, 0
    for e in Enrollment.query.filter_by(class_id=class_id, status="active").all():
        if Invoice.query.filter_by(school_id=school_id, student_id=e.student_id, description=description).first():
            skipped += 1
            continue
        invoice = Invoice(
            school_id=school_id, invoice_number=_next_invoice_number(school_id), student_id=e.student_id,
            description=description, amount=amount, due_date=due,
        )
        db.session.add(invoice)
        db.session.flush()
        notify_guardians_of_student(
            school_id, e.student_id, "invoice_created", f"New invoice: {description}",
            f"Le {amount:,.2f} due" + (f" by {due}" if due else ""),
            related_entity_type="invoice", related_entity_id=invoice.id,
        )
        created += 1
    db.session.commit()
    return jsonify({"class_name": school_class.name, "created": created, "skipped": skipped}), 201


@bp.patch("/<invoice_id>/cancel")
@permission_required("finance.manage")
def cancel_invoice(invoice_id):
    """
    Cancel an invoice (e.g. billed in error). Found missing during a gap
    audit, the model has always supported a 'cancelled' status but no
    route ever reached it. Refuses to cancel an invoice that already has
    successful payments against it, since that would silently orphan real
    money received, refund those payments first.
    """
    from app.models import Payment
    invoice = scoped_query(Invoice).filter_by(id=invoice_id).first_or_404()

    has_payments = Payment.query.filter_by(invoice_id=invoice.id, status="successful").first()
    if has_payments:
        return jsonify({"error": "Cannot cancel an invoice with successful payments, refund them first"}), 409

    invoice.status = "cancelled"
    db.session.commit()
    return jsonify(invoice.to_dict())


@bp.post("/generate-from-structure")
@permission_required("finance.manage")
def generate_from_structure():
    """
    Bulk-create one invoice per student currently enrolled in the fee
    structure's class (or every active student if the structure has no
    class restriction), this is how a school bills "everyone in JSS1
    Le 500,000 tuition" in one action instead of one invoice at a time.
    """
    data = request.get_json(silent=True) or {}
    structure_id = data.get("fee_structure_id")
    if not structure_id:
        return jsonify({"error": "fee_structure_id is required"}), 400

    structure = scoped_query(FeeStructure).filter_by(id=structure_id).first_or_404()
    school_id = current_school_id()

    if structure.class_id:
        enrollments = Enrollment.query.filter_by(
            class_id=structure.class_id, academic_year_id=structure.academic_year_id, status="active"
        ).all()
        student_ids = [e.student_id for e in enrollments]
    else:
        enrollments = Enrollment.query.filter_by(academic_year_id=structure.academic_year_id, status="active").all()
        student_ids = [e.student_id for e in enrollments]

    created = []
    for student_id in student_ids:
        existing = Invoice.query.filter_by(school_id=school_id, fee_structure_id=structure.id, student_id=student_id).first()
        if existing:
            continue
        invoice = Invoice(
            school_id=school_id, invoice_number=_next_invoice_number(school_id),
            student_id=student_id, fee_structure_id=structure.id,
            description=structure.name, amount=structure.amount, due_date=structure.due_date,
        )
        db.session.add(invoice)
        db.session.flush()
        notify_guardians_of_student(
            school_id, student_id, "invoice_created", f"New invoice: {invoice.description}",
            f"Le {invoice.amount:,.2f} due" + (f" by {invoice.due_date}" if invoice.due_date else ""),
            related_entity_type="invoice", related_entity_id=invoice.id,
        )
        created.append(invoice)

    db.session.commit()
    return jsonify({"created": len(created), "invoices": [i.to_dict() for i in created]}), 201
