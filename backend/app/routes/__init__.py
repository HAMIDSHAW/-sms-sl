def register_blueprints(app):
    from app.routes import (
        auth, platform, schools, students, guardians, staff, academics,
        enrollments, users, attendance, timetable, assignments, materials,
        exams, grading, marks, results, fee_structures, invoices, payments, finance_reports,
        messages, announcements, notifications, leave, payroll, discipline, library, analytics, inventory,
        transport, audit, uploads, dashboard,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(platform.bp)
    app.register_blueprint(schools.bp)
    app.register_blueprint(students.bp)
    app.register_blueprint(guardians.bp)
    app.register_blueprint(staff.bp)
    app.register_blueprint(academics.bp)
    app.register_blueprint(enrollments.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(attendance.bp)
    app.register_blueprint(timetable.bp)
    app.register_blueprint(assignments.bp)
    app.register_blueprint(materials.bp)
    app.register_blueprint(exams.bp)
    app.register_blueprint(grading.bp)
    app.register_blueprint(marks.bp)
    app.register_blueprint(results.bp)
    app.register_blueprint(fee_structures.bp)
    app.register_blueprint(invoices.bp)
    app.register_blueprint(payments.bp)
    app.register_blueprint(finance_reports.bp)
    app.register_blueprint(messages.bp)
    app.register_blueprint(announcements.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(leave.bp)
    app.register_blueprint(payroll.bp)
    app.register_blueprint(discipline.bp)
    app.register_blueprint(library.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(transport.bp)
    app.register_blueprint(audit.bp)
    app.register_blueprint(uploads.bp)
    app.register_blueprint(dashboard.bp)
