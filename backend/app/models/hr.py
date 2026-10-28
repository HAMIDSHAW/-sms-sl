from datetime import datetime, timezone

from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

LEAVE_STATUSES = ["pending", "approved", "rejected", "cancelled"]
PAYROLL_STATUSES = ["draft", "processed", "paid"]


class LeaveRequest(db.Model, TimestampMixin):
    __tablename__ = "leave_requests"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False, default="annual")  # annual, sick, maternity, paternity, unpaid
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(500), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending")
    reviewed_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    review_note = db.Column(db.String(500), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        from app.models import Staff
        staff = Staff.query.get(self.staff_id)
        reviewer = Staff.query.get(self.reviewed_by_staff_id) if self.reviewed_by_staff_id else None
        return {
            "id": self.id, "staff_id": self.staff_id, "leave_type": self.leave_type,
            "start_date": self.start_date.isoformat(), "end_date": self.end_date.isoformat(),
            "reason": self.reason, "status": self.status, "review_note": self.review_note,
            "reviewed_by_staff_id": self.reviewed_by_staff_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "staff_name": staff.full_name if staff else None,
            "staff_photo_url": staff.photo_url if staff else None,
            "staff_position": staff.position if staff else None,
            "reviewed_by_name": reviewer.full_name if reviewer else None,
        }


class PayrollRun(db.Model, TimestampMixin):
    """One payroll cycle (e.g. 'January 2027') covering every active staff member (spec section 68)."""

    __tablename__ = "payroll_runs"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    period_label = db.Column(db.String(50), nullable=False)  # "January 2027"
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    processed_at = db.Column(db.DateTime, nullable=True)

    def payable_slips(self):
        """Payslips that count toward this run. Until it is paid, anyone who has left is ignored."""
        from app.models import Staff
        from app.utils.payroll import is_payable
        slips = Payslip.query.filter_by(payroll_run_id=self.id).all()
        if self.status == "paid":
            return slips
        return [s for s in slips if is_payable(Staff.query.get(s.staff_id))]

    def to_dict(self):
        slips = self.payable_slips()
        return {
            "id": self.id, "period_label": self.period_label,
            "period_start": self.period_start.isoformat(), "period_end": self.period_end.isoformat(),
            "status": self.status, "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "payslip_count": len(slips), "total_net": sum(p.net_salary for p in slips),
        }


class Payslip(db.Model, TimestampMixin):
    """One staff member's pay breakdown within a PayrollRun (spec section 68)."""

    __tablename__ = "payslips"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    payroll_run_id = db.Column(db.String(36), db.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)

    base_salary = db.Column(db.Float, nullable=False, default=0)
    allowances = db.Column(db.Float, nullable=False, default=0)
    bonuses = db.Column(db.Float, nullable=False, default=0)
    deductions = db.Column(db.Float, nullable=False, default=0)
    taxes = db.Column(db.Float, nullable=False, default=0)
    other_deductions = db.Column(db.Float, nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default="draft")  # draft, processed, paid

    __table_args__ = (
        db.UniqueConstraint("payroll_run_id", "staff_id", name="uq_payslip_run_staff"),
    )

    @property
    def net_salary(self):
        return self.base_salary + self.allowances + self.bonuses - self.deductions - self.taxes - self.other_deductions

    def to_dict(self):
        from app.models import Staff
        staff = Staff.query.get(self.staff_id)
        return {
            "id": self.id, "payroll_run_id": self.payroll_run_id, "staff_id": self.staff_id,
            "base_salary": self.base_salary, "allowances": self.allowances, "bonuses": self.bonuses,
            "deductions": self.deductions, "taxes": self.taxes, "other_deductions": self.other_deductions,
            "net_salary": self.net_salary, "status": self.status,
            "staff_name": staff.full_name if staff else None,
            "staff_photo_url": staff.photo_url if staff else None,
            "staff_position": staff.position if staff else None,
        }
