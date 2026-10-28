from flask import g, request

from app.extensions import db
from app.models import AuditLog
from app.utils.tenancy import current_school_id, current_user


def record_audit(action, module, entity_type=None, entity_id=None, before=None, after=None):
    """
    Call this from a route right before/after db.session.commit() for any
    sensitive mutation. Swallows its own errors, a logging failure must
    never break the actual operation it's recording.
    """
    try:
        user = current_user()
        entry = AuditLog(
            school_id=current_school_id() if user and user.school_id else None,
            user_id=user.id if user else None,
            action=action, module=module, entity_type=entity_type, entity_id=entity_id,
            before_value=before, after_value=after,
            ip_address=request.remote_addr,
        )
        db.session.add(entry)
        g.audit_recorded = True  # tells the global activity hook not to log this request twice
    except Exception:
        pass
