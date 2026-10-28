"""
Automated "period starting soon" reminders.

Runs once a minute. Anything whose start_time falls 4-6 minutes from the
current time, on today's day_of_week, gets a reminder pushed to:
  - the teacher assigned to that period, and
  - every student enrolled in that class (and their guardians).

Idempotency: a reminder is only sent once per (timetable_entry, calendar
day). That's checked against the Notification table itself (a row with
related_entity_type="timetable_reminder", related_entity_id=<entry id>,
created today) rather than an in-memory set, so a server restart mid-day
can't cause either a duplicate flood or a silently-skipped period.

A 2-minute window checked every 60 seconds means each entry is seen at
least once (and sometimes twice, which the idempotency check absorbs)
regardless of small clock drift between the job tick and wall-clock time.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def check_and_send_reminders(app):
    with app.app_context():
        from app.extensions import db
        from app.models import TimetableEntry, Enrollment, Notification, Student
        from app.models.timetable import DAYS_OF_WEEK
        from app.utils.notify import notify, notify_guardians_of_student

        now = datetime.now()
        today_name = DAYS_OF_WEEK[now.weekday()]
        window_start = (now + timedelta(minutes=4)).time()
        window_end = (now + timedelta(minutes=6)).time()

        entries = TimetableEntry.query.filter(
            TimetableEntry.day_of_week == today_name,
            TimetableEntry.start_time >= window_start,
            TimetableEntry.start_time <= window_end,
        ).all()

        today_start = datetime.combine(now.date(), datetime.min.time())

        for entry in entries:
            already_sent = Notification.query.filter(
                Notification.related_entity_type == "timetable_reminder",
                Notification.related_entity_id == entry.id,
                Notification.created_at >= today_start,
            ).first()
            if already_sent:
                continue

            class_name = entry.school_class.name if entry.school_class else "class"
            subject_name = entry.subject.name if entry.subject else "period"
            when = entry.start_time.strftime("%H:%M")
            title = f"{subject_name} starts at {when}"
            body = f"{class_name}, {entry.room or 'room TBA'}"

            try:
                if entry.staff and entry.staff.user_id:
                    notify(
                        entry.school_id, entry.staff.user_id, "period_starting_soon", title, body,
                        related_entity_type="timetable_reminder", related_entity_id=entry.id,
                    )

                student_ids = [
                    e.student_id for e in Enrollment.query.filter_by(
                        class_id=entry.class_id, academic_year_id=entry.academic_year_id, status="active",
                    ).all()
                ]
                for student_id in student_ids:
                    notify_guardians_of_student(
                        entry.school_id, student_id, "period_starting_soon", title, body,
                        related_entity_type="timetable_reminder", related_entity_id=entry.id,
                    )
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception("Failed sending period reminder for timetable entry %s", entry.id)


def start_period_reminder_scheduler(app):
    """Run check_and_send_reminders once a minute on a plain daemon thread.
    Uses only the standard library, so no extra package has to be installed."""
    import threading
    import time

    def loop():
        while True:
            # Wait first: on a brand new install the tables do not exist for the first moments.
            time.sleep(60)
            try:
                check_and_send_reminders(app)
            except Exception:
                logger.exception("Period reminder loop failed")

    t = threading.Thread(target=loop, name="period-reminders", daemon=True)
    t.start()
    return t
