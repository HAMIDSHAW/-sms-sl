from datetime import date, datetime, timezone

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import (
    Assignment, AssignmentSubmission, Staff, Student, Enrollment, SchoolClass, Subject,
    AcademicYear, TeacherAssignment,
)
from app.utils.audit import record_audit
from app.utils.tenancy import (
    current_school_id, current_user, permission_required, scoped_query, has_permission,
    linked_student_id, linked_staff_id, linked_guardian_children_ids, resolve_guardian_selected_child, has_role,
)

bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date() if value else None


def _today():
    return date.today()


def _is_owner(assignment):
    """
    Only the teacher who set an assignment (or, if an administrator set it on their behalf,
    that administrator) may see its submissions, grade, change, extend or publish it.
    """
    staff_id = linked_staff_id()
    if staff_id and assignment.staff_id == staff_id:
        return True
    return bool(assignment.created_by_user_id and assignment.created_by_user_id == current_user().id)


def _can_oversee():
    """
    The principal may look over every teacher's published assignments and how far hand-in has got,
    read-only. They can never see what students wrote, grade, change, extend or delete anything.
    """
    return has_role("principal")


def _owned_or_404(assignment_id):
    """Fetch an assignment for a staff caller. Someone else's looks exactly like one that doesn't exist."""
    assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
    if not _is_owner(assignment):
        from werkzeug.exceptions import NotFound
        raise NotFound()
    return assignment


def _owned_query():
    """Assignments the caller set themselves."""
    conditions = [Assignment.created_by_user_id == current_user().id]
    staff_id = linked_staff_id()
    if staff_id:
        conditions.append(Assignment.staff_id == staff_id)
    return scoped_query(Assignment).filter(db.or_(*conditions))


def _submission_state(assignment, student_id):
    sub = AssignmentSubmission.query.filter_by(assignment_id=assignment.id, student_id=student_id).first()
    if not sub:
        overdue = assignment.due_date and _today() > assignment.due_date
        return {"status": "overdue" if overdue else "not_submitted", "marks_obtained": None, "submission_id": None}
    return {
        "status": sub.status, "marks_obtained": sub.marks_obtained, "submission_id": sub.id,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None, "feedback": sub.feedback,
    }


def _teaches(staff_id, class_id, subject_id):
    return TeacherAssignment.query.filter_by(
        school_id=current_school_id(), staff_id=staff_id, class_id=class_id, subject_id=subject_id
    ).first() is not None


def _set_due_date(assignment, new_due):
    """
    Change the deadline. Moving it later is an extension: the first deadline is remembered and
    an assignment that had closed opens again.
    """
    if new_due < _today():
        return "Pick a deadline from today onward. To stop submissions now, close the assignment instead."
    if new_due > assignment.due_date:
        if assignment.original_due_date is None:
            assignment.original_due_date = assignment.due_date
        if assignment.status == "closed":
            assignment.status = "published"
    assignment.due_date = new_due
    return None


def _notify_class(assignment, kind, title, body):
    from app.utils.notify import notify, notify_guardians_of_student
    for enrollment in Enrollment.query.filter_by(class_id=assignment.class_id, status="active").all():
        student = Student.query.get(enrollment.student_id)
        if student and student.user_id:
            notify(current_school_id(), student.user_id, kind, title, body,
                   related_entity_type="assignment", related_entity_id=assignment.id)
        notify_guardians_of_student(current_school_id(), enrollment.student_id, kind, title, body,
                                    related_entity_type="assignment", related_entity_id=assignment.id)


@bp.get("")
@permission_required("assignments.view")
def list_assignments():
    """
    A student sees their own class's published assignments, each with their own submission
    status. A parent sees the SELECTED child's class (?student_id=, validated against their own
    children). Everyone else sees only the assignments they set themselves.
    """
    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()
    subject_student = student_id or child_id

    if subject_student:
        query = scoped_query(Assignment)
        enrollment = Enrollment.query.filter_by(student_id=subject_student, status="active").first()
        if not enrollment:
            return jsonify([])
        query = query.filter(Assignment.class_id == enrollment.class_id, Assignment.status.in_(["published", "closed"]))
    elif _can_oversee():
        # The principal's view: every teacher's published assignments (never drafts), read-only.
        query = scoped_query(Assignment).filter(Assignment.status.in_(["published", "closed"]))
        for field in ["class_id", "subject_id", "staff_id", "status"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Assignment, field) == value)
    else:
        query = _owned_query()
        for field in ["class_id", "section_id", "subject_id", "status"]:
            value = request.args.get(field)
            if value:
                query = query.filter(getattr(Assignment, field) == value)

    items = []
    for a in query.order_by(Assignment.due_date).all():
        d = a.to_dict()
        if subject_student:
            d["my_submission"] = _submission_state(a, subject_student)
            d["student_id"] = subject_student
        else:
            total = Enrollment.query.filter_by(class_id=a.class_id, status="active").count()
            subs = AssignmentSubmission.query.filter_by(assignment_id=a.id).all()
            d["class_size"] = total
            d["submission_count"] = len(subs)
            d["graded_count"] = sum(1 for x in subs if x.status == "graded")
            d["read_only"] = not _is_owner(a)
        items.append(d)
    return jsonify(items)


@bp.get("/options")
@permission_required("assignments.create")
def assignment_options():
    """
    The class and subject combinations a teacher may set work for: exactly the ones they teach.
    A teacher can teach several subjects (and the same subject to several classes), so this is a
    list of pairs. An administrator setting work on someone's behalf passes ?staff_id=.
    """
    staff_id = linked_staff_id()
    if not staff_id:
        staff_id = request.args.get("staff_id")
        if not staff_id or not Staff.query.filter_by(id=staff_id, school_id=current_school_id()).first():
            return jsonify([])
    rows = TeacherAssignment.query.filter_by(school_id=current_school_id(), staff_id=staff_id).all()
    seen, options = set(), []
    for r in rows:
        if (r.class_id, r.subject_id) in seen:
            continue
        seen.add((r.class_id, r.subject_id))
        klass, subject = SchoolClass.query.get(r.class_id), Subject.query.get(r.subject_id)
        if klass and subject:
            options.append({"class_id": klass.id, "class_name": klass.name, "subject_id": subject.id, "subject_name": subject.name})
    options.sort(key=lambda o: (o["class_name"], o["subject_name"]))
    return jsonify(options)


@bp.get("/<assignment_id>")
@permission_required("assignments.view")
def get_assignment(assignment_id):
    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()

    if student_id or child_id:
        assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
        enrollment = Enrollment.query.filter_by(student_id=student_id or child_id, status="active").first()
        if assignment.status not in ("published", "closed") or not enrollment or enrollment.class_id != assignment.class_id:
            return jsonify({"error": "Not found"}), 404
        d = assignment.to_dict()
        d["my_submission"] = _submission_state(assignment, student_id or child_id)
        d["student_id"] = student_id or child_id
        return jsonify(d)

    assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
    if _is_owner(assignment):
        d = assignment.to_dict()
        d["is_owner"] = True
        return jsonify(d)
    if _can_oversee() and assignment.status in ("published", "closed"):
        d = assignment.to_dict()
        d["is_owner"] = False
        d["read_only"] = True
        return jsonify(d)
    return jsonify({"error": "Not found"}), 404


@bp.post("")
@permission_required("assignments.create")
def create_assignment():
    data = request.get_json(silent=True) or {}
    required = ["subject_id", "class_id", "academic_year_id", "title", "due_date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    school_id = current_school_id()
    # staff_id comes from the caller's own linked staff record, so a teacher can't set work in
    # someone else's name. Only an account with no staff record (an administrator acting on a
    # teacher's behalf) names the teacher in the request.
    staff_id = linked_staff_id() or data.get("staff_id")
    if not staff_id:
        return jsonify({"error": "Choose which teacher this assignment is for"}), 400
    teacher = Staff.query.filter_by(id=staff_id, school_id=school_id).first()
    if not teacher:
        return jsonify({"error": "That teacher does not belong to this school"}), 404

    klass = SchoolClass.query.filter_by(id=data["class_id"], school_id=school_id).first()
    subject = Subject.query.filter_by(id=data["subject_id"], school_id=school_id).first()
    if not klass or not subject or not AcademicYear.query.filter_by(id=data["academic_year_id"], school_id=school_id).first():
        return jsonify({"error": "The class, subject or academic year does not belong to this school"}), 404
    if not _teaches(staff_id, klass.id, subject.id):
        who = "You are" if staff_id == linked_staff_id() else f"{teacher.full_name} is"
        return jsonify({"error": f"{who} not assigned to teach {subject.name} to {klass.name}"}), 403

    try:
        due = _d(data["due_date"])
        start = _d(data.get("start_date"))
    except (TypeError, ValueError):
        return jsonify({"error": "Dates must look like 2027-01-31"}), 400
    if due < _today():
        return jsonify({"error": "The deadline cannot be in the past"}), 400
    try:
        max_marks = int(data.get("max_marks", 100))
    except (TypeError, ValueError):
        return jsonify({"error": "max_marks must be a whole number"}), 400
    if max_marks < 1:
        return jsonify({"error": "max_marks must be at least 1"}), 400
    status = data.get("status", "draft")
    if status not in ("draft", "published"):
        return jsonify({"error": "status must be draft or published"}), 400

    assignment = Assignment(
        school_id=school_id,
        subject_id=subject.id, class_id=klass.id, section_id=data.get("section_id"),
        staff_id=staff_id, created_by_user_id=current_user().id,
        academic_year_id=data["academic_year_id"], term_id=data.get("term_id"),
        title=data["title"].strip(), description=data.get("description"), instructions=data.get("instructions"),
        start_date=start, due_date=due,
        max_marks=max_marks, attachment_url=data.get("attachment_url"),
        submission_type=data.get("submission_type", "file"),
        status=status,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify(assignment.to_dict()), 201


@bp.patch("/<assignment_id>")
@permission_required("assignments.update")
def update_assignment(assignment_id):
    assignment = _owned_or_404(assignment_id)
    data = request.get_json(silent=True) or {}
    editable = ["title", "description", "instructions", "max_marks", "attachment_url", "submission_type"]
    for field in editable:
        if field in data:
            setattr(assignment, field, data[field])
    if "status" in data:
        if data["status"] not in ("draft", "published", "closed"):
            return jsonify({"error": "status must be draft, published or closed"}), 400
        assignment.status = data["status"]
    if "start_date" in data:
        try:
            assignment.start_date = _d(data["start_date"])
        except (TypeError, ValueError):
            return jsonify({"error": "Dates must look like 2027-01-31"}), 400
    if "due_date" in data:
        try:
            new_due = _d(data["due_date"])
        except (TypeError, ValueError):
            return jsonify({"error": "Dates must look like 2027-01-31"}), 400
        error = _set_due_date(assignment, new_due)
        if error:
            return jsonify({"error": error}), 400
    db.session.commit()
    return jsonify(assignment.to_dict())


@bp.post("/<assignment_id>/extend")
@permission_required("assignments.update")
def extend_assignment(assignment_id):
    """
    Give students more time. Only the owner can. A closed assignment opens again, the class
    (and parents) are told the new deadline, and the original deadline stays on record.
    """
    assignment = _owned_or_404(assignment_id)
    data = request.get_json(silent=True) or {}
    try:
        new_due = _d(data.get("due_date"))
    except (TypeError, ValueError):
        return jsonify({"error": "Dates must look like 2027-01-31"}), 400
    if not new_due:
        return jsonify({"error": "Choose the new deadline"}), 400
    if new_due <= assignment.due_date and not (assignment.status == "closed" and new_due >= _today()):
        return jsonify({"error": f"Choose a date after the current deadline ({assignment.due_date.isoformat()})"}), 400

    old = assignment.due_date
    error = _set_due_date(assignment, new_due)
    if error:
        return jsonify({"error": error}), 400
    if assignment.status == "closed":
        assignment.status = "published"
    record_audit("assignment.extend", "assignments", "assignment", assignment.id,
                 before={"due_date": old.isoformat()}, after={"due_date": new_due.isoformat()})
    if assignment.status == "published":
        _notify_class(assignment, "assignment_extended", f"More time: {assignment.title}", f"New deadline: {new_due.isoformat()}")
    db.session.commit()
    return jsonify(assignment.to_dict())


@bp.post("/<assignment_id>/publish")
@permission_required("assignments.update")
def publish_assignment(assignment_id):
    """Draft -> Published (spec section 36). Only published assignments become visible to students/parents."""
    assignment = _owned_or_404(assignment_id)
    if assignment.due_date < _today():
        return jsonify({"error": "The deadline has already passed. Set a new deadline before publishing."}), 409
    assignment.status = "published"
    db.session.commit()

    from app.utils.notify import notify_guardians_of_student
    for e in Enrollment.query.filter_by(class_id=assignment.class_id, status="active").all():
        notify_guardians_of_student(
            current_school_id(), e.student_id, "assignment_published", f"New assignment: {assignment.title}",
            f"Due {assignment.due_date}", related_entity_type="assignment", related_entity_id=assignment.id,
        )
    db.session.commit()
    return jsonify(assignment.to_dict())


@bp.delete("/<assignment_id>")
@permission_required("assignments.delete")
def delete_assignment(assignment_id):
    """Only the teacher who set the assignment can delete it (not even admin or principal)."""
    assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
    if not linked_staff_id() or assignment.staff_id != linked_staff_id():
        return jsonify({"error": "Only the teacher who set this assignment can delete it"}), 403

    db.session.delete(assignment)
    db.session.commit()
    return jsonify({"message": "Assignment deleted"})


# --- Submissions (spec sections 37-38) -----------------------------------

@bp.get("/<assignment_id>/submissions")
@permission_required("assignments.view")
def list_submissions(assignment_id):
    """
    The owner (the teacher who set it) sees every submission, for grading. A student only ever
    sees their own row and a parent only their selected child's, enforced here, not just in the UI.
    Any other staff member gets "not found".
    """
    student_id = linked_student_id()
    child_id = None if student_id else resolve_guardian_selected_child()

    if student_id or child_id:
        assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
        query = scoped_query(AssignmentSubmission).filter_by(assignment_id=assignment.id, student_id=student_id or child_id)
        return jsonify([s.to_dict() for s in query.all()])

    assignment = _owned_or_404(assignment_id)
    return jsonify([s.to_dict() for s in scoped_query(AssignmentSubmission).filter_by(assignment_id=assignment.id).all()])


@bp.get("/<assignment_id>/roster")
@permission_required("assignments.grade")
def assignment_roster(assignment_id):
    """Every student in the class with their submission state, so a teacher sees who has NOT handed in."""
    assignment = _owned_or_404(assignment_id)
    subs = {s.student_id: s for s in AssignmentSubmission.query.filter_by(assignment_id=assignment.id).all()}
    rows = []
    for e in Enrollment.query.filter_by(class_id=assignment.class_id, status="active").all():
        student = Student.query.get(e.student_id)
        if not student:
            continue
        sub = subs.get(student.id)
        row = sub.to_dict() if sub else {
            "id": None, "assignment_id": assignment.id, "student_id": student.id, "status": "not_submitted",
            "student_name": student.full_name, "student_number": student.student_number,
            "student_photo_url": student.photo_url, "marks_obtained": None, "feedback": None,
        }
        rows.append(row)
    rows.sort(key=lambda r: (r.get("student_name") or ""))
    return jsonify(rows)


@bp.get("/<assignment_id>/progress")
@permission_required("assignments.view")
def assignment_progress(assignment_id):
    """
    Who has handed in and what they scored, for the principal's oversight. Deliberately leaves out
    what the students wrote, their attachments and the teacher's feedback: that stays between the
    teacher and the student.
    """
    if not _can_oversee():
        return jsonify({"error": "Not found"}), 404
    assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
    if assignment.status not in ("published", "closed"):
        return jsonify({"error": "Not found"}), 404
    subs = {s.student_id: s for s in AssignmentSubmission.query.filter_by(assignment_id=assignment.id).all()}
    rows = []
    for e in Enrollment.query.filter_by(class_id=assignment.class_id, status="active").all():
        student = Student.query.get(e.student_id)
        if not student:
            continue
        sub = subs.get(student.id)
        rows.append({
            "student_id": student.id, "student_name": student.full_name, "student_number": student.student_number,
            "status": sub.status if sub else "not_submitted",
            "marks_obtained": sub.marks_obtained if sub else None,
            "submitted_at": sub.submitted_at.isoformat() if sub and sub.submitted_at else None,
        })
    rows.sort(key=lambda r: r["student_name"] or "")
    return jsonify(rows)


@bp.post("/<assignment_id>/submissions")
@permission_required("assignments.submit")
def submit_assignment(assignment_id):
    """
    A student submits their own work. student_id is NEVER taken from the
    request body, only from the caller's own linked Student record, so
    there is no way to submit on behalf of another student even by editing
    the request.
    """
    student_id = linked_student_id()
    if not student_id:
        return jsonify({"error": "No student profile linked to this account"}), 403

    assignment = scoped_query(Assignment).filter_by(id=assignment_id).first_or_404()
    enrollment = Enrollment.query.filter_by(student_id=student_id, status="active").first()
    if assignment.status == "draft" or not enrollment or enrollment.class_id != assignment.class_id:
        return jsonify({"error": "Not found"}), 404
    if assignment.is_closed:
        return jsonify({
            "error": f"This assignment closed on {assignment.due_date.isoformat()}. Ask your teacher if they can extend the deadline.",
            "closed": True,
        }), 409
    data = request.get_json(silent=True) or {}

    now = datetime.now(timezone.utc)
    is_late = False

    submission = AssignmentSubmission.query.filter_by(assignment_id=assignment_id, student_id=student_id).first()
    if not submission:
        submission = AssignmentSubmission(
            school_id=current_school_id(), assignment_id=assignment_id, student_id=student_id,
        )
        db.session.add(submission)

    submission.content_text = data.get("content_text")
    submission.attachment_url = data.get("attachment_url")
    submission.submitted_at = now
    submission.status = "late" if is_late else "submitted"

    from app.utils.notify import notify, notify_guardians_of_student
    student = Student.query.get(student_id)
    teacher = Staff.query.get(assignment.staff_id)
    if teacher and teacher.user_id:
        notify(current_school_id(), teacher.user_id, "assignment_submitted",
               f"{student.full_name} submitted {assignment.title}", "Open the assignment to grade it.",
               related_entity_type="assignment", related_entity_id=assignment.id)
    notify_guardians_of_student(
        current_school_id(), student_id, "assignment_submitted",
        f"{student.full_name} submitted {assignment.title}", "Handed in" + (" late." if is_late else " on time."),
        related_entity_type="assignment", related_entity_id=assignment.id,
    )
    db.session.commit()
    return jsonify(submission.to_dict()), 201


@bp.patch("/<assignment_id>/submissions/<submission_id>/grade")
@permission_required("assignments.grade")
def grade_submission(assignment_id, submission_id):
    """Teacher grades a submission (spec section 38)."""
    assignment = _owned_or_404(assignment_id)  # only the teacher who set it can grade it
    submission = scoped_query(AssignmentSubmission).filter_by(
        id=submission_id, assignment_id=assignment.id
    ).first_or_404()
    data = request.get_json(silent=True) or {}

    if "marks_obtained" not in data:
        return jsonify({"error": "marks_obtained is required"}), 400

    try:
        marks = float(data["marks_obtained"])
    except (TypeError, ValueError):
        return jsonify({"error": "marks_obtained must be a number"}), 400
    if marks < 0 or (assignment.max_marks is not None and marks > assignment.max_marks):
        return jsonify({"error": f"Marks must be between 0 and {assignment.max_marks}"}), 400

    submission.marks_obtained = marks
    submission.feedback = data.get("feedback")
    submission.graded_by_staff_id = linked_staff_id()  # always the real caller, never a spoofed id
    submission.graded_at = datetime.now(timezone.utc)
    submission.status = "graded"

    from app.utils.notify import notify, notify_guardians_of_student
    student = Student.query.get(submission.student_id)
    body = f"{marks:g} / {assignment.max_marks:g}" + (f". {submission.feedback}" if submission.feedback else "")
    if student and student.user_id:
        notify(current_school_id(), student.user_id, "assignment_graded",
               f"Your work was graded: {assignment.title}", body,
               related_entity_type="assignment", related_entity_id=assignment.id)
    if student:
        notify_guardians_of_student(
            current_school_id(), student.id, "assignment_graded",
            f"{student.full_name} was graded: {assignment.title}", body,
            related_entity_type="assignment", related_entity_id=assignment.id,
        )
    db.session.commit()
    return jsonify(submission.to_dict())
