from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from app.models import AuditLog, User
from app.utils.tenancy import permission_required, scoped_query

bp = Blueprint("audit", __name__, url_prefix="/api/audit-logs")


@bp.get("")
@permission_required("audit.view")
def list_audit_logs():
    """
    Who did what, when, spec section 75. Filterable by entity_type +
    entity_id (e.g. "who added this student") or by module. Newest first.
    """
    query = scoped_query(AuditLog)

    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id")
    module = request.args.get("module")
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if entity_id:
        query = query.filter_by(entity_id=entity_id)
    if module:
        query = query.filter_by(module=module)
    user_id = request.args.get("user_id")
    if user_id:
        query = query.filter_by(user_id=user_id)
    date_from, date_to = request.args.get("date_from"), request.args.get("date_to")
    if date_from:
        query = query.filter(AuditLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(AuditLog.created_at < datetime.fromisoformat(date_to) + timedelta(days=1))

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 30)), 100)
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    user_ids = {log.user_id for log in pagination.items if log.user_id}
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    items = []
    for log in pagination.items:
        d = log.to_dict()
        user = users.get(log.user_id)
        d["user_name"] = f"{user.first_name} {user.last_name}" if user else None
        d["user_email"] = user.email if user else None
        d["role"] = user.roles[0].name.replace("_", " ") if user and user.roles else None
        after = log.after_value if isinstance(log.after_value, dict) else {}
        d["summary"] = after.get("summary") or log.action.replace(".", " ").replace("_", " ")
        items.append(d)

    return jsonify({
        "items": items, "page": pagination.page, "pages": pagination.pages, "total": pagination.total,
    })
