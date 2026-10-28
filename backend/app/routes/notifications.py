from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Notification
from app.utils.tenancy import current_user, jwt_required_scoped

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@jwt_required_scoped
def list_notifications():
    user = current_user()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return jsonify([n.to_dict() for n in notifications])


@bp.patch("/<notification_id>/read")
@jwt_required_scoped
def mark_read(notification_id):
    user = current_user()
    n = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify(n.to_dict())


@bp.post("/read-all")
@jwt_required_scoped
def mark_all_read():
    user = current_user()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify({"message": "All notifications marked read"})
