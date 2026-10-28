import math
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Book, BorrowRecord, Student, Staff, School, DEFAULT_LOAN_DAYS, DEFAULT_DAILY_FINE
from app.utils.audit import record_audit
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, scoped_query, has_permission,
    linked_student_id, linked_guardian_children_ids,
)

bp = Blueprint("library", __name__, url_prefix="/api/library")

MAX_LOAN_DAYS = 365


def _caller_staff():
    user = current_user()
    return Staff.query.filter_by(user_id=user.id, school_id=current_school_id()).first()


def _school_policy():
    """(loan days, daily fine) the school applies when a book has no rule of its own."""
    school = School.query.get(current_school_id())
    days = school.library_loan_days if school and school.library_loan_days else DEFAULT_LOAN_DAYS
    fine = school.library_daily_fine if school and school.library_daily_fine is not None else DEFAULT_DAILY_FINE
    return days, fine


def _whole_days(value, label="loan period"):
    """Parse a loan length in days. Returns (days, error)."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None, f"The {label} must be a whole number of days"
    if days < 1 or days > MAX_LOAN_DAYS:
        return None, f"The {label} must be between 1 and {MAX_LOAN_DAYS} days"
    return days, None


def _money(value, label="fine"):
    """Parse a Leone amount (>= 0). Returns (amount, error)."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None, f"The {label} must be a number"
    if not math.isfinite(amount) or amount < 0:
        return None, f"The {label} cannot be negative"
    return amount, None


def _book_rules(data):
    """Optional per-book loan_days / daily_fine. Blank or null clears the rule. Returns (rules, error)."""
    rules = {}
    if "loan_days" in data:
        if data["loan_days"] in (None, ""):
            rules["loan_days"] = None
        else:
            days, err = _whole_days(data["loan_days"], "loan period for this book")
            if err:
                return None, err
            rules["loan_days"] = days
    if "daily_fine" in data:
        if data["daily_fine"] in (None, ""):
            rules["daily_fine"] = None
        else:
            amount, err = _money(data["daily_fine"], "daily fine for this book")
            if err:
                return None, err
            rules["daily_fine"] = amount
    return rules, None


# --- Library policy (set by the principal) ----------------------------------

@bp.get("/policy")
@permission_required("library.view")
def get_policy():
    days, fine = _school_policy()
    return jsonify({
        "loan_days": days, "daily_fine": fine,
        "can_edit": has_permission("library.policy"),
    })


@bp.patch("/policy")
@permission_required("library.policy")
def update_policy():
    """The principal sets the school-wide loan period and the fine per overdue day. A book can still override both."""
    data = request.get_json(silent=True) or {}
    school = School.query.get_or_404(current_school_id())
    before = {"loan_days": school.library_loan_days, "daily_fine": school.library_daily_fine}
    if "loan_days" in data:
        days, err = _whole_days(data["loan_days"], "standard loan period")
        if err:
            return jsonify({"error": err}), 400
        school.library_loan_days = days
    if "daily_fine" in data:
        amount, err = _money(data["daily_fine"], "fine per day")
        if err:
            return jsonify({"error": err}), 400
        school.library_daily_fine = amount
    record_audit("library.policy.update", "library", "school", school.id, before=before,
                 after={"loan_days": school.library_loan_days, "daily_fine": school.library_daily_fine})
    db.session.commit()
    days, fine = _school_policy()
    return jsonify({"loan_days": days, "daily_fine": fine, "can_edit": True})


# --- Books (spec section 61: catalog) --------------------------------------

@bp.get("/books")
@permission_required("library.view")
def list_books():
    query = scoped_query(Book).filter_by(is_active=True)
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Book.title.ilike(like), Book.author.ilike(like)))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 25)), 200)
    category = request.args.get("category")
    if category:
        query = query.filter(Book.category == category)
    order = Book.created_at.desc() if request.args.get("sort") == "recent" else Book.title
    pagination = query.order_by(order).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [b.to_dict() for b in pagination.items],
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
    })


@bp.post("/books")
@permission_required("library.manage")
def create_book():
    data = request.get_json(silent=True) or {}
    if not str(data.get("title") or "").strip():
        return jsonify({"error": "title is required"}), 400
    try:
        copies = int(data.get("total_copies", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "total_copies must be a whole number"}), 400
    if copies < 0:
        return jsonify({"error": "total_copies cannot be negative"}), 400
    rules, err = _book_rules(data)
    if err:
        return jsonify({"error": err}), 400

    book = Book(
        school_id=current_school_id(), title=data["title"].strip(), author=data.get("author"),
        publisher=data.get("publisher"), isbn=data.get("isbn"), category=data.get("category"),
        total_copies=copies, available_copies=copies, **rules,
    )
    db.session.add(book)
    db.session.commit()
    return jsonify(book.to_dict()), 201


@bp.patch("/books/<book_id>")
@permission_required("library.manage")
def update_book(book_id):
    book = scoped_query(Book).filter_by(id=book_id).first_or_404()
    data = request.get_json(silent=True) or {}
    for field in ["title", "author", "publisher", "isbn", "category", "is_active"]:
        if field in data:
            setattr(book, field, data[field])
    rules, err = _book_rules(data)
    if err:
        return jsonify({"error": err}), 400
    for field, value in rules.items():
        setattr(book, field, value)
    if "total_copies" in data:
        # Adjust available_copies by the same delta so currently-borrowed
        # copies aren't silently lost from the count.
        try:
            new_total = int(data["total_copies"])
        except (TypeError, ValueError):
            return jsonify({"error": "total_copies must be a whole number"}), 400
        if new_total < 0:
            return jsonify({"error": "total_copies cannot be negative"}), 400
        delta = new_total - book.total_copies
        book.total_copies = new_total
        book.available_copies = max(0, min(new_total, book.available_copies + delta))
    if "available_copies" in data:
        # Direct correction (a copy was lost, damaged or found). Never above the total.
        try:
            available = int(data["available_copies"])
        except (TypeError, ValueError):
            return jsonify({"error": "available_copies must be a whole number"}), 400
        if available < 0 or available > book.total_copies:
            return jsonify({"error": f"available_copies must be between 0 and {book.total_copies}"}), 400
        book.available_copies = available
    db.session.commit()
    return jsonify(book.to_dict())


@bp.delete("/books/<book_id>")
@permission_required("library.manage")
def delete_book(book_id):
    """Remove a book from the catalog. Hidden rather than erased so old loan records still make sense."""
    book = scoped_query(Book).filter_by(id=book_id).first_or_404()
    open_loans = BorrowRecord.query.filter_by(book_id=book.id, status="borrowed").count()
    if open_loans:
        return jsonify({"error": f"{open_loans} cop{'y is' if open_loans == 1 else 'ies are'} still out on loan. Return them first."}), 409
    book.is_active = False
    db.session.commit()
    return jsonify({"message": "Book removed from the catalog"})


# --- Circulation: borrow / return (spec section 61) ------------------------

@bp.get("/borrow-records")
@permission_required("library.view")
def list_borrow_records():
    """Librarians see everything (filterable). A student/guardian sees only their own (or their child's) borrow history."""
    query = scoped_query(BorrowRecord)
    user = current_user()

    student_scope = linked_student_id()
    guardian_children = linked_guardian_children_ids()

    if user.has_permission("library.manage"):
        for field in ["book_id", "student_id", "staff_id", "status"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(BorrowRecord, field) == value)
    elif student_scope:
        query = query.filter(BorrowRecord.student_id == student_scope)
    elif guardian_children:
        query = query.filter(BorrowRecord.student_id.in_(guardian_children))
    else:
        caller_staff = _caller_staff()
        if not caller_staff:
            return jsonify([])
        query = query.filter(BorrowRecord.staff_id == caller_staff.id)

    return jsonify([r.to_dict() for r in query.order_by(BorrowRecord.borrowed_date.desc()).all()])


@bp.post("/borrow")
@permission_required("library.circulation")
def borrow_book():
    """
    Issue a copy of a book to a student or staff member. Validates both
    the book and the borrower belong to this school (same cross-tenant FK
    check pattern established in the gap-fix audit), and refuses if no
    copies are currently available.
    """
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    student_id = data.get("student_id")
    staff_id = data.get("staff_id")

    if not book_id or (not student_id and not staff_id) or (student_id and staff_id):
        return jsonify({"error": "book_id and exactly one of student_id/staff_id are required"}), 400

    school_id = current_school_id()
    book = Book.query.filter_by(id=book_id, school_id=school_id).first()
    if not book:
        return jsonify({"error": "book_id does not belong to this school"}), 404
    if book.available_copies < 1:
        return jsonify({"error": "No copies of this book are currently available"}), 409

    if student_id and not Student.query.filter_by(id=student_id, school_id=school_id).first():
        return jsonify({"error": "student_id does not belong to this school"}), 404
    if staff_id and not Staff.query.filter_by(id=staff_id, school_id=school_id).first():
        return jsonify({"error": "staff_id does not belong to this school"}), 404

    # How long: an explicit due date or number of days from whoever is lending, otherwise
    # this book's own rule, otherwise the principal's school-wide default.
    school_days, school_fine = _school_policy()
    today = date.today()
    if data.get("due_date"):
        try:
            due = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return jsonify({"error": "due_date must look like 2027-01-31"}), 400
        if due <= today:
            return jsonify({"error": "The due date must be after today"}), 400
        if (due - today).days > MAX_LOAN_DAYS:
            return jsonify({"error": f"A loan cannot be longer than {MAX_LOAN_DAYS} days"}), 400
    else:
        if data.get("loan_days") not in (None, ""):
            days, err = _whole_days(data["loan_days"])
            if err:
                return jsonify({"error": err}), 400
        else:
            days = book.loan_days or school_days
        due = today + timedelta(days=days)

    record = BorrowRecord(
        school_id=school_id, book_id=book.id, student_id=student_id, staff_id=staff_id,
        borrowed_date=today, due_date=due,
        daily_fine_rate=book.daily_fine if book.daily_fine is not None else school_fine,
        issued_by_staff_id=_caller_staff().id if _caller_staff() else None,
    )
    book.available_copies -= 1
    db.session.add(record)
    db.session.commit()
    return jsonify(record.to_dict()), 201


@bp.post("/borrow-records/<record_id>/return")
@permission_required("library.circulation")
def return_book(record_id):
    """
    Take a copy back and restock it. If it is late, the fine is worked out automatically
    (days late x the rate that applied when it was lent). A librarian or admin (library.manage)
    may instead set the amount charged, including 0 to waive it, but must say why.
    """
    record = scoped_query(BorrowRecord).filter_by(id=record_id).first_or_404()
    if record.status == "returned":
        return jsonify({"error": "This copy has already been returned"}), 409
    data = request.get_json(silent=True) or {}

    today = date.today()
    rate = record.daily_fine_rate if record.daily_fine_rate is not None else DEFAULT_DAILY_FINE
    days_late = max(0, (today - record.due_date).days)
    calculated = days_late * rate

    charged, note = calculated, None
    if data.get("fine_amount") not in (None, ""):
        if not has_permission("library.manage"):
            return jsonify({"error": "Only the librarian or an administrator can change a fine"}), 403
        charged, err = _money(data["fine_amount"])
        if err:
            return jsonify({"error": err}), 400
        if charged != calculated:
            note = str(data.get("fine_note") or "").strip()
            if len(note) < 3:
                return jsonify({"error": "Please say why the fine is being changed (for example: waived, book was damaged)"}), 400
            record_audit("library.fine.adjust", "library", "borrow_record", record.id,
                         before={"calculated": calculated}, after={"charged": charged, "reason": note})

    record.returned_date = today
    record.status = "returned"
    record.fine_calculated = calculated
    record.fine_amount = charged
    record.fine_note = note[:255] if note else None

    book = Book.query.get(record.book_id)
    if book:
        book.available_copies = min(book.total_copies, book.available_copies + 1)

    db.session.commit()
    return jsonify(record.to_dict())


@bp.get("/overdue")
@permission_required("library.manage")
def list_overdue():
    today = date.today()
    overdue = scoped_query(BorrowRecord).filter(
        BorrowRecord.status == "borrowed", BorrowRecord.due_date < today
    ).all()
    return jsonify([r.to_dict() for r in overdue])
