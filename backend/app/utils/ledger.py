"""
A student's financial position is always DERIVED from Invoice + Payment
rows, never stored as a separate running balance, that's the rule from
spec section 51: "the financial account must only update after a verified
successful payment," and the only way to guarantee that is to compute it
fresh from the underlying transactions every time, not maintain a
duplicate number that could drift.
"""

from app.models import Invoice, Payment


def student_ledger(school_id, student_id):
    invoices = Invoice.query.filter_by(school_id=school_id, student_id=student_id).all()
    payments = Payment.query.filter_by(school_id=school_id, student_id=student_id, status="successful").all()

    total_billed = sum(i.amount for i in invoices)
    total_paid = sum(p.amount for p in payments)
    balance = total_billed - total_paid

    return {
        "student_id": student_id,
        "total_billed": total_billed,
        "total_paid": total_paid,
        "balance": balance,
        "invoices": [i.to_dict() for i in invoices],
        "payments": [p.to_dict() for p in payments],
    }


def recompute_invoice_status(invoice):
    """Called after any payment against this invoice, derives unpaid/partially_paid/paid from actual payments."""
    paid = sum(p.amount for p in Payment.query.filter_by(invoice_id=invoice.id, status="successful").all())
    if paid <= 0:
        invoice.status = "unpaid"
    elif paid < invoice.amount:
        invoice.status = "partially_paid"
    else:
        invoice.status = "paid"
