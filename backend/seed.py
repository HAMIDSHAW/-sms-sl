"""
Seeds ONE demo tenant with a full set of test accounts (one per role) and
realistic-scale sample data: 20-50 students per class across all six
classes, a full Monday-Friday timetable (five subject periods plus a
lunch period every day) for every class, with several subjects taught
by teachers who each cover more than one class, matching how a real
secondary school staffs itself, not one teacher per subject.

Uses Kenema Government Secondary School as the reference, a real,
long-established (est. 1952) government secondary school on Combema
Road, Kenema, purely as realistic starter content. Every field seeded
here is editable by that school's admin from the settings screen at any
time (see app/routes/schools.py); this is placeholder data, not a
hard-coded identity.

TEST ACCOUNTS ONLY: every role account below has must_change_password
set to False and a shared, memorable password purely so testing has no
friction. Real onboarding (via the setup wizard / admin-created accounts)
still forces a password change on first login, as tested throughout this
project, this seed script just skips that step for convenience.
"""
import os
import random
from datetime import date, datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import (
    School, User, AcademicYear, Term, SchoolClass, Section, Subject,
    Staff, Student, Guardian, StudentGuardian, Enrollment, TeacherAssignment,
    AttendanceStatus, DEFAULT_ATTENDANCE_STATUSES, Attendance,
    Assignment, AssignmentSubmission, LearningMaterial,
    Examination, ExamSchedule, Mark,
    FeeCategory, FeeStructure, Invoice, Payment,
    Announcement, Message, Notification,
    LeaveRequest, PayrollRun, Payslip,
    DisciplinaryRecord,
    Book, BorrowRecord,
    Supplier, InventoryItem,
    Driver, Vehicle, TransportRoute, RouteStop, TransportAssignment,
    TimetableEntry,
)
from app.utils.rbac_seed import ensure_system_roles, ensure_super_admin_role
from app.utils.ids import generate_student_number
from app.utils.grading import ensure_default_grade_scale, compute_results, compute_class_positions

PUBLIC_DEMO_PASSWORD = "Password123!"  # printed in the README, so never acceptable on a real deployment
TEST_PASSWORD = os.environ.get("DEMO_PASSWORD") or PUBLIC_DEMO_PASSWORD
_demo_hash = None


def _demo_password_hash():
    """
    Every demo account shares one password, so hash it once instead of ~200 times. Hashing is
    deliberately slow, and on a small free host that alone would turn a one-minute seed into ten.
    """
    global _demo_hash
    if _demo_hash is None:
        from app.extensions import bcrypt
        _demo_hash = bcrypt.generate_password_hash(TEST_PASSWORD).decode("utf-8")
    return _demo_hash


def check_demo_password_for_deployment():
    """On a real deployment the demo accounts need a private password. Returns an error message or None."""
    from app.utils.passwords import validate_password
    if not os.environ.get("DEMO_PASSWORD"):
        return ("Set DEMO_PASSWORD to a private password of your own. Without it the demo accounts would use "
                "the public password printed in the README, and anyone could log in as the administrator.")
    if os.environ["DEMO_PASSWORD"] == PUBLIC_DEMO_PASSWORD:
        return "DEMO_PASSWORD is the public README password. Choose your own."
    return validate_password(os.environ["DEMO_PASSWORD"])
STUDENTS_PER_CLASS = 30  # within the requested 20-50 range

DEMO_SCHOOL = {
    "name": "Kenema Government Secondary School",
    "short_name": "KGSS",
    "motto": "Aut Optimum Aut Nihil",
    "address": "Combema Road, Kenema",
    "city": "Kenema",
    "district": "Kenema District",
    "country": "Sierra Leone",
    "phone": "+232 76 000000",
    "email": "info@kgss.example.sl",
    "student_id_prefix": "KGSS",
}

CLASSES = ["JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"]
SECTIONS = ["A", "B"]
SUBJECTS = [
    ("English Language", "ENG"), ("Mathematics", "MTH"), ("Integrated Science", "SCI"),
    ("Social Studies", "SOC"), ("French", "FRN"), ("Agriculture", "AGR"),
    ("Computer Studies", "ICT"), ("Physical Education", "PE"),
    ("Lunch Break", "LUNCH"),
]

# Staff with login accounts, one per role, per the test-account table in the README.
STAFF_DEFS = [
    ("Mr", "Mustapha", "Mansaray", "EMP-00001", "teacher", "Academics", "Mathematics Teacher", "teacher", "+232 76 100001"),
    ("Mrs", "Fatmata", "Kamara", "EMP-00002", "teacher", "Academics", "English Teacher", "teacher2", "+232 76 100002"),
    ("Mrs", "Sarah", "Conteh", "EMP-00003", "administrator", "Administration", "Principal", "principal", "+232 76 100003"),
    ("Mr", "James", "Bangura", "EMP-00004", "administrator", "Finance", "Accountant", "accountant", "+232 76 100004"),
    ("Miss", "Aminata", "Sesay", "EMP-00005", "administrator", "Academics", "Exam Officer", "examofficer", "+232 76 100005"),
    ("Mr", "Ibrahim", "Turay", "EMP-00006", "administrator", "HR", "HR Officer", "hrofficer", "+232 76 100006"),
    ("Madam", "Grace", "Koroma", "EMP-00007", "support", "Library", "Librarian", "librarian", "+232 76 100007"),
    ("Mr", "Foday", "Kamara", "EMP-00008", "support", "Operations", "Inventory Manager", "inventory", "+232 76 100008"),
    ("Mr", "Alusine", "Kargbo", "EMP-00009", "support", "Operations", "Transport Manager", "transport", "+232 76 100009"),
]

SLUG_TO_ROLE = {
    "teacher": "teacher", "teacher2": "teacher", "principal": "principal",
    "accountant": "accountant", "examofficer": "exam_officer", "hrofficer": "hr_officer",
    "librarian": "librarian", "inventory": "inventory_manager", "transport": "transport_manager",
}

# Additional teaching staff, no login needed, they exist so the timetable
# can show what a real school actually looks like: several subjects each
# taught by two teachers who split the six classes between them, so any
# one teacher realistically covers more than one class per day, and no
# teacher is ever double-booked. (first, last, employee_number, position, slug)
EXTRA_TEACHERS = [
    ("Mrs", "Amara", "Sesay", "EMP-00010", "Mathematics Teacher", "mathteacher2", "+232 76 100010"),
    ("Miss", "Zainab", "Turay", "EMP-00011", "English Teacher", "engteacher2", "+232 76 100011"),
    ("Mr", "Abubakarr", "Kposowa", "EMP-00012", "Integrated Science Teacher", "sciteacher1", "+232 76 100012"),
    ("Mrs", "Hawa", "Bangura", "EMP-00013", "Integrated Science Teacher", "sciteacher2", "+232 76 100013"),
    ("Mr", "Sorie", "Kargbo", "EMP-00014", "Social Studies Teacher", "socteacher1", "+232 76 100014"),
    ("Miss", "Isata", "Jalloh", "EMP-00015", "Social Studies Teacher", "socteacher2", "+232 76 100015"),
    ("Mr", "Ibrahim", "Koroma", "EMP-00016", "French Teacher", "frteacher1", "+232 76 100016"),
    ("Madam", "Mariama", "Sillah", "EMP-00017", "French Teacher", "frteacher2", "+232 76 100017"),
]

# Which staff slug is the "primary" (covers 4 classes) vs "secondary"
# (covers the remaining 2 classes) teacher for each subject taught daily.
SUBJECT_ORDER = ["MTH", "ENG", "SCI", "SOC", "FRN"]  # five periods a day
SUBJECT_TEACHER_SLUGS = {
    "MTH": ("teacher", "mathteacher2"),
    "ENG": ("teacher2", "engteacher2"),
    "SCI": ("sciteacher1", "sciteacher2"),
    "SOC": ("socteacher1", "socteacher2"),
    "FRN": ("frteacher1", "frteacher2"),
}
PRIMARY_CLASSES = CLASSES[:4]   # JSS 1, JSS 2, JSS 3, SSS 1, one teacher, rotated (shifts 0-3)
SECONDARY_CLASSES = CLASSES[4:]  # SSS 2, SSS 3, the other teacher, rotated (shifts 0-1)

PERIOD_TIMES = [
    ("08:00", "08:45"), ("08:45", "09:30"), ("09:30", "10:15"),
    ("11:00", "11:45"), ("11:45", "12:30"),
]
LUNCH_TIME = ("10:15", "11:00")
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

MALE_FIRST_NAMES = [
    "Mohamed", "Ibrahim", "Alusine", "Foday", "Abu", "Sorie", "Alhaji", "Amara", "Santigie", "Sahr",
    "Momoh", "Brima", "Kekura", "Sheku", "Yayah", "Bockarie", "Tamba", "Musa", "Idrissa", "Abdulai",
    "Osman", "Lamin", "Sallieu", "Ansumana",
]
FEMALE_FIRST_NAMES = [
    "Fatmata", "Aminata", "Mariama", "Isata", "Adama", "Kadiatu", "Hawa", "Zainab", "Memuna", "Marie",
    "Yeabu", "Kumba", "Rugiatu", "Fanta", "Aisha", "Jariatu", "Massah", "Salamatu", "Mabinty", "Umu",
    "Haja", "Kadija", "Yema", "Sia",
]
LAST_NAMES = [
    "Sesay", "Koroma", "Kamara", "Bangura", "Turay", "Conteh", "Sankoh", "Mansaray", "Kargbo", "Fofanah",
    "Jalloh", "Sillah", "Kanu", "Vandi", "Kabba", "Kallon", "Sowa", "Sheriff", "Kaikai", "Dumbuya",
    "Kposowa", "Gbondo", "Yillah", "Kposo",
]


def _seed_material_if_missing(school, subject, class_obj, staff, year):
    title = f"{subject.name}, {class_obj.name} resources"
    if LearningMaterial.query.filter_by(school_id=school.id, title=title, class_id=class_obj.id, subject_id=subject.id).first():
        return
    db.session.add(LearningMaterial(
        school_id=school.id, subject_id=subject.id, class_id=class_obj.id, staff_id=staff.id,
        academic_year_id=year.id, title=title,
        description=f"Term reference material for {subject.name} in {class_obj.name}.",
        material_type="pdf",
    ))


def _get_or_create_user(school_id, email, first_name, last_name, role_name, roles_map):
    user = User.query.filter_by(school_id=school_id, email=email).first()
    if not user:
        user = User(
            school_id=school_id, email=email, first_name=first_name, last_name=last_name,
            must_change_password=False,
        )
        user.password_hash = _demo_password_hash()
        user.roles.append(roles_map[role_name])
        db.session.add(user)
        db.session.flush()
    return user


STAFF_ADDRESSES = [
    "12 Hangha Road, near the Central Mosque, Kenema",
    "Nongowa Chiefdom, behind Kenema Government Hospital",
    "5 Combema Road, opposite Rokel Commercial Bank, Kenema",
    "Blama Road, near the Methodist Church, Kenema",
    "Dama Road, next to the Freetown Highway filling station, Kenema",
    "Lowcost Housing Estate, Block C, Kenema",
    "Burma Camp, close to the Police Barracks, Kenema",
    "Tikonko Road junction, Kenema",
    "New London, near the Orange Money shop, Kenema",
]
BASE_SALARY_BY_STAFF_TYPE = {"teacher": 2000000, "administrator": 2500000, "support": 1500000}
GUARDIAN_FIRST_NAMES = [
    "Alhaji", "Mohamed", "Ibrahim", "Fatmata", "Aminata", "Mariama", "Sorie", "Kadiatu", "Santigie", "Hawa",
    "Abu", "Isata", "Foday", "Zainab", "Sahr", "Marie", "Brima", "Memuna", "Tamba", "Adama",
]
TUITION_BY_CLASS = {"JSS 1": 500000, "JSS 2": 520000, "JSS 3": 550000, "SSS 1": 600000, "SSS 2": 620000, "SSS 3": 650000}


def seed_extras(school, staff_objs):
    """
    Realistic school-wide data layered on top of the base seed. Every block checks
    for what already exists, so running seed.py again (or on an older database)
    only adds what is missing.
    """
    from app.utils.ledger import recompute_invoice_status

    rng = random.Random(20261009)
    today = date.today()
    year = AcademicYear.query.filter_by(school_id=school.id, is_current=True).first() or AcademicYear.query.filter_by(school_id=school.id).first()
    term = Term.query.filter_by(school_id=school.id, academic_year_id=year.id, is_current=True).first() or Term.query.filter_by(school_id=school.id).first()
    classes = {c.name: c for c in SchoolClass.query.filter_by(school_id=school.id).all()}
    subjects = {s.code: s for s in Subject.query.filter_by(school_id=school.id).all()}
    class_by_id = {c.id: c for c in classes.values()}

    enroll_by_class = {}
    for e in Enrollment.query.filter_by(school_id=school.id, status="active").all():
        enroll_by_class.setdefault(e.class_id, []).append(e.student_id)
    students = {s.id: s for s in Student.query.filter_by(school_id=school.id).all()}
    showcase_names = {"Abdul": None, "Isata": None}
    for s in students.values():
        if s.first_name in showcase_names and showcase_names[s.first_name] is None:
            showcase_names[s.first_name] = s.id
    abdul_id, isata_id = showcase_names["Abdul"], showcase_names["Isata"]

    # --- Staff: home address and base salary ---------------------------------
    for i, member in enumerate(Staff.query.filter_by(school_id=school.id).order_by(Staff.employee_number).all()):
        if not member.address:
            member.address = STAFF_ADDRESSES[i % len(STAFF_ADDRESSES)]
        if not member.base_salary:
            member.base_salary = BASE_SALARY_BY_STAFF_TYPE.get(member.staff_type, 1800000)

    # --- Guardians: real names instead of "<First>s Guardian" -----------------
    for g in Guardian.query.filter_by(school_id=school.id, last_name="Guardian").all():
        link = StudentGuardian.query.filter_by(guardian_id=g.id).first()
        child = students.get(link.student_id) if link else None
        g.first_name = rng.choice(GUARDIAN_FIRST_NAMES)
        g.last_name = child.last_name if child else "Kamara"
        g.phone = f"+232 7{rng.randint(5, 9)} {rng.randint(100000, 999999)}"
        g.address = rng.choice(STAFF_ADDRESSES)
        g.occupation = rng.choice(["Trader", "Farmer", "Teacher", "Nurse", "Driver", "Civil servant", "Tailor"])

    accountant = staff_objs.get("accountant")
    marker = staff_objs.get("teacher")
    db.session.flush()

    # --- Attendance: nine school days of whole-day records for everyone -------
    status_by_code = {s.code: s for s in AttendanceStatus.query.filter_by(school_id=school.id).all()}
    school_days = []
    d = today
    while len(school_days) < 9:
        if d.weekday() < 5:
            school_days.append(d)
        d -= timedelta(days=1)
    existing_whole_day = {
        (a.student_id, a.date) for a in Attendance.query.filter(
            Attendance.school_id == school.id, Attendance.subject_id.is_(None), Attendance.date.in_(school_days)
        ).all()
    }
    for class_id, student_ids in enroll_by_class.items():
        for day in school_days:
            for sid in student_ids:
                if (sid, day) in existing_whole_day:
                    continue
                roll = rng.random()
                code = "present" if roll < 0.90 else "late" if roll < 0.94 else "absent" if roll < 0.98 else "excused"
                if sid == abdul_id:
                    code = "present"
                db.session.add(Attendance(
                    school_id=school.id, student_id=sid, class_id=class_id, academic_year_id=year.id, term_id=term.id,
                    date=day, status_id=status_by_code[code].id, marked_by_staff_id=marker.id if marker else None,
                ))
    db.session.flush()

    # --- Finance: a fee structure per class, an invoice per student, payments with payer details ---
    tuition = FeeCategory.query.filter_by(school_id=school.id, name="Tuition").first()
    receipts = Payment.query.filter_by(school_id=school.id).count()
    invoice_count = Invoice.query.filter_by(school_id=school.id).count()
    methods = ["cash", "cash", "mobile_money", "mobile_money", "bank_transfer"]
    for cname, cls in classes.items():
        structure = FeeStructure.query.filter_by(school_id=school.id, class_id=cls.id, name=f"{cname} Tuition - First Term").first()
        if not structure and cname == "JSS 1":
            structure = FeeStructure.query.filter_by(school_id=school.id, class_id=cls.id).first()
        if not structure:
            structure = FeeStructure(
                school_id=school.id, name=f"{cname} Tuition - First Term", academic_year_id=year.id, term_id=term.id,
                class_id=cls.id, fee_category_id=tuition.id, amount=TUITION_BY_CLASS.get(cname, 500000),
                due_date=date(2026, 10, 1),
            )
            db.session.add(structure)
            db.session.flush()
        for sid in enroll_by_class.get(cls.id, []):
            if Invoice.query.filter_by(school_id=school.id, student_id=sid, fee_structure_id=structure.id).first():
                continue
            invoice_count += 1
            invoice = Invoice(
                school_id=school.id, invoice_number=f"INV-{invoice_count:06d}", student_id=sid,
                fee_structure_id=structure.id, description=structure.name, amount=structure.amount, due_date=structure.due_date,
            )
            db.session.add(invoice)
            db.session.flush()
            roll = rng.random()
            if sid in (abdul_id, isata_id) or roll >= 0.75:
                continue  # left unpaid, so there are overdue invoices to chase
            amount = structure.amount if roll < 0.50 else round(structure.amount * rng.choice([0.3, 0.5, 0.6]), -3)
            link = StudentGuardian.query.filter_by(student_id=sid).first()
            guardian = Guardian.query.get(link.guardian_id) if link else None
            student = students[sid]
            who = rng.random()
            if guardian and who < 0.75:
                payer = (f"{guardian.first_name} {guardian.last_name}", guardian.phone, link.relationship_type or "parent")
            elif who < 0.9:
                payer = (f"{rng.choice(GUARDIAN_FIRST_NAMES)} {student.last_name}", f"+232 7{rng.randint(5, 9)} {rng.randint(100000, 999999)}", "relative")
            else:
                payer = (student.full_name, student.phone, "student")
            receipts += 1
            db.session.add(Payment(
                school_id=school.id, invoice_id=invoice.id, student_id=sid, amount=amount,
                payment_method=rng.choice(methods), status="successful", receipt_number=f"RCT-{receipts:06d}",
                received_by_staff_id=accountant.id if accountant else None,
                payer_name=payer[0], payer_phone=payer[1], payer_relationship=payer[2],
                paid_at=datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 20)),
            ))
            db.session.flush()
            recompute_invoice_status(invoice)
    # Give the older showcase payments a payer too, so no receipt is blank.
    for p in Payment.query.filter_by(school_id=school.id, payer_name=None).all():
        link = StudentGuardian.query.filter_by(student_id=p.student_id).first()
        g = Guardian.query.get(link.guardian_id) if link else None
        if g:
            p.payer_name, p.payer_phone, p.payer_relationship = f"{g.first_name} {g.last_name}", g.phone, "parent"
        if not p.received_by_staff_id and accountant:
            p.received_by_staff_id = accountant.id
    db.session.flush()

    # --- Exams: every class sits the five core subjects, so positions mean something ---
    exam = Examination.query.filter_by(school_id=school.id, name="First Term Examination").first()
    if exam:
        core = ["MTH", "ENG", "SCI", "SOC", "FRN"]
        exam_day = date(2026, 12, 2)
        ability = {}
        for sid in students:
            ability[sid] = rng.gauss(62, 14)
        if abdul_id:
            ability[abdul_id] = 96
        if isata_id:
            ability[isata_id] = 46
        for cname, cls in classes.items():
            for offset, code in enumerate(core):
                schedule = ExamSchedule.query.filter_by(examination_id=exam.id, class_id=cls.id, subject_id=subjects[code].id).first()
                if not schedule:
                    schedule = ExamSchedule(
                        school_id=school.id, examination_id=exam.id, subject_id=subjects[code].id, class_id=cls.id,
                        date=exam_day + timedelta(days=offset), start_time=datetime.strptime("09:00", "%H:%M").time(),
                        end_time=datetime.strptime("11:00", "%H:%M").time(), max_marks=100, room=f"{cname} classroom",
                    )
                    db.session.add(schedule)
                    db.session.flush()
                have = {m.student_id for m in Mark.query.filter_by(exam_schedule_id=schedule.id).all()}
                for sid in enroll_by_class.get(cls.id, []):
                    if sid in have:
                        continue
                    score = max(8, min(98, round(ability[sid] + rng.gauss(0, 8))))
                    db.session.add(Mark(school_id=school.id, exam_schedule_id=schedule.id, student_id=sid, obtained_marks=score))
        db.session.flush()
        for cname, cls in classes.items():
            for sid in enroll_by_class.get(cls.id, []):
                result = compute_results(school.id, exam.id, sid)
                if result and result.status != "published":
                    result.status = "published"
            compute_class_positions(school.id, exam.id, cls.id)
        db.session.flush()

    # --- Assignments with submissions, per class ------------------------------
    def _teacher_for(cls_id, code):
        entry = TimetableEntry.query.filter_by(school_id=school.id, class_id=cls_id, subject_id=subjects[code].id).first()
        return entry.staff_id if entry else None

    ASSIGNMENT_DEFS = [
        ("MTH", "Mathematics Exercise 1", "Solve questions 1 to 10 on page 24. Show all working.", 14),
        ("ENG", "English Composition: My Community", "Write a composition of at least 250 words about your community.", 10),
        ("SCI", "Science Worksheet: States of Matter", "Complete the worksheet on solids, liquids and gases.", 18),
    ]
    for cname, cls in classes.items():
        for code, title, instructions, due_in in ASSIGNMENT_DEFS:
            staff_id = _teacher_for(cls.id, code)
            if not staff_id:
                continue
            assignment = Assignment.query.filter_by(school_id=school.id, class_id=cls.id, title=title).first()
            if not assignment:
                assignment = Assignment(
                    school_id=school.id, subject_id=subjects[code].id, class_id=cls.id, staff_id=staff_id,
                    academic_year_id=year.id, term_id=term.id, title=title, description=instructions,
                    instructions=instructions, start_date=today - timedelta(days=6),
                    due_date=today + timedelta(days=due_in - 12), max_marks=20, submission_type="text", status="published",
                )
                db.session.add(assignment)
                db.session.flush()
            for sid in enroll_by_class.get(cls.id, []):
                if sid == abdul_id and code == "MTH":
                    continue  # left un-submitted so the student and parent logins can try the flow
                pair = random.Random(f"{cname}|{code}|{sid}")  # same answer on every run, so re-seeding adds nothing
                if pair.random() > 0.68 and sid != isata_id:
                    continue
                if AssignmentSubmission.query.filter_by(assignment_id=assignment.id, student_id=sid).first():
                    continue
                late = pair.random() < 0.12
                submitted_at = datetime.now(timezone.utc) - timedelta(days=pair.randint(0, 4), hours=pair.randint(0, 20))
                sub = AssignmentSubmission(
                    school_id=school.id, assignment_id=assignment.id, student_id=sid,
                    content_text="Here is my completed work for this assignment.",
                    submitted_at=submitted_at, status="late" if late else "submitted",
                )
                if pair.random() < 0.45 or sid == isata_id:
                    sub.status = "graded"
                    sub.marks_obtained = max(3, min(20, round(pair.gauss(14, 4))))
                    sub.feedback = pair.choice(["Good effort.", "Well done, keep it up.", "Check your working on the later questions.", "Neat and accurate."])
                    sub.graded_by_staff_id = staff_id
                    sub.graded_at = submitted_at + timedelta(days=1)
                db.session.add(sub)
    db.session.flush()

    # --- Discipline: a spread of cases and outcomes ---------------------------
    principal = staff_objs.get("principal")
    pool = [sid for sid in students if sid not in (abdul_id, isata_id)]
    CASES = [
        ("incident", "high", "Fought with a classmate during break.", "Parents called in. Two day suspension.", "resolved"),
        ("warning", "low", "Came late to school three times this week.", "Verbal warning given.", "open"),
        ("incident", "medium", "Was found using a phone during an exam.", None, "open"),
        ("warning", "medium", "Disrupted a lesson repeatedly.", "Moved to the front row, to be reviewed in two weeks.", "open"),
        ("positive_recognition", None, "Won the inter-school quiz for the school.", "Recognised at assembly.", "resolved"),
        ("positive_recognition", None, "Volunteered to clean the library every Friday.", "Certificate issued.", "resolved"),
        ("suspension", "high", "Repeated bullying of a younger student.", "Suspended for one week pending a parents meeting.", "open"),
    ]
    if DisciplinaryRecord.query.filter_by(school_id=school.id).count() < 4:
        for i, (cat, sev, desc, action, status) in enumerate(CASES):
            rec = DisciplinaryRecord(
                school_id=school.id, student_id=pool[(i * 17) % len(pool)],
                reported_by_staff_id=(principal or marker).id, date=today - timedelta(days=i * 2 + 1),
                category=cat, severity=sev, description=desc, action_taken=action, status=status,
            )
            if status == "resolved":
                rec.follow_up_note = "Matter closed after follow up."
                rec.resolved_at = datetime.now(timezone.utc)
            db.session.add(rec)

    # --- Inventory: more assets, one genuinely under maintenance ----------------
    from app.models import MaintenanceRecord
    supplier = Supplier.query.filter_by(school_id=school.id).first()
    if InventoryItem.query.filter_by(school_id=school.id).count() < 4:
        ITEMS = [
            ("Projector", "Electronics", 2, 2200000, "Staff room", "under_maintenance"),
            ("Laptops", "Electronics", 12, 6500000, "ICT lab", "in_use"),
            ("Whiteboards", "Furniture", 10, 450000, "Classrooms", "in_use"),
            ("Science lab microscopes", "Laboratory", 6, 1800000, "Science lab", "in_use"),
            ("Football kits", "Sports", 3, 900000, "Sports store", "in_stock"),
        ]
        for name, cat, qty, cost, loc, status in ITEMS:
            item = InventoryItem(
                school_id=school.id, name=name, category=cat, supplier_id=supplier.id if supplier else None,
                quantity=qty, unit_cost=cost, location=loc, status=status,
            )
            db.session.add(item)
            db.session.flush()
            if status == "under_maintenance":
                db.session.add(MaintenanceRecord(
                    school_id=school.id, item_id=item.id, description="Lamp replacement and cooling fan repair.",
                    cost=350000, performed_date=today - timedelta(days=2),
                    recorded_by_staff_id=staff_objs["inventory"].id if "inventory" in staff_objs else None,
                ))

    # --- Leave: a couple of requests still waiting for HR to decide ----------------
    if LeaveRequest.query.filter_by(school_id=school.id, status="pending").count() < 2:
        for key, kind, start, length, why in [
            ("teacher", "annual", 12, 5, "Family wedding in Bo."),
            ("teacher2", "sick", 3, 2, "Medical appointment and recovery."),
            ("librarian", "casual", 20, 1, "Personal errand."),
        ]:
            member = staff_objs.get(key)
            if member:
                db.session.add(LeaveRequest(
                    school_id=school.id, staff_id=member.id, leave_type=kind, start_date=today + timedelta(days=start),
                    end_date=today + timedelta(days=start + length - 1), reason=why, status="pending",
                ))

    # --- Payroll: a draft run waiting to be generated -----------------------------
    if not PayrollRun.query.filter_by(school_id=school.id, period_label="February 2027").first():
        db.session.add(PayrollRun(
            school_id=school.id, period_label="February 2027", period_start=date(2027, 2, 1),
            period_end=date(2027, 2, 28), status="draft",
        ))
    db.session.flush()


def run_seed(app=None, from_boot=False):
    """
    Load the demo school. On a real deployment this needs your explicit say-so (ALLOW_DEMO_SEED=1, or
    SEED_DEMO_ON_BOOT=1 which the app itself passes as from_boot) AND a private DEMO_PASSWORD, because
    every demo account shares one password.
    """
    from app.utils.security import is_deployment
    if is_deployment():
        if not from_boot and os.environ.get("ALLOW_DEMO_SEED") != "1":
            raise SystemExit(
                "Refusing to seed demo data into a production setup without your say-so. Set ALLOW_DEMO_SEED=1 "
                "and a private DEMO_PASSWORD if you do want a demo school on this site."
            )
        problem = check_demo_password_for_deployment()
        if problem:
            raise SystemExit("Refusing to seed demo data: " + problem)
    app = app or create_app()
    with app.app_context():
        db.create_all()
        ensure_super_admin_role()

        school = School.query.filter_by(short_name=DEMO_SCHOOL["short_name"]).first()
        if not school:
            school = School(country="Sierra Leone")
            db.session.add(school)
        for k, v in DEMO_SCHOOL.items():
            setattr(school, k, v)
        school.setup_completed = True
        db.session.flush()

        roles = ensure_system_roles(school)
        ensure_default_grade_scale(school.id)
        db.session.flush()

        super_admin_role = ensure_super_admin_role()
        if not User.query.filter_by(school_id=None, email="superadmin@platform.example").first():
            sa = User(
                school_id=None, email="superadmin@platform.example",
                first_name="Platform", last_name="Admin", must_change_password=False,
            )
            sa.password_hash = _demo_password_hash()
            sa.roles.append(super_admin_role)
            db.session.add(sa)

        owner = _get_or_create_user(school.id, "admin@kgss.example.sl", "School", "Administrator", "school_administrator", roles)

        # --- Academic year + terms ---
        year = AcademicYear.query.filter_by(school_id=school.id, name="2026/2027").first()
        if not year:
            year = AcademicYear(
                school_id=school.id, name="2026/2027",
                start_date=date(2026, 9, 1), end_date=date(2027, 7, 31), is_current=True,
            )
            db.session.add(year)
            db.session.flush()
            term_defs = [
                ("First Term", date(2026, 9, 1), date(2026, 12, 12)),
                ("Second Term", date(2027, 1, 11), date(2027, 4, 2)),
                ("Third Term", date(2027, 4, 20), date(2027, 7, 31)),
            ]
            for i, (name, start, end) in enumerate(term_defs):
                db.session.add(Term(
                    school_id=school.id, academic_year_id=year.id, name=name,
                    start_date=start, end_date=end, is_current=(i == 0),
                ))
        db.session.flush()
        term = Term.query.filter_by(academic_year_id=year.id, is_current=True).first()

        # --- Classes + sections ---
        class_objs = {}
        section_objs = {}  # {class_name: {"A": Section, "B": Section}}
        for i, cname in enumerate(CLASSES):
            c = SchoolClass.query.filter_by(school_id=school.id, name=cname).first()
            if not c:
                c = SchoolClass(school_id=school.id, name=cname, order_index=i)
                db.session.add(c)
                db.session.flush()
            class_objs[cname] = c
            section_objs[cname] = {}
            for sname in SECTIONS:
                sec = Section.query.filter_by(class_id=c.id, name=sname).first()
                if not sec:
                    sec = Section(school_id=school.id, class_id=c.id, name=sname, capacity=45)
                    db.session.add(sec)
                    db.session.flush()
                section_objs[cname][sname] = sec
        db.session.flush()
        jss1 = class_objs["JSS 1"]
        section_a = section_objs["JSS 1"]["A"]

        # --- Subjects ---
        subject_objs = {}
        for name, code in SUBJECTS:
            s = Subject.query.filter_by(school_id=school.id, code=code).first()
            if not s:
                s = Subject(school_id=school.id, name=name, code=code)
                db.session.add(s)
                db.session.flush()
            subject_objs[code] = s
        db.session.flush()
        math_subject = subject_objs["MTH"]

        # --- Staff, one per role, each with a login account ---
        staff_objs = {}
        for title, fn, ln, emp_no, stype, dept, position, slug, phone in STAFF_DEFS:
            s = Staff.query.filter_by(school_id=school.id, employee_number=emp_no).first()
            if not s:
                s = Staff(
                    school_id=school.id, employee_number=emp_no, title=title, first_name=fn, last_name=ln,
                    staff_type=stype, department=dept, position=position, phone=phone,
                    employment_date=date(2022, 9, 1),
                )
                db.session.add(s)
                db.session.flush()
            staff_objs[slug] = s

            email = f"{slug}@kgss.example.sl"
            user = _get_or_create_user(school.id, email, fn, ln, SLUG_TO_ROLE[slug], roles)
            if not s.user_id:
                s.user_id = user.id

        # --- Additional teaching staff (no login) so subjects have real coverage ---
        for title, fn, ln, emp_no, position, slug, phone in EXTRA_TEACHERS:
            s = Staff.query.filter_by(school_id=school.id, employee_number=emp_no).first()
            if not s:
                s = Staff(
                    school_id=school.id, employee_number=emp_no, title=title, first_name=fn, last_name=ln,
                    staff_type="teacher", department="Academics", position=position, phone=phone,
                    employment_date=date(2023, 9, 1),
                )
                db.session.add(s)
                db.session.flush()
            staff_objs[slug] = s

        db.session.flush()
        teacher_staff = staff_objs["teacher"]

        # --- Class masters (homeroom teachers), one per class, so a
        # whole-day attendance check has someone responsible for it. ---
        CLASS_MASTERS = {
            "JSS 1": "teacher", "JSS 2": "teacher2", "JSS 3": "sciteacher1",
            "SSS 1": "socteacher1", "SSS 2": "mathteacher2", "SSS 3": "engteacher2",
        }
        for cname, slug in CLASS_MASTERS.items():
            class_objs[cname].class_master_staff_id = staff_objs[slug].id
        db.session.flush()

        # --- Teacher assignments + full weekly timetable, all 6 classes ---
        # Each subject is taught by two teachers: a "primary" covering the
        # first four classes (rotated so they're never double-booked) and a
        # "secondary" covering the remaining two, exactly how a school
        # actually staffs a subject across grade levels, and a direct,
        # concrete demonstration that one teacher teaches more than one
        # class. Every class gets five subject periods and one lunch period,
        # every weekday.
        timetable_seeded = TimetableEntry.query.filter_by(school_id=school.id).count() >= len(CLASSES) * len(DAYS) * 6
        if not timetable_seeded:
            for subject_code in SUBJECT_ORDER:
                primary_slug, secondary_slug = SUBJECT_TEACHER_SLUGS[subject_code]
                primary_teacher = staff_objs[primary_slug]
                secondary_teacher = staff_objs[secondary_slug]

                for shift, cname in enumerate(PRIMARY_CLASSES):
                    if not TeacherAssignment.query.filter_by(
                        staff_id=primary_teacher.id, subject_id=subject_objs[subject_code].id,
                        class_id=class_objs[cname].id, academic_year_id=year.id,
                    ).first():
                        db.session.add(TeacherAssignment(
                            school_id=school.id, staff_id=primary_teacher.id, subject_id=subject_objs[subject_code].id,
                            class_id=class_objs[cname].id, academic_year_id=year.id,
                        ))
                for shift, cname in enumerate(SECONDARY_CLASSES):
                    if not TeacherAssignment.query.filter_by(
                        staff_id=secondary_teacher.id, subject_id=subject_objs[subject_code].id,
                        class_id=class_objs[cname].id, academic_year_id=year.id,
                    ).first():
                        db.session.add(TeacherAssignment(
                            school_id=school.id, staff_id=secondary_teacher.id, subject_id=subject_objs[subject_code].id,
                            class_id=class_objs[cname].id, academic_year_id=year.id,
                        ))
            db.session.flush()

            all_staff_for_duty = list(staff_objs.values())
            for day in DAYS:
                for shift, cname in enumerate(PRIMARY_CLASSES):
                    for period_idx, (start, end) in enumerate(PERIOD_TIMES):
                        subject_code = SUBJECT_ORDER[(period_idx + shift) % len(SUBJECT_ORDER)]
                        teacher = staff_objs[SUBJECT_TEACHER_SLUGS[subject_code][0]]
                        db.session.add(TimetableEntry(
                            school_id=school.id, academic_year_id=year.id, class_id=class_objs[cname].id,
                            subject_id=subject_objs[subject_code].id, staff_id=teacher.id,
                            day_of_week=day, start_time=datetime.strptime(start, "%H:%M").time(),
                            end_time=datetime.strptime(end, "%H:%M").time(), room=cname,
                        ))
                for shift, cname in enumerate(SECONDARY_CLASSES):
                    for period_idx, (start, end) in enumerate(PERIOD_TIMES):
                        subject_code = SUBJECT_ORDER[(period_idx + shift) % len(SUBJECT_ORDER)]
                        teacher = staff_objs[SUBJECT_TEACHER_SLUGS[subject_code][1]]
                        db.session.add(TimetableEntry(
                            school_id=school.id, academic_year_id=year.id, class_id=class_objs[cname].id,
                            subject_id=subject_objs[subject_code].id, staff_id=teacher.id,
                            day_of_week=day, start_time=datetime.strptime(start, "%H:%M").time(),
                            end_time=datetime.strptime(end, "%H:%M").time(), room=cname,
                        ))
                # Lunch, same time for every class, a different duty staff member
                # per class so no one is (even nominally) double-booked.
                for i, cname in enumerate(CLASSES):
                    duty_staff = all_staff_for_duty[i % len(all_staff_for_duty)]
                    db.session.add(TimetableEntry(
                        school_id=school.id, academic_year_id=year.id, class_id=class_objs[cname].id,
                        subject_id=subject_objs["LUNCH"].id, staff_id=duty_staff.id,
                        day_of_week=day, start_time=datetime.strptime(LUNCH_TIME[0], "%H:%M").time(),
                        end_time=datetime.strptime(LUNCH_TIME[1], "%H:%M").time(), room="Dining hall",
                    ))
            db.session.flush()

        # --- Students + guardians, 20-50 per class (30 here) ---
        rng = random.Random(20260901)  # fixed seed so re-running seed.py is deterministic
        student_objs_by_class = {cname: [] for cname in CLASSES}

        # The two named, richly-seeded showcase students (login accounts,
        # published result, invoice, attendance, discipline, library loan,
        # transport assignment) stay first in JSS 1.
        named_defs = [
            ("Abdul", "Sesay", "male", date(2013, 4, 12)),
            ("Isata", "Koroma", "female", date(2013, 8, 3)),
        ]
        for fn, ln, gender, dob in named_defs:
            student = Student.query.filter_by(school_id=school.id, first_name=fn, last_name=ln).first()
            if not student:
                student = Student(
                    school_id=school.id, student_number=generate_student_number(school),
                    first_name=fn, last_name=ln, gender=gender, date_of_birth=dob,
                    address="Nongowa Chiefdom, Kenema", admission_date=date(2026, 9, 1),
                )
                db.session.add(student)
                db.session.flush()
                guardian = Guardian(school_id=school.id, first_name=f"{fn}s", last_name="Guardian", phone="+232 77 000000")
                db.session.add(guardian)
                db.session.flush()
                db.session.add(StudentGuardian(
                    student_id=student.id, guardian_id=guardian.id, relationship_type="parent",
                    is_primary_contact=True, is_emergency_contact=True,
                ))
                db.session.add(Enrollment(
                    school_id=school.id, student_id=student.id, academic_year_id=year.id,
                    class_id=jss1.id, section_id=section_a.id, enrollment_date=date(2026, 9, 1),
                ))
            student_objs_by_class["JSS 1"].append(student)
        db.session.flush()
        s1, s2 = student_objs_by_class["JSS 1"][0], student_objs_by_class["JSS 1"][1]

        # Bulk-fill every class up to STUDENTS_PER_CLASS. Idempotent by
        # count, not by name (repeated Sierra Leonean names are realistic
        # and expected, the student_number is the real unique identifier).
        used_dob_years = list(range(2008, 2016))
        for cname in CLASSES:
            existing_count = Enrollment.query.filter_by(
                school_id=school.id, class_id=class_objs[cname].id, academic_year_id=year.id,
            ).count()
            to_create = max(0, STUDENTS_PER_CLASS - existing_count)
            for i in range(to_create):
                gender = rng.choice(["male", "female"])
                fn = rng.choice(MALE_FIRST_NAMES if gender == "male" else FEMALE_FIRST_NAMES)
                ln = rng.choice(LAST_NAMES)
                dob = date(rng.choice(used_dob_years), rng.randint(1, 12), rng.randint(1, 28))

                student = Student(
                    school_id=school.id, student_number=generate_student_number(school),
                    first_name=fn, last_name=ln, gender=gender, date_of_birth=dob,
                    address="Kenema, Sierra Leone", admission_date=date(2026, 9, 1),
                )
                db.session.add(student)
                db.session.flush()

                guardian = Guardian(
                    school_id=school.id, first_name=f"{fn}s", last_name="Guardian",
                    phone=f"+232 7{rng.randint(0, 9)} {rng.randint(100000, 999999)}",
                )
                db.session.add(guardian)
                db.session.flush()
                db.session.add(StudentGuardian(
                    student_id=student.id, guardian_id=guardian.id, relationship_type="parent",
                    is_primary_contact=True, is_emergency_contact=True,
                ))

                section_name = "A" if (existing_count + i) % 2 == 0 else "B"
                db.session.add(Enrollment(
                    school_id=school.id, student_id=student.id, academic_year_id=year.id,
                    class_id=class_objs[cname].id, section_id=section_objs[cname][section_name].id,
                    enrollment_date=date(2026, 9, 1),
                ))
                student_objs_by_class[cname].append(student)
        db.session.flush()

        # --- One student login + one parent login, linked to the named showcase student ---
        student_user = _get_or_create_user(school.id, "student@kgss.example.sl", s1.first_name, s1.last_name, "student", roles)
        if not s1.user_id:
            s1.user_id = student_user.id

        g1 = Guardian.query.join(StudentGuardian, Guardian.id == StudentGuardian.guardian_id).filter(
            StudentGuardian.student_id == s1.id
        ).first()
        parent_user = _get_or_create_user(school.id, "parent@kgss.example.sl", g1.first_name, g1.last_name, "parent", roles)
        if not g1.user_id:
            g1.user_id = parent_user.id

        # Make the second showcase student (Isata) a sibling of Abdul under
        # the same parent login, in addition to her own existing guardian -
        # so the demo parent account actually has more than one child
        # linked to it. Without this, the "a parent can have more than one
        # kid" scenario had no seeded account to ever test it with.
        existing_link = StudentGuardian.query.filter_by(student_id=s2.id, guardian_id=g1.id).first()
        if not existing_link:
            db.session.add(StudentGuardian(
                student_id=s2.id, guardian_id=g1.id, relationship_type="parent",
                is_primary_contact=False, is_emergency_contact=False,
            ))

        db.session.flush()

        # --- Attendance: mark today for the two showcase students ---
        if not AttendanceStatus.query.filter_by(school_id=school.id).first():
            for st in DEFAULT_ATTENDANCE_STATUSES:
                db.session.add(AttendanceStatus(school_id=school.id, **st))
            db.session.flush()
        present_status = AttendanceStatus.query.filter_by(school_id=school.id, code="present").first()
        absent_status = AttendanceStatus.query.filter_by(school_id=school.id, code="absent").first()
        today = date.today()
        if not Attendance.query.filter_by(student_id=s1.id, date=today, subject_id=None).first():
            db.session.add(Attendance(
                school_id=school.id, student_id=s1.id, class_id=jss1.id, section_id=section_a.id,
                academic_year_id=year.id, term_id=term.id, date=today, status_id=present_status.id,
                marked_by_staff_id=teacher_staff.id,
            ))
        if not Attendance.query.filter_by(student_id=s2.id, date=today, subject_id=None).first():
            db.session.add(Attendance(
                school_id=school.id, student_id=s2.id, class_id=jss1.id, section_id=section_a.id,
                academic_year_id=year.id, term_id=term.id, date=today, status_id=absent_status.id,
                marked_by_staff_id=teacher_staff.id,
            ))

        # Per-period marks too, the whole-day check above is the class
        # master's summary; these are the actual subject-period marks a
        # student would accumulate across the day, matching the real
        # per-period workflow (each subject teacher marks their own
        # period, not just one blanket daily mark).
        english_subject = subject_objs["ENG"]
        for student, status in [(s1, present_status), (s2, present_status)]:
            if not Attendance.query.filter_by(student_id=student.id, date=today, subject_id=math_subject.id).first():
                db.session.add(Attendance(
                    school_id=school.id, student_id=student.id, class_id=jss1.id, section_id=section_a.id,
                    subject_id=math_subject.id, academic_year_id=year.id, term_id=term.id, date=today,
                    status_id=status.id, marked_by_staff_id=teacher_staff.id,
                ))
            if not Attendance.query.filter_by(student_id=student.id, date=today, subject_id=english_subject.id).first():
                db.session.add(Attendance(
                    school_id=school.id, student_id=student.id, class_id=jss1.id, section_id=section_a.id,
                    subject_id=english_subject.id, academic_year_id=year.id, term_id=term.id, date=today,
                    status_id=(present_status if student is s1 else absent_status).id,
                    marked_by_staff_id=staff_objs["teacher2"].id,
                ))

        # --- Assignment (published) + learning material ---
        if not Assignment.query.filter_by(school_id=school.id, title="Algebra Homework 1").first():
            db.session.add(Assignment(
                school_id=school.id, subject_id=math_subject.id, class_id=jss1.id, section_id=section_a.id,
                staff_id=teacher_staff.id, academic_year_id=year.id, term_id=term.id,
                title="Algebra Homework 1", description="Solve the linear equations on page 42.",
                due_date=today + timedelta(days=7), max_marks=20, status="published",
            ))
        if not LearningMaterial.query.filter_by(school_id=school.id, title="Term 1 Algebra Notes").first():
            db.session.add(LearningMaterial(
                school_id=school.id, subject_id=math_subject.id, class_id=jss1.id, section_id=section_a.id,
                staff_id=teacher_staff.id, academic_year_id=year.id,
                title="Term 1 Algebra Notes", description="Summary notes covering linear equations.",
                material_type="pdf",
            ))

        db.session.flush()

        # --- One learning material per subject, per class, every class sees
        # material for every subject it's actually taught, by the teacher who
        # actually teaches it there (same primary/secondary split as the
        # timetable), not just the one showcase Math note above. ---
        materials_seeded = LearningMaterial.query.filter_by(school_id=school.id).count()
        if materials_seeded < len(SUBJECT_ORDER) * len(CLASSES):
            for subject_code in SUBJECT_ORDER:
                primary_slug, secondary_slug = SUBJECT_TEACHER_SLUGS[subject_code]
                for cname in PRIMARY_CLASSES:
                    _seed_material_if_missing(school, subject_objs[subject_code], class_objs[cname], staff_objs[primary_slug], year)
                for cname in SECONDARY_CLASSES:
                    _seed_material_if_missing(school, subject_objs[subject_code], class_objs[cname], staff_objs[secondary_slug], year)
            db.session.flush()

        # --- Examination with schedule, marks, and a computed + published result ---
        exam = Examination.query.filter_by(school_id=school.id, name="First Term Examination").first()
        if not exam:
            exam = Examination(
                school_id=school.id, name="First Term Examination", academic_year_id=year.id, term_id=term.id,
                start_date=date(2026, 12, 1), end_date=date(2026, 12, 10), status="completed",
            )
            db.session.add(exam)
            db.session.flush()

            schedule = ExamSchedule(
                school_id=school.id, examination_id=exam.id, subject_id=math_subject.id, class_id=jss1.id,
                section_id=section_a.id, date=date(2026, 12, 2), start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("11:00", "%H:%M").time(), max_marks=100,
            )
            db.session.add(schedule)
            db.session.flush()

            db.session.add(Mark(school_id=school.id, exam_schedule_id=schedule.id, student_id=s1.id, obtained_marks=85))
            db.session.add(Mark(school_id=school.id, exam_schedule_id=schedule.id, student_id=s2.id, obtained_marks=45))
            db.session.flush()

            for student in [s1, s2]:
                result = compute_results(school.id, exam.id, student.id)
                if result:
                    result.status = "published"
            compute_class_positions(school.id, exam.id, jss1.id)

        # --- Finance: fee category, structure, invoices, one payment ---
        tuition = FeeCategory.query.filter_by(school_id=school.id, name="Tuition").first()
        if not tuition:
            tuition = FeeCategory(school_id=school.id, name="Tuition")
            db.session.add(tuition)
            db.session.flush()

        structure = FeeStructure.query.filter_by(school_id=school.id, name="JSS1 Tuition - First Term").first()
        if not structure:
            structure = FeeStructure(
                school_id=school.id, name="JSS1 Tuition - First Term", academic_year_id=year.id, term_id=term.id,
                class_id=jss1.id, fee_category_id=tuition.id, amount=500000, due_date=date(2026, 10, 1),
            )
            db.session.add(structure)
            db.session.flush()

        for i, student in enumerate([s1, s2]):
            invoice = Invoice.query.filter_by(school_id=school.id, student_id=student.id, fee_structure_id=structure.id).first()
            if not invoice:
                count = Invoice.query.filter_by(school_id=school.id).count()
                invoice = Invoice(
                    school_id=school.id, invoice_number=f"INV-{count + 1:06d}", student_id=student.id,
                    fee_structure_id=structure.id, description=structure.name, amount=structure.amount,
                    due_date=structure.due_date,
                )
                db.session.add(invoice)
                db.session.flush()
                if i == 0:
                    pcount = Payment.query.filter_by(school_id=school.id).count()
                    db.session.add(Payment(
                        school_id=school.id, invoice_id=invoice.id, student_id=student.id, amount=structure.amount,
                        payment_method="mobile_money", reference="MM-SEED-001", status="successful",
                        receipt_number=f"RCT-{pcount + 1:06d}",
                    ))
                    invoice.status = "paid"

        # --- Discipline: one positive recognition record ---
        if not DisciplinaryRecord.query.filter_by(school_id=school.id, student_id=s1.id).first():
            db.session.add(DisciplinaryRecord(
                school_id=school.id, student_id=s1.id, reported_by_staff_id=teacher_staff.id,
                date=today, category="positive_recognition", description="Helped a classmate with homework.",
                action_taken="Praised in class.",
            ))

        # --- Library: a real catalog, not just one book ---
        book = Book.query.filter_by(school_id=school.id, title="Things Fall Apart").first()
        if not book:
            book = Book(
                school_id=school.id, title="Things Fall Apart", author="Chinua Achebe",
                category="Literature", total_copies=3, available_copies=2,
            )
            db.session.add(book)
            db.session.flush()
            db.session.add(BorrowRecord(
                school_id=school.id, book_id=book.id, student_id=s1.id,
                borrowed_date=today - timedelta(days=3), due_date=today + timedelta(days=11),
                issued_by_staff_id=staff_objs["librarian"].id,
            ))

        MORE_BOOKS = [
            ("The River Between", "Ngũgĩ wa Thiong'o", "Literature", 2),
            ("New General Mathematics for JSS", "M.F. Macrae", "Mathematics", 5),
            ("New General Mathematics for SSS", "M.F. Macrae", "Mathematics", 5),
            ("Integrated Science for Secondary Schools", "STAN", "Science", 4),
            ("A History of Sierra Leone", "Christopher Fyfe", "History", 2),
            ("Waiting for an Angel", "Helon Habila", "Literature", 2),
            ("Purple Hibiscus", "Chimamanda Ngozi Adichie", "Literature", 3),
            ("English Grammar in Use", "Raymond Murphy", "English Language", 4),
            ("Longman Active Study Dictionary", "Longman", "Reference", 3),
            ("Elementary French Course", "WACE", "French", 2),
            ("Introduction to Computer Studies", "STAN", "Computer Studies", 3),
            ("Citizenship Education for West Africa", "WAEC", "Social Studies", 3),
            ("Half of a Yellow Sun", "Chimamanda Ngozi Adichie", "Literature", 2),
            ("Basic Agricultural Science", "STAN", "Agriculture", 3),
        ]
        if Book.query.filter_by(school_id=school.id).count() < len(MORE_BOOKS) + 1:
            for title, author, category, copies in MORE_BOOKS:
                if not Book.query.filter_by(school_id=school.id, title=title).first():
                    db.session.add(Book(
                        school_id=school.id, title=title, author=author, category=category,
                        total_copies=copies, available_copies=copies,
                    ))
            db.session.flush()

        # A couple more active loans so the librarian sees real circulation, not one row.
        extra_loan_book = Book.query.filter_by(school_id=school.id, title="New General Mathematics for JSS").first()
        if extra_loan_book and not BorrowRecord.query.filter_by(school_id=school.id, book_id=extra_loan_book.id).first():
            db.session.add(BorrowRecord(
                school_id=school.id, book_id=extra_loan_book.id, student_id=s2.id,
                borrowed_date=today - timedelta(days=6), due_date=today + timedelta(days=8),
                issued_by_staff_id=staff_objs["librarian"].id,
            ))
            extra_loan_book.available_copies -= 1

        # --- Inventory: one supplier, one item ---
        supplier = Supplier.query.filter_by(school_id=school.id, name="Kenema Office Supplies").first()
        if not supplier:
            supplier = Supplier(school_id=school.id, name="Kenema Office Supplies", phone="+232 76 111111")
            db.session.add(supplier)
            db.session.flush()
            db.session.add(InventoryItem(
                school_id=school.id, name="Student desks", category="Furniture", supplier_id=supplier.id,
                quantity=50, unit_cost=150000, location="JSS1 classroom",
            ))

        # --- Transport: driver, vehicle, route with stops, one student assignment ---
        driver = Driver.query.filter_by(school_id=school.id, full_name="Mohamed Kargbo").first()
        if not driver:
            driver = Driver(
                school_id=school.id, full_name="Mohamed Kargbo", phone="+232 77 222222",
                license_number="DL-0042", address="Combema Road, Kenema",
            )
            db.session.add(driver)
            db.session.flush()

            vehicle = Vehicle(
                school_id=school.id, vehicle_number="BUS-01", vehicle_type="bus", capacity=30, driver_id=driver.id,
            )
            db.session.add(vehicle)
            db.session.flush()

            route = TransportRoute(
                school_id=school.id, name="Combema Road Route", vehicle_id=vehicle.id, driver_id=driver.id,
                departure_time=datetime.strptime("06:30", "%H:%M").time(),
            )
            db.session.add(route)
            db.session.flush()

            stop1 = RouteStop(school_id=school.id, route_id=route.id, name="Combema Junction", order_index=0,
                               arrival_time=datetime.strptime("06:45", "%H:%M").time())
            db.session.add(stop1)
            db.session.add(RouteStop(school_id=school.id, route_id=route.id, name="School Gate", order_index=1,
                                      arrival_time=datetime.strptime("07:00", "%H:%M").time()))
            db.session.flush()

        # A second driver on the roster (not yet assigned a route) so the
        # driver list isn't just one row.
        if not Driver.query.filter_by(school_id=school.id, full_name="Fatmata Bangura").first():
            db.session.add(Driver(
                school_id=school.id, full_name="Fatmata Bangura", phone="+232 78 333333",
                license_number="DL-0091", address="Hangha Road, Kenema",
            ))

            db.session.add(TransportAssignment(school_id=school.id, student_id=s1.id, route_id=route.id, stop_id=stop1.id))

        # --- HR: leave requests across several staff and statuses, not just one ---
        LEAVE_DEFS = [
            (teacher_staff.id, "sick", 2, 4, "Flu", "pending"),
            ("engteacher2", "annual", 20, 25, "Family event", "approved"),
            ("sciteacher1", "annual", -15, -10, "Wedding", "approved"),
            ("principal", "maternity", 30, 100, "Maternity leave", "pending"),
            ("hrofficer", "unpaid", -30, -28, "Personal matter", "rejected"),
        ]
        for staff_ref, leave_type, start_offset, end_offset, reason, status in LEAVE_DEFS:
            staff_id = staff_ref if staff_ref == teacher_staff.id else staff_objs[staff_ref].id
            if LeaveRequest.query.filter_by(school_id=school.id, staff_id=staff_id, reason=reason).first():
                continue
            lr = LeaveRequest(
                school_id=school.id, staff_id=staff_id, leave_type=leave_type,
                start_date=today + timedelta(days=start_offset), end_date=today + timedelta(days=end_offset),
                reason=reason, status=status,
            )
            if status in ("approved", "rejected"):
                lr.reviewed_by_staff_id = staff_objs["hrofficer"].id
                lr.reviewed_at = datetime.now(timezone.utc)
            db.session.add(lr)

        # --- Payroll: three months of history, every staff member paid each run ---
        PAYROLL_MONTHS = [
            ("November 2026", date(2026, 11, 1), date(2026, 11, 30), "paid"),
            ("December 2026", date(2026, 12, 1), date(2026, 12, 31), "paid"),
            ("January 2027", date(2027, 1, 1), date(2027, 1, 31), "processed"),
        ]
        BASE_SALARY_BY_TYPE = {"teacher": 2000000, "administrator": 2500000, "support": 1500000}
        for period_label, period_start, period_end, run_status in PAYROLL_MONTHS:
            run = PayrollRun.query.filter_by(school_id=school.id, period_label=period_label).first()
            if run:
                continue
            run = PayrollRun(
                school_id=school.id, period_label=period_label, period_start=period_start,
                period_end=period_end, status=run_status, processed_at=datetime.now(timezone.utc),
            )
            db.session.add(run)
            db.session.flush()
            for slug, staff_member in staff_objs.items():
                base = BASE_SALARY_BY_TYPE.get(staff_member.staff_type, 1800000)
                db.session.add(Payslip(
                    school_id=school.id, payroll_run_id=run.id, staff_id=staff_member.id,
                    base_salary=base, allowances=int(base * 0.1), taxes=int(base * 0.075),
                    status="paid" if run_status == "paid" else "pending",
                ))
        db.session.flush()

        # --- Communication: one school-wide announcement, one message ---
        if not Announcement.query.filter_by(school_id=school.id, title="Welcome to the new term").first():
            db.session.add(Announcement(
                school_id=school.id, author_user_id=owner.id, title="Welcome to the new term",
                body="First Term begins September 1st. We wish all students a productive year.",
                audience_type="school",
            ))
        if not Message.query.filter_by(school_id=school.id, sender_user_id=owner.id, recipient_user_id=parent_user.id).first():
            db.session.add(Message(
                school_id=school.id, sender_user_id=owner.id, recipient_user_id=parent_user.id,
                subject="Welcome", body="Welcome to KGSS's school management system. Please reach out with any questions.",
            ))

        # --- A starter set of notifications, so the bell has something in
        # it for every test login on a freshly-seeded database, without
        # having to first perform the action (send a message, mark
        # attendance, etc.) that would normally trigger each one. ---
        def _seed_notification(user_id, ntype, title, body, days_ago=0, read=False):
            if not user_id:
                return
            exists = Notification.query.filter_by(school_id=school.id, user_id=user_id, title=title).first()
            if exists:
                return
            n = Notification(
                school_id=school.id, user_id=user_id, type=ntype, title=title, body=body,
                created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
                is_read=read,
            )
            db.session.add(n)

        teacher_uid = staff_objs["teacher"].user_id if "teacher" in staff_objs else None
        principal_uid = staff_objs["principal"].user_id if "principal" in staff_objs else None
        accountant_uid = staff_objs["accountant"].user_id if "accountant" in staff_objs else None
        hr_uid = staff_objs["hrofficer"].user_id if "hrofficer" in staff_objs else None

        _seed_notification(owner.id, "message_received", "New message from a parent", "Re: Abdul's homework, could we set up a time to talk?", days_ago=0)
        _seed_notification(owner.id, "invoice_created", "Invoice created", "Term 1 tuition invoice issued for 5 students.", days_ago=1, read=True)
        _seed_notification(teacher_uid, "period_starting_soon", "Mathematics starts at 09:00", "JSS 1, Room 4", days_ago=0)
        _seed_notification(teacher_uid, "leave_decided", "Leave request approved", "Your casual leave (Oct 5 to Oct 6) was approved.", days_ago=2, read=True)
        _seed_notification(student_user.id, "assignment_published", "New assignment: Algebra Basics", "Due in 5 days. Check the Assignments page for details.", days_ago=0)
        _seed_notification(student_user.id, "result_published", "First Term results published", "Your First Term examination results are now available.", days_ago=3, read=True)
        _seed_notification(parent_user.id, "attendance_absent", "Marked absent on the most recent school day", "No note provided.", days_ago=0)
        _seed_notification(parent_user.id, "invoice_created", "New invoice: Term 1 Tuition", "Le 500,000.00 due by end of term.", days_ago=1)
        _seed_notification(parent_user.id, "announcement_published", "Welcome to the new term", "First Term begins September 1st.", days_ago=5, read=True)
        _seed_notification(accountant_uid, "payment_successful", "Payment recorded", "A payment was recorded against an open invoice.", days_ago=1, read=True)
        _seed_notification(hr_uid, "message_received", "New message from a staff member", "Question about the payroll schedule.", days_ago=0)
        _seed_notification(principal_uid, "message_received", "New message", "A parent has a question about their child's progress.", days_ago=0)

        seed_extras(school, staff_objs)
        db.session.commit()

        total_students = Student.query.filter_by(school_id=school.id).count()
        print(f"Seeded {total_students} students across {len(CLASSES)} classes, "
              f"full weekly timetable for all classes, {len(STAFF_DEFS) + len(EXTRA_TEACHERS)} staff.")


if __name__ == "__main__":
    run_seed()
