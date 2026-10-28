from datetime import date, timedelta

from app.extensions import db
from app.models.base import gen_uuid, TimestampMixin

BORROW_STATUSES = ["borrowed", "returned", "overdue", "lost"]
DEFAULT_LOAN_DAYS = 14
DEFAULT_DAILY_FINE = 500  # Le, school-configurable via Book.daily_fine_override or a future settings field


class Book(db.Model, TimestampMixin):
    __tablename__ = "books"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    isbn = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(120), nullable=True)

    total_copies = db.Column(db.Integer, nullable=False, default=1)
    available_copies = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Optional per-book rules, set when the book is added. Empty means "use the
    # school-wide default set by the principal" (see School.library_*).
    loan_days = db.Column(db.Integer, nullable=True)
    daily_fine = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "author": self.author, "publisher": self.publisher,
            "isbn": self.isbn, "category": self.category,
            "total_copies": self.total_copies, "available_copies": self.available_copies,
            "is_active": self.is_active,
            "loan_days": self.loan_days, "daily_fine": self.daily_fine,
        }


class BorrowRecord(db.Model, TimestampMixin):
    """
    A single loan of one copy of a book (spec section 61: Borrowing,
    Returns, Overdue, Fines). Borrower is either a student or a staff
    member, never both, matching the two kinds of library member the
    spec allows.
    """

    __tablename__ = "borrow_records"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    school_id = db.Column(db.String(36), db.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)

    book_id = db.Column(db.String(36), db.ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey("students.id", ondelete="CASCADE"), nullable=True)
    staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=True)

    borrowed_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    returned_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="borrowed")
    fine_amount = db.Column(db.Float, nullable=False, default=0)
    # The per-day rate that applied when the book was lent, so a later change to the
    # school/book rate never changes what an existing loan owes.
    daily_fine_rate = db.Column(db.Float, nullable=True)
    # What the system worked out at return time, kept next to fine_amount (what was
    # actually charged) so an adjustment or waiver is always traceable.
    fine_calculated = db.Column(db.Float, nullable=True)
    fine_note = db.Column(db.String(255), nullable=True)
    issued_by_staff_id = db.Column(db.String(36), db.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)

    def to_dict(self):
        from app.models import Student, Staff, Book
        borrower = Student.query.get(self.student_id) if self.student_id else Staff.query.get(self.staff_id)
        book = Book.query.get(self.book_id)
        rate = self.daily_fine_rate if self.daily_fine_rate is not None else DEFAULT_DAILY_FINE
        days_overdue = max(0, (date.today() - self.due_date).days) if self.status == "borrowed" else 0
        return {
            "id": self.id, "book_id": self.book_id, "student_id": self.student_id, "staff_id": self.staff_id,
            "borrowed_date": self.borrowed_date.isoformat(), "due_date": self.due_date.isoformat(),
            "returned_date": self.returned_date.isoformat() if self.returned_date else None,
            "status": self.status, "fine_amount": self.fine_amount,
            "daily_fine_rate": rate, "fine_calculated": self.fine_calculated, "fine_note": self.fine_note,
            "days_overdue": days_overdue, "fine_due": days_overdue * rate if self.status == "borrowed" else 0,
            "book_title": book.title if book else None,
            "borrower_name": (borrower.full_name if hasattr(borrower, "full_name") else f"{borrower.first_name} {borrower.last_name}") if borrower else None,
            "borrower_photo_url": borrower.photo_url if borrower else None,
        }
