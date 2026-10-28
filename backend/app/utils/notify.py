"""
Event-driven notification creation (spec section 58/90). Call notify()
from wherever the triggering event actually happens, never from the
frontend. Wired into a representative set of real trigger points so far
(assignment publish, result publish, payment recorded) rather than every
possible event; see backend README for the full list still to wire up.
"""

from app.extensions import db
from app.models import Notification


def notify(school_id, user_id, type_, title, body=None, related_entity_type=None, related_entity_id=None):
    try:
        n = Notification(
            school_id=school_id, user_id=user_id, type=type_, title=title, body=body,
            related_entity_type=related_entity_type, related_entity_id=related_entity_id,
        )
        db.session.add(n)
    except Exception:
        pass


def notify_guardians_of_student(school_id, student_id, type_, title, body=None, **kwargs):
    """Fan out a notification to every guardian linked to a student's own login account."""
    from app.models import StudentGuardian, Guardian

    links = StudentGuardian.query.filter_by(student_id=student_id).all()
    for link in links:
        guardian = Guardian.query.get(link.guardian_id)
        if guardian and guardian.user_id:
            notify(school_id, guardian.user_id, type_, title, body, **kwargs)

    from app.models import Student
    student = Student.query.get(student_id)
    if student and student.user_id:
        notify(school_id, student.user_id, type_, title, body, **kwargs)


def notify_permission_holders(school_id, permission_code, type_, title, body=None, exclude_user_id=None, **kwargs):
    """Tell everyone in the school who holds `permission_code` (admins hold every code via the wildcard)."""
    from app.models import User

    for user in User.query.filter_by(school_id=school_id, is_active=True).all():
        if user.id == exclude_user_id:
            continue
        if user.has_permission(permission_code):
            notify(school_id, user.id, type_, title, body, **kwargs)
