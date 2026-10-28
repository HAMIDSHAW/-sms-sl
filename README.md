# SMS, School Management System

Kenema-based, Sierra Leone-oriented school management platform. This
folder holds both halves of the system:

```
SMS/
  backend/    Flask + SQLAlchemy API, SQL Server-ready (see backend/README.md)
  frontend/   React + Vite + Tailwind UI (see frontend/README.md)
```

## How to run it

**1. Backend:**
```bash
cd backend
pip install -r requirements.txt --break-system-packages   # or use a venv
py seed.py                     # creates dev.db + seeds test data (see below)
py -m flask --app run.py run   # serves on http://127.0.0.1:5000
```
(On Windows, `py` reliably finds your installed Python even when a bare `python`/`python3`/`flask` command gets intercepted by the Microsoft Store shim. On macOS/Linux, use `python3 seed.py` and `python3 -m flask --app run.py run` instead.)

**2. Frontend** (in a second terminal):
```bash
cd frontend
npm install
cp .env.example .env           # defaults to http://localhost:5000, fine if backend runs on its default port
npm run dev                    # serves on http://localhost:5173
```

Open http://localhost:5173 and log in with any account from the table
below. That's the whole setup, no separate database server needed for
testing (it runs on local SQLite); see backend/README.md for pointing it
at real SQL Server later.

## Test accounts

Every account below uses the same password so there's nothing to look up
mid-test. **These are test-only accounts**, `seed.py` deliberately skips
the forced-password-change step for them; a real admin-created account
still forces a password change on first login (worth trying with the
super-admin-created-school flow if you want to see that in action).

**Password for every account below: `Password123!`**

| Role | Email | What you'll see |
|---|---|---|
| Platform super admin | `superadmin@platform.example` | Can create/suspend schools (platform-level, not tied to KGSS) |
| School administrator | `admin@kgss.example.sl` | Full access to everything at KGSS |
| Teacher (Math, JSS1) | `teacher@kgss.example.sl` | Own assignment, own marks entry, can message the seeded parent |
| Teacher (English) | `teacher2@kgss.example.sl` | English teacher covering four classes including JSS 1 (can message JSS 1 parents; use a teacher-only account with no class to test the "unrelated parent" block) |
| Principal | `principal@kgss.example.sl` | Results approval, academics, finance view |
| Accountant | `accountant@kgss.example.sl` | Finance module, fee ledgers, payments |
| Exam officer | `examofficer@kgss.example.sl` | Exam scheduling, results review |
| HR officer | `hrofficer@kgss.example.sl` | Staff, leave approval, payroll |
| Librarian | `librarian@kgss.example.sl` | Book catalog, borrow/return |
| Inventory manager | `inventory@kgss.example.sl` | Assets, suppliers, maintenance |
| Transport manager | `transport@kgss.example.sl` | Vehicles, drivers, routes |
| Student (Abdul Sesay) | `student@kgss.example.sl` | Own published result (A, rank 1), own assignment, own invoice (paid) |
| Parent (Abdul's guardian) | `parent@kgss.example.sl` | Abdul's results/attendance/invoice, a welcome message from the admin |

A second student (Isata Koroma, F grade, unpaid invoice, absent today) has
no login of her own, she exists so you can confirm things like "student 1
can't see student 2's data" stay true. Beyond these two, every class has
30 realistically-named students (180 total across all six classes, split
across each class's two sections), enough for rosters, class attendance
reports, and class rank to show real numbers instead of one or two rows.

Every class also has a full Monday-Friday timetable, five subject
periods a day plus a lunch period, all conflict-free. Five subjects
(Math, English, Science, Social Studies, French) each have two real
teachers so no one is double-booked and at least one teacher genuinely
teaches four different classes across a single day, worth checking a
teacher's timetable to see this directly.

**What's already sitting there waiting for you to look at it**: a
computed and published exam result, a paid invoice and an unpaid one, a
pending leave request, a processed payroll run, a discipline record
(positive recognition), a library loan in progress, an inventory item, a
transport route with two stops and one rider, a school-wide announcement,
and a message in the parent's inbox. You shouldn't need to create
anything just to see what each screen looks like with real data.

## Build order / phase status

1. **Foundation + Core SIS**, multi-tenancy, auth, RBAC, school setup,
   students, guardians, staff, academic structure, enrollment. Done.
2. **Attendance + Timetable**, configurable statuses, bulk marking,
   reports; timetable with teacher/room/class conflict detection. Done.
3. **Assignments + Learning Materials**, draft/publish workflow,
   submissions, grading, server-side student/parent self-scoping. Done.
4. **Exams + Grading + Results + Report Cards**, configurable grade
   scale, marks entry, full draft→teacher_submitted→exam_officer_review→
   principal_approved→published approval workflow, report card assembly.
   Done.
5. **Finance**, fee structures, student ledgers, invoices, payments,
   receipts, expenses, financial reports. Done, including a self-scoping
   security gap found and fixed during testing (see backend/README.md).
6. **Communication**, direct messaging (with a real relationship check,
   not just role-based access), announcements with audience targeting,
   event-driven notifications. Done, three real gaps found and fixed
   while building it (see backend/README.md gap-fix pass #3): staff/
   guardian accounts couldn't be linked to logins, TeacherAssignment had
   no API routes, and there was no way to look up a valid message
   recipient outside the admin user list.
7. **HR/Payroll**, leave requests (with staff self-scoping) and payroll
   runs/payslips. Done, including catching and fixing a self-scoping bug
   introduced in the same phase.
8. **Discipline**, incidents, warnings, positive recognition, resolve/
   follow-up workflow. Done. Deliberately staff-only visibility for now
   (see backend/README.md), whether students/parents should see their
   own records directly is a policy call, not a technical one.
9. **Library**, book catalog, borrowing/returns with copy tracking, and
   overdue fine calculation. Done.
10. **Analytics**, dashboard overview, enrollment trends, attendance
    trends, academic performance (class + subject level). Done, this
    phase's testing also caught and fixed two real bugs left over from
    earlier phases (see backend/README.md): a shadowed-import bug that
    silently broke mark entry, and a missing grade-scale auto-seed that
    could leave results permanently ungraded depending on click order.

A full sweep from Phase 1 through Phase 10 (gap-fix pass #6) found the
same staff-attribution bug in Materials that had already been fixed in
Assignments/Marks, plus two structural nesting endpoints (sections,
terms) that trusted a URL parameter without validating it belonged to
the caller's school. Both fixed and verified. See backend/README.md for
the broader, deliberately-not-fully-fixed systemic pattern this pass
also surfaced (structural IDs in request bodies not validated against
the caller's school, low real risk in the single-school deployment
model, but worth a proper decorator-based fix if you ever run multiple
schools from one deployment).

11. **Inventory**, assets, suppliers, and maintenance tracking (item
    status auto-flips when maintenance is logged). Done.
12. **Transport**, vehicles, drivers, routes with stops, student
    assignments. Done.

Every module from the original 134-section master spec that maps to a
distinct operational area is now built. The account model was also
explicitly confirmed and completed this round: admin-only account
creation (no self-registration route exists anywhere), with self-service
password change and profile updates (name/phone/photo) available to
everyone once their account exists.

A gap-fix pass was done after Phase 3 (see backend/README.md) covering
logout/session management, email verification, audit logs, CSV
import/export, pagination consistency, and basic rate limiting/security
headers, worth another such pass once Finance is in, before moving on to
the remaining modules.

## Deploying (GitHub + Supabase + Render + Netlify + UptimeRobot)

The full step-by-step guide is in **[DEPLOYMENT.md](DEPLOYMENT.md)**. In short:

- `cd backend`, then `py preflight.py --secrets` makes your two secret keys, and
  `py preflight.py --env-file .env.production --test-upload` checks your database, file storage and settings
  from your own computer before you deploy anything. `.env.production` is git-ignored.
- On its first start against an empty database the app creates every table itself. Later releases that add
  columns are applied automatically on start (look for "Auto-migration added N missing column(s)" in the log).
  Take a Supabase backup before deploying a release that changes the database.
- **Demo data on a deployed site:** set `SEED_DEMO_ON_BOOT=1` and a private `DEMO_PASSWORD` on Render. The first
  start (only against a database with no school) loads the demo school, and every demo account uses your
  `DEMO_PASSWORD`. The app refuses to seed a real deployment with the public password above, and refuses to seed
  at all without `DEMO_PASSWORD`. Remove `SEED_DEMO_ON_BOOT` once it has finished.
- **No demo data:** leave those two unset and run `py -m flask --env-file .env.production --app run.py create-superadmin`
  once from your computer. It creates only a platform owner login, who then creates the real school.
- The app refuses to start in production with default keys, a missing `CORS_ORIGINS`, or a missing
  `DATABASE_URL` (which would otherwise silently use a SQLite file that Render erases on every redeploy).
- `/api/health` answers instantly and `/api/health/db` also checks the database. Point UptimeRobot at the second
  one every 5 minutes: it keeps the free Render server awake and the Supabase project active, and emails you
  if either goes down.
- `backend/sql/` is for SQL Server only. Not needed on Supabase Postgres.

## October 2026 changes

- **Payroll**: creating a run fills it at once, one payslip per current employee, from their standing salary (so Staff and Total net pay are never blank). Until a run is marked paid, HR can edit any payslip, remove someone from that month, or add them back. A raise or cut is made on the staff record (Staff page, pencil icon) or ticked on a payslip as "their salary from now on", and the next run starts from it. Staff who are deleted or marked "Left the school" are taken off unpaid runs automatically and can never be paid. Staff only see their own payslips once paid.
- **Library**: the librarian chooses the loan length when lending (standard, a few presets, any number of days, or a date). The principal sets the school-wide standard loan period and fine per late day (Library, "Loan rules and fines"); a book can carry its own. When a late book is taken back the fine is worked out automatically and the librarian can reduce or waive it with a reason, which is recorded.
- **Assignments**: private to the teacher who sets them. Only that teacher can see submissions and grade. The principal has a read-only overview of every teacher's published assignments (who set them, who has handed in, marks), but never what students wrote, and cannot grade, change, extend or delete. Teachers can only set work for the class and subject pairs they teach (a teacher may teach several subjects). An assignment closes after its due date and students cannot hand in; the owner can extend or reopen it, and the class is told the new deadline.
- **Names**: students, guardians and staff cannot change their own names. An administrator edits them (pencil or "Edit name" on the record) and the person's login follows.
- **Exports**: Excel only (the CSV student export was removed; CSV import is unchanged).
- **Notifications**: clicking one marks it read and closes the list; tapping outside, pressing Escape or changing page also closes it.
- **SQL Server**: `backend/sql/schema.sql` was brought up to date with the models. For an existing database, run `backend/sql/upgrade_2026_10.sql` once (safe to repeat).
