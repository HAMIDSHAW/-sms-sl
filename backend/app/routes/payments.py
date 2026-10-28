from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Payment, Invoice
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, scoped_query,
    linked_student_id, linked_staff_id, linked_guardian_children_ids, resolve_guardian_selected_child,
)
from app.utils.ledger import recompute_invoice_status
from app.utils.audit import record_audit

bp = Blueprint("payments", __name__, url_prefix="/api/payments")


def _next_receipt_number(school_id):
    count = Payment.query.filter_by(school_id=school_id).count()
    return f"RCT-{count + 1:06d}"


@bp.get("")
@permission_required("finance.view")
def list_payments():
    query = scoped_query(Payment)
    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()

    if student_id or child_id:
        query = query.filter(Payment.student_id == (student_id or child_id))
    else:
        for field in ["student_id", "invoice_id", "status"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Payment, field) == value)

    if not (student_id or child_id):
        q = (request.args.get("q") or "").strip()
        if q:
            from app.models import Student
            like = f"%{q}%"
            matches = Student.query.filter(
                Student.school_id == current_school_id(),
                db.or_(Student.first_name.ilike(like), Student.last_name.ilike(like), Student.student_number.ilike(like)),
            ).all()
            query = query.filter(db.or_(
                Payment.student_id.in_([m.id for m in matches] or [""]), Payment.payer_name.ilike(like),
                Payment.receipt_number.ilike(like), Payment.reference.ilike(like),
            ))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    pagination = query.order_by(Payment.paid_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [p.to_dict() for p in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.post("")
@permission_required("finance.payment.create")
def record_payment():
    """
    Record a payment against an invoice (spec section 52-53). The
    student's outstanding balance updates implicitly, recomputed from
    invoices+payments (see app/utils/ledger.py), never written directly -
    and only ever after a payment lands in "successful" status (spec
    section 51: "must only update after a verified successful payment").
    """
    data = request.get_json(silent=True) or {}
    # Payments are recorded by school staff who actually received the money. A student or parent
    # account must never be able to mark its own fees as paid, whatever permissions it holds.
    if linked_student_id() or linked_guardian_children_ids():
        from app.utils.security import log_security_event
        log_security_event("payment_blocked_for_family_account", user_id=current_user().id)
        return jsonify({"error": "Payments are recorded by the school's accountant"}), 403
    required = ["invoice_id", "amount"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    invoice = scoped_query(Invoice).filter_by(id=data["invoice_id"]).first_or_404()
    school_id = current_school_id()
    status = data.get("status", "successful")

    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be greater than zero"}), 400
    if invoice.status == "cancelled":
        return jsonify({"error": "This invoice was cancelled"}), 409
    already_paid = sum(
        p.amount for p in Payment.query.filter_by(invoice_id=invoice.id, status="successful").all()
    )
    if status == "successful" and amount > invoice.amount - already_paid + 0.001:
        return jsonify({"error": f"That is more than the balance of Le {invoice.amount - already_paid:,.2f}"}), 409

    payment = Payment(
        school_id=school_id, invoice_id=invoice.id, student_id=invoice.student_id,
        amount=amount, payment_method=data.get("payment_method", "cash"),
        reference=data.get("reference"), received_by_staff_id=linked_staff_id() or data.get("received_by_staff_id"),
        payer_name=(data.get("payer_name") or "").strip() or None,
        payer_phone=(data.get("payer_phone") or "").strip() or None,
        payer_relationship=data.get("payer_relationship"),
        notes=data.get("notes"), status=status,
        receipt_number=_next_receipt_number(school_id) if status == "successful" else None,
    )
    db.session.add(payment)
    db.session.flush()

    if status == "successful":
        recompute_invoice_status(invoice)

    db.session.commit()
    record_audit(
        "payment.record", "finance", "payment", payment.id,
        after={"summary": f"Recorded a payment of Le {amount:,.0f} for {invoice.description}", "invoice_id": invoice.id, "amount": amount, "status": status, "payer": data.get("payer_name")},
    )

    from app.utils.notify import notify_guardians_of_student
    notify_guardians_of_student(
        school_id, invoice.student_id,
        "payment_successful" if status == "successful" else "payment_failed",
        f"Payment {'received' if status == 'successful' else 'failed'}: {invoice.description}",
        f"Le {amount:,.0f}", related_entity_type="payment", related_entity_id=payment.id,
    )
    db.session.commit()

    return jsonify(payment.to_dict()), 201


@bp.patch("/<payment_id>/refund")
@permission_required("finance.refund")
def refund_payment(payment_id):
    """Mark a payment refunded and re-derive the invoice's status accordingly."""
    payment = scoped_query(Payment).filter_by(id=payment_id).first_or_404()
    data = request.get_json(silent=True) or {}
    is_partial = data.get("partial", False)

    payment.status = "partially_refunded" if is_partial else "refunded"
    if not is_partial:
        payment.amount = 0  # fully refunded payments no longer count toward the invoice's paid total

    invoice = scoped_query(Invoice).filter_by(id=payment.invoice_id).first()
    if invoice:
        recompute_invoice_status(invoice)

    db.session.commit()
    record_audit("payment.refund", "finance", "payment", payment_id, after={"partial": is_partial})
    db.session.commit()
    return jsonify(payment.to_dict())


@bp.get("/<payment_id>/receipt")
@permission_required("finance.view")
def get_receipt(payment_id):
    """
    Structured receipt data (spec section 54), school details, student,
    invoice, amount, method, reference, date, receipt number. Same pattern
    as the report card endpoint: JSON now, a printable/PDF layout is a
    frontend (or later PDF-generation) concern.
    """
    from app.models import School, Student

    payment = scoped_query(Payment).filter_by(id=payment_id).first_or_404()
    if payment.status != "successful":
        return jsonify({"error": "Receipts are only available for successful payments"}), 404

    invoice = scoped_query(Invoice).filter_by(id=payment.invoice_id).first_or_404()
    student = scoped_query(Student).filter_by(id=payment.student_id).first_or_404()
    school = School.query.get(current_school_id())

    return jsonify({
        "receipt_number": payment.receipt_number,
        "school": {"name": school.name, "address": school.address, "logo_url": school.logo_url},
        "student": {"full_name": student.full_name, "student_number": student.student_number},
        "invoice": {"invoice_number": invoice.invoice_number, "description": invoice.description},
        "paid_by": {"name": payment.payer_name, "phone": payment.payer_phone, "relationship": payment.payer_relationship},
        "amount": payment.amount, "payment_method": payment.payment_method,
        "reference": payment.reference, "paid_at": payment.paid_at.isoformat(),
    })
