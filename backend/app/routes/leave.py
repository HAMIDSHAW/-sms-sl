from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import LeaveRequest, Staff
from app.utils.tenancy import current_school_id, current_user, permission_required, scoped_query, jwt_required_scoped
from app.utils.notify import notify

bp = Blueprint("leave", __name__, url_prefix="/api/hr/leave")


def _d(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _caller_staff():
    user = current_user()
    return Staff.query.filter_by(user_id=user.id, school_id=current_school_id()).first()


@bp.get("")
@jwt_required_scoped
def list_leave():
    """
    HR/admin with hr.leave.view see everyone's requests (filterable by
    staff_id). A staff member with no broader permission sees only their
    own, this is the same self-scoping pattern used for students/parents
    elsewhere, applied to the staff side for once.
    """
    user = current_user()
    query = scoped_query(LeaveRequest)

    if user.has_permission("hr.leave.view"):
        staff_id = request.args.get("staff_id")
        if staff_id:
            query = query.filter_by(staff_id=staff_id)
    else:
        caller_staff = _caller_staff()
        if not caller_staff:
            return jsonify({"error": "No staff record linked to this account"}), 403
        query = query.filter_by(staff_id=caller_staff.id)

    return jsonify([r.to_dict() for r in query.order_by(LeaveRequest.created_at.desc()).all()])


@bp.post("")
@permission_required("hr.leave.request")
def create_leave_request():
    """A staff member requests leave for themself, staff_id is always their own linked record, never client-supplied."""
    caller_staff = _caller_staff()
    if not caller_staff:
        return jsonify({"error": "No staff record linked to this account"}), 403

    data = request.get_json(silent=True) or {}
    required = ["start_date", "end_date"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    leave = LeaveRequest(
        school_id=current_school_id(), staff_id=caller_staff.id,
        leave_type=data.get("leave_type", "annual"), start_date=_d(data["start_date"]),
        end_date=_d(data["end_date"]), reason=data.get("reason"),
    )
    db.session.add(leave)
    db.session.flush()
    from app.utils.notify import notify_permission_holders
    notify_permission_holders(
        current_school_id(), "hr.leave.approve", "leave_requested", f"Leave request from {caller_staff.full_name}",
        f"{leave.leave_type.title()} leave, {leave.start_date} to {leave.end_date}.",
        exclude_user_id=current_user().id, related_entity_type="leave_request", related_entity_id=leave.id,
    )
    db.session.commit()
    return jsonify(leave.to_dict()), 201


@bp.post("/<leave_id>/approve")
@permission_required("hr.leave.approve")
def approve_leave(leave_id):
    leave = scoped_query(LeaveRequest).filter_by(id=leave_id).first_or_404()
    if leave.status != "pending":
        return jsonify({"error": f"Cannot approve a request in status '{leave.status}'"}), 409
    data = request.get_json(silent=True) or {}
    leave.status = "approved"
    leave.review_note = data.get("review_note")
    leave.reviewed_by_staff_id = _caller_staff().id if _caller_staff() else None
    leave.reviewed_at = datetime.now(timezone.utc)
    staff_member = Staff.query.get(leave.staff_id)
    if staff_member and staff_member.user_id:
        notify(
            current_school_id(), staff_member.user_id, "leave_decided", "Leave request approved",
            f"Your {leave.leave_type} leave ({leave.start_date} to {leave.end_date}) was approved.",
            related_entity_type="leave_request", related_entity_id=leave.id,
        )
    db.session.commit()
    return jsonify(leave.to_dict())


@bp.post("/<leave_id>/reject")
@permission_required("hr.leave.approve")
def reject_leave(leave_id):
    leave = scoped_query(LeaveRequest).filter_by(id=leave_id).first_or_404()
    if leave.status != "pending":
        return jsonify({"error": f"Cannot reject a request in status '{leave.status}'"}), 409
    data = request.get_json(silent=True) or {}
    leave.status = "rejected"
    leave.review_note = data.get("review_note")
    leave.reviewed_by_staff_id = _caller_staff().id if _caller_staff() else None
    leave.reviewed_at = datetime.now(timezone.utc)
    staff_member = Staff.query.get(leave.staff_id)
    if staff_member and staff_member.user_id:
        notify(
            current_school_id(), staff_member.user_id, "leave_decided", "Leave request rejected",
            f"Your {leave.leave_type} leave ({leave.start_date} to {leave.end_date}) was rejected."
            + (f" Note: {leave.review_note}" if leave.review_note else ""),
            related_entity_type="leave_request", related_entity_id=leave.id,
        )
    db.session.commit()
    return jsonify(leave.to_dict())
