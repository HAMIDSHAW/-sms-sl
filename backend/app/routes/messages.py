from datetime import datetime, timezone

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import Message, User
from app.utils.tenancy import current_school_id, current_user, jwt_required_scoped
from app.utils.messaging import can_message
from app.utils.notify import notify

bp = Blueprint("messages", __name__, url_prefix="/api/messages")


@bp.get("/contacts")
@jwt_required_scoped
def searchable_contacts():
    """
    Recipient lookup for composing a message. Deliberately NOT the same as
    /api/users (which requires the staff-only users.view permission) -
    this exists so an ordinary teacher or parent can find someone to
    message at all. Safe to expose broadly because it only ever returns
    people can_message() already says the caller may contact; it can't be
    used to enumerate the whole school's directory.
    """
    q = request.args.get("q", "").strip().lower()
    sender = current_user()
    candidates = User.query.filter_by(school_id=current_school_id(), is_active=True).all()

    results = []
    for candidate in candidates:
        if candidate.id == sender.id:
            continue
        if q and q not in candidate.email.lower() and q not in f"{candidate.first_name} {candidate.last_name}".lower():
            continue
        if can_message(sender, candidate):
            results.append({
                "id": candidate.id, "email": candidate.email,
                "full_name": f"{candidate.first_name} {candidate.last_name}",
            })
        if len(results) >= 20:
            break

    return jsonify(results)


@bp.get("/inbox")
@jwt_required_scoped
def inbox():
    user = current_user()
    messages = Message.query.filter_by(recipient_user_id=user.id).order_by(Message.created_at.desc()).all()
    return jsonify([m.to_dict(viewer_id=user.id) for m in messages])


@bp.get("/sent")
@jwt_required_scoped
def sent():
    user = current_user()
    messages = Message.query.filter_by(sender_user_id=user.id).order_by(Message.created_at.desc()).all()
    return jsonify([m.to_dict(viewer_id=user.id) for m in messages])


@bp.post("")
@jwt_required_scoped
def send_message():
    """
    Send a direct message. The relationship check in can_message() is the
    real guard here (spec section 56), this route just calls it and
    refuses with a clear reason if it fails, rather than silently
    dropping the message or letting the frontend decide who's allowed.
    """
    data = request.get_json(silent=True) or {}
    recipient_id = data.get("recipient_user_id")
    body = data.get("body")
    if not recipient_id or not body:
        return jsonify({"error": "recipient_user_id and body are required"}), 400

    sender = current_user()
    recipient = User.query.filter_by(id=recipient_id, school_id=current_school_id()).first()
    if not recipient:
        return jsonify({"error": "Recipient not found"}), 404

    if not can_message(sender, recipient):
        return jsonify({"error": "You are not permitted to message this person"}), 403

    message = Message(
        school_id=current_school_id(), sender_user_id=sender.id, recipient_user_id=recipient.id,
        subject=data.get("subject"), body=body, is_anonymous=bool(data.get("is_anonymous")),
    )
    db.session.add(message)
    db.session.flush()

    notify(
        current_school_id(), recipient.id, "message_received",
        "New message" if data.get("is_anonymous") else f"New message from {sender.first_name} {sender.last_name}",
        body[:200], related_entity_type="message", related_entity_id=message.id,
    )

    db.session.commit()
    return jsonify(message.to_dict(viewer_id=sender.id)), 201


@bp.patch("/<message_id>/read")
@jwt_required_scoped
def mark_read(message_id):
    user = current_user()
    message = Message.query.filter_by(id=message_id, recipient_user_id=user.id).first_or_404()
    message.read_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(message.to_dict(viewer_id=user.id))


@bp.post("/<message_id>/reply")
@jwt_required_scoped
def reply_to_message(message_id):
    """
    Reply to a message you RECEIVED. The original sender already chose to
    contact you, so the relationship rule is not re-checked, and an anonymous
    sender's identity is never revealed to the person replying (the reply is
    simply routed to them on the server).
    """
    user = current_user()
    original = Message.query.filter_by(id=message_id, recipient_user_id=user.id).first_or_404()
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body is required"}), 400

    subject = original.subject or "Message"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    reply = Message(
        school_id=current_school_id(), sender_user_id=user.id, recipient_user_id=original.sender_user_id,
        subject=subject, body=body, is_anonymous=False,
    )
    db.session.add(reply)
    if not original.read_at:
        original.read_at = datetime.now(timezone.utc)
    db.session.flush()
    notify(
        current_school_id(), original.sender_user_id, "message_received",
        f"New reply from {user.first_name} {user.last_name}", body[:200],
        related_entity_type="message", related_entity_id=reply.id,
    )
    db.session.commit()
    return jsonify(reply.to_dict(viewer_id=user.id)), 201
