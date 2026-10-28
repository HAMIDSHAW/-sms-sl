"""
Global activity log.

Every successful create / update / delete made through the API is written to
the audit log automatically, with the person who did it and a plain English
summary ("Recorded a payment", "Graded a submission"). Routes that already call
record_audit() themselves are not logged a second time.

Reads (GET) are not logged. Notification housekeeping is skipped as noise.
"""
import re

from flask import g, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.extensions import db

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

SKIP_PREFIXES = ("/api/notifications", "/api/auth/refresh", "/api/uploads")

# (METHOD, normalised path) -> (action, summary). "<id>" stands for any uuid.
LABELS = {
    ("POST", "/api/auth/login"): ("auth.login", "Signed in"),
    ("POST", "/api/auth/logout"): ("auth.logout", "Signed out"),
    ("POST", "/api/auth/change-password"): ("auth.change_password", "Changed their password"),
    ("PATCH", "/api/auth/me"): ("auth.update_profile", "Updated their own profile"),
    ("POST", "/api/students"): ("students.create", "Added a student"),
    ("PATCH", "/api/students/<id>"): ("students.update", "Edited a student record"),
    ("DELETE", "/api/students/<id>"): ("students.delete", "Deleted a student"),
    ("POST", "/api/staff"): ("staff.create", "Added a staff member"),
    ("PATCH", "/api/staff/<id>"): ("staff.update", "Edited a staff record"),
    ("DELETE", "/api/staff/<id>"): ("staff.delete", "Removed a staff member"),
    ("POST", "/api/guardians"): ("guardians.create", "Added a guardian"),
    ("PATCH", "/api/guardians/<id>"): ("guardians.update", "Edited a guardian"),
    ("POST", "/api/attendance"): ("attendance.mark", "Marked attendance"),
    ("POST", "/api/attendance/bulk"): ("attendance.mark", "Marked attendance for a class"),
    ("POST", "/api/assignments"): ("assignments.create", "Created an assignment"),
    ("PATCH", "/api/assignments/<id>"): ("assignments.update", "Edited an assignment"),
    ("DELETE", "/api/assignments/<id>"): ("assignments.delete", "Deleted an assignment"),
    ("POST", "/api/assignments/<id>/publish"): ("assignments.publish", "Published an assignment"),
    ("POST", "/api/assignments/<id>/submissions"): ("assignments.submit", "Submitted an assignment"),
    ("PATCH", "/api/assignments/<id>/submissions/<id>/grade"): ("assignments.grade", "Graded a submission"),
    ("POST", "/api/materials"): ("materials.create", "Shared a learning material"),
    ("PATCH", "/api/materials/<id>"): ("materials.update", "Edited a learning material"),
    ("DELETE", "/api/materials/<id>"): ("materials.delete", "Deleted a learning material"),
    ("POST", "/api/exams"): ("exams.create", "Created an examination"),
    ("PATCH", "/api/exams/<id>"): ("exams.update", "Edited an examination"),
    ("POST", "/api/invoices"): ("finance.invoice.create", "Created an invoice"),
    ("POST", "/api/invoices/bill-class"): ("finance.invoice.bulk", "Billed a whole class"),
    ("POST", "/api/invoices/generate-from-structure"): ("finance.invoice.bulk", "Generated invoices from a fee structure"),
    ("PATCH", "/api/invoices/<id>/cancel"): ("finance.invoice.cancel", "Cancelled an invoice"),
    ("POST", "/api/payments"): ("finance.payment.create", "Recorded a payment"),
    ("PATCH", "/api/payments/<id>/refund"): ("finance.payment.refund", "Refunded a payment"),
    ("POST", "/api/messages"): ("messages.send", "Sent a message"),
    ("POST", "/api/messages/<id>/reply"): ("messages.reply", "Replied to a message"),
    ("POST", "/api/announcements"): ("announcements.create", "Posted an announcement"),
    ("POST", "/api/hr/leave"): ("hr.leave.request", "Requested leave"),
    ("POST", "/api/hr/leave/<id>/approve"): ("hr.leave.approve", "Approved a leave request"),
    ("POST", "/api/hr/leave/<id>/reject"): ("hr.leave.reject", "Rejected a leave request"),
    ("PATCH", "/api/hr/payroll/payslips/<id>"): ("hr.payslip.update", "Adjusted a payslip"),
    ("POST", "/api/hr/payroll/runs"): ("hr.payroll.create", "Created a payroll run"),
    ("POST", "/api/hr/payroll/runs/<id>/generate"): ("hr.payroll.generate", "Generated payslips"),
    ("POST", "/api/hr/payroll/runs/<id>/mark-paid"): ("hr.payroll.paid", "Marked a payroll run as paid"),
    ("POST", "/api/discipline"): ("discipline.create", "Recorded a discipline case"),
    ("PATCH", "/api/discipline/<id>"): ("discipline.update", "Updated a discipline case"),
    ("POST", "/api/discipline/<id>/resolve"): ("discipline.resolve", "Resolved a discipline case"),
    ("POST", "/api/library/books"): ("library.book.create", "Added a library book"),
    ("PATCH", "/api/library/books/<id>"): ("library.book.update", "Updated a library book"),
    ("DELETE", "/api/library/books/<id>"): ("library.book.delete", "Removed a library book"),
    ("POST", "/api/library/borrow"): ("library.borrow", "Lent out a library book"),
    ("POST", "/api/library/borrow-records/<id>/return"): ("library.return", "Took a library book back"),
    ("POST", "/api/marks/bulk"): ("exams.marks", "Entered exam marks"),
    ("POST", "/api/results/compute"): ("results.compute", "Calculated results"),
    ("POST", "/api/results/<id>/submit"): ("results.submit", "Submitted results for review"),
    ("POST", "/api/results/<id>/review"): ("results.review", "Reviewed results"),
    ("POST", "/api/results/<id>/approve"): ("results.approve", "Approved results"),
    ("POST", "/api/results/<id>/publish"): ("results.publish", "Published results"),
    ("POST", "/api/exams/<id>/schedules"): ("exams.schedule", "Scheduled an exam paper"),
    ("POST", "/api/enrollments"): ("enrollment.create", "Enrolled a student in a class"),
    ("PATCH", "/api/enrollments/<id>"): ("enrollment.update", "Changed a student's enrollment"),
    ("POST", "/api/users"): ("users.create", "Created a login account"),
    ("PATCH", "/api/users/<id>"): ("users.update", "Edited a login account"),
    ("DELETE", "/api/users/<id>"): ("users.delete", "Deactivated a login account"),
    ("POST", "/api/users/<id>/reset-password"): ("users.reset_password", "Reset someone's password"),
    ("POST", "/api/students/import"): ("students.import", "Imported students from a file"),
    ("POST", "/api/academics/classes"): ("academics.class.create", "Added a class"),
    ("PATCH", "/api/academics/classes/<id>"): ("academics.class.update", "Edited a class"),
    ("POST", "/api/academics/subjects"): ("academics.subject.create", "Added a subject"),
    ("POST", "/api/academics/years"): ("academics.year.create", "Added an academic year"),
    ("POST", "/api/academics/teacher-assignments"): ("academics.teacher.assign", "Assigned a teacher to a class"),
    ("POST", "/api/finance/structures"): ("finance.structure.create", "Created a fee structure"),
    ("POST", "/api/finance/expenses"): ("finance.expense.create", "Recorded an expense"),
    ("POST", "/api/guardians/<id>/link-student/<id>"): ("guardians.link", "Linked a guardian to a student"),
    ("POST", "/api/inventory/items"): ("inventory.create", "Added an inventory item"),
    ("DELETE", "/api/inventory/items/<id>"): ("inventory.delete", "Removed an inventory item"),
    ("POST", "/api/inventory/items/<id>/maintenance"): ("inventory.maintenance", "Sent an item for maintenance"),
    ("POST", "/api/inventory/items/<id>/restore"): ("inventory.restore", "Returned an item to service"),
    ("POST", "/api/transport/vehicles"): ("transport.vehicle.create", "Added a vehicle"),
    ("POST", "/api/transport/routes"): ("transport.route.create", "Added a transport route"),
    ("POST", "/api/transport/drivers"): ("transport.driver.create", "Added a driver"),
    ("POST", "/api/timetable"): ("timetable.create", "Added a timetable period"),
    ("PATCH", "/api/timetable/<id>"): ("timetable.update", "Edited a timetable period"),
    ("DELETE", "/api/timetable/<id>"): ("timetable.delete", "Deleted a timetable period"),
    ("PATCH", "/api/school"): ("school.update", "Changed school settings"),
}

VERBS = {"POST": "Created", "PATCH": "Updated", "PUT": "Updated", "DELETE": "Deleted"}


def _normalise(path):
    return UUID_RE.sub("<id>", path.rstrip("/") or "/")


def _entity_from_path(path):
    ids = UUID_RE.findall(path)
    parts = [p for p in path.split("/") if p and not UUID_RE.fullmatch(p)]
    entity_type = parts[1] if len(parts) > 1 else None
    return entity_type, (ids[0] if ids else None)


def register(app):
    @app.after_request
    def _log_activity(response):
        try:
            if request.method not in VERBS or not request.path.startswith("/api"):
                return response
            if response.status_code >= 400 or request.path.startswith(SKIP_PREFIXES):
                return response
            if getattr(g, "audit_recorded", False):
                return response

            from app.models import AuditLog, User

            user_id, school_id = None, None
            if request.path == "/api/auth/login":
                data = response.get_json(silent=True) or {}
                user_data = data.get("user") or {}
                user_id, school_id = user_data.get("id"), user_data.get("school_id")
            else:
                verify_jwt_in_request(optional=True)
                user_id = get_jwt_identity()
                if user_id:
                    school_id = get_jwt().get("school_id")
            if not user_id:
                return response

            norm = _normalise(request.path)
            action, summary = LABELS.get((request.method, norm), (None, None))
            module = (request.path.split("/") + ["", "", ""])[2] or "system"
            if not action:
                tail = " ".join(p for p in request.path.split("/")[2:] if p and not UUID_RE.fullmatch(p))
                action = f"{module}.{request.method.lower()}"
                summary = f"{VERBS[request.method]} {tail.replace('-', ' ')}"
            entity_type, entity_id = _entity_from_path(request.path)

            db.session.add(AuditLog(
                school_id=school_id, user_id=user_id, action=action, module=module,
                entity_type=entity_type, entity_id=entity_id,
                after_value={"summary": summary, "method": request.method, "path": request.path},
                ip_address=request.remote_addr,
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        return response
