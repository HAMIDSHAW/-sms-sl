from datetime import datetime, timezone

from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

PAYMENT_METHODS = ["cash", "bank_transfer", "mobile_money", "card", "online_gateway"]
PAYMENT_STATUSES = ["pending", "successful", "failed", "cancelled", "refunded", "partially_refunded"]


class FeeCategory(db.Model, TimestampMixin):
    """e.g. Tuition, Registration, Examination, Transport (spec section 50). School-defined, not a fixed enum."""

    __tablename__ = "fee_categories"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (db.UniqueConstraint("school_id", "name", name="uq_fee_category_school_name"),)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description, "is_active": self.is_active}


class FeeStructure(db.Model, TimestampMixin):
    """A charge template for a class/term (spec section 49), e.g. 'JSS1 Tuition, First Term, Le 500,000'."""

    __tablename__ = "fee_structures"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    name = db.Column(db.String(255), nullable=False)
    academic_year_id = db.Column(db.String(36), db.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False)
    term_id = db.Column(db.String(36), db.ForeignKey("terms.id", ondelete="SET NULL"), nullable=True)
    class_id = db.Column(db.String(36), db.ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    fee_category_id = db.Column(db.String(36), db.ForeignKey("fee_categories.id", ondelete="CASCADE"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    late_fee = db.Column(db.Float, nullable=False, default=0)
    is_mandatory = db.Column(db.Boolean, nullable=False, default=True)

    school_class = db.relationship("SchoolClass", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "academic_year_id": self.academic_year_id,
            "term_id": self.term_id, "class_id": self.class_id,
            "class_name": self.school_class.name if self.school_class else None,
            "fee_category_id": self.fee_category_id,
            "amount": self.amount, "due_date": self.due_date.isoformat() if self.due_date else None,
            "late_fee": self.late_fee, "is_mandatory": self.is_mandatory,
        }


class Invoice(db.Model, TimestampMixin):
    """
    One billed charge against a student, generated from a FeeStructure
    (spec section 51-52). A student's outstanding balance is always
    derived from their invoices + payments, never hand-tracked as a
    separate number that could drift out of sync.
    """

    __tablename__ = "invoices"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    invoice_number = db.Column(db.String(50), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    fee_structure_id = db.Column(db.String(36), db.ForeignKey("fee_structures.id", ondelete="SET NULL"), nullable=True)

    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="unpaid")  # unpaid, partially_paid, paid, cancelled

    __table_args__ = (db.UniqueConstraint("school_id", "invoice_number", name="uq_invoice_school_number"),)

    def to_dict(self):
        from app.models import Student, Enrollment, SchoolClass
        student = Student.query.get(self.student_id)
        enrollment = Enrollment.query.filter_by(student_id=self.student_id, status="active").first()
        school_class = SchoolClass.query.get(enrollment.class_id) if enrollment else None
        paid = sum(
            p.amount for p in Payment.query.filter_by(invoice_id=self.id, status="successful").all()
        )
        return {
            "id": self.id, "invoice_number": self.invoice_number, "student_id": self.student_id,
            "fee_structure_id": self.fee_structure_id, "description": self.description,
            "amount": self.amount, "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "student_name": student.full_name if student else None,
            "student_number": student.student_number if student else None,
            "class_name": school_class.name if school_class else None,
            "paid_amount": paid, "balance": max(self.amount - paid, 0),
        }


class Payment(db.Model, TimestampMixin):
    """One payment transaction against an invoice (spec section 52-53)."""

    __tablename__ = "payments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    invoice_id = db.Column(db.String(36), db.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), nullable=False, default="cash")
    reference = db.Column(db.String(120), nullable=True)
    received_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="successful")

    receipt_number = db.Column(db.String(50), nullable=True)
    paid_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Who actually handed over the money (a parent, the student, a relative...)
    payer_name = db.Column(db.String(160), nullable=True)
    payer_phone = db.Column(db.String(50), nullable=True)
    payer_relationship = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        from app.models import Student, Staff
        invoice = Invoice.query.get(self.invoice_id)
        student = Student.query.get(self.student_id)
        receiver = Staff.query.get(self.received_by_staff_id) if self.received_by_staff_id else None
        return {
            "id": self.id, "invoice_id": self.invoice_id, "student_id": self.student_id,
            "amount": self.amount, "payment_method": self.payment_method, "reference": self.reference,
            "notes": self.notes, "status": self.status, "receipt_number": self.receipt_number,
            "paid_at": self.paid_at.isoformat(),
            "payer_name": self.payer_name, "payer_phone": self.payer_phone,
            "payer_relationship": self.payer_relationship,
            "paid_for": invoice.description if invoice else None,
            "invoice_number": invoice.invoice_number if invoice else None,
            "student_name": student.full_name if student else None,
            "student_number": student.student_number if student else None,
            "received_by_name": receiver.full_name if receiver else None,
        }


class Expense(db.Model, TimestampMixin):
    """A school outgoing cost, separate from student billing (spec section 48, "Expenses")."""

    __tablename__ = "expenses"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    recorded_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "category": self.category, "description": self.description,
            "amount": self.amount, "expense_date": self.expense_date.isoformat(),
        }
