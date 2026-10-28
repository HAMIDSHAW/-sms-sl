# School Management Platform, Phase 1 + Phase 2

A working backend covering Phase 1 (Foundation + Core SIS: multi-tenancy,
auth, RBAC, school setup/settings, students, guardians, staff, academic
structure, enrollment) and Phase 2 (Attendance + Timetable, plus the
authentication gaps found after Phase 1 was reviewed: forgot/reset-password
and real enforcement of forced password changes). Everything below has been
run and verified, not just written, see "What was tested."

Currently built for a **single school per deployment**, one school's data
per database/instance, not a shared multi-school SaaS. The tenancy code
(`school_id` on every table, `scoped_query()`) is still there and doesn't
get in your way; it just means you'll only ever have one row in `schools`.
If another school wants it, standing up a new database + a fresh deploy
pointed at it is the intended path, per your call.

## Why it's built this way

- **Multi-tenant from row one.** Every school-owned table carries a
  `school_id`. Every route filters through `scoped_query()`
  (`app/utils/tenancy.py`), which takes the school ID from the caller's JWT
 , never from the request body. This is what makes cross-school data leaks
  structurally impossible rather than "policy we have to remember."
- **RBAC is real, not decorative.** Permissions are granular strings
  (`students.create`, `results.publish`, etc., see `DEFAULT_PERMISSIONS` in
  `app/models/auth.py`), baked into the JWT at login so every request can
  authorize without extra DB round-trips. `school_owner` and
  `school_administrator` get wildcard (`*`) access; every other role
  (principal, teacher, accountant, student, parent) gets only what's listed.
  Schools can add custom roles later without touching code.
- **Nothing about a specific school is hard-coded.** Name, logo, motto,
  address, currency, terminology, and student-ID format are all fields on
  the `School` row, editable any time via `PATCH /api/school` (confirmed
  working in testing, see below). The seed data uses Kenema Government
  Secondary School purely as realistic placeholder content; a real admin
  can rebrand it in one API call.
- **SQLAlchemy models AND raw SQL Server DDL are both provided**
  (`sql/schema.sql`), since you work directly in SSMS. They describe the
  same schema, use whichever fits your workflow; the ORM's `db.create_all()`
  is there for quick local dev.

## Project layout

```
app/
  config.py          # env-driven config (SQLite fallback for dev, SQL Server for prod)
  extensions.py       # db, bcrypt, jwt, cors singletons
  models/
    school.py         # School (tenant root)
    auth.py            # Permission, Role, User + DEFAULT_PERMISSIONS/DEFAULT_ROLES
    people.py          # Student, Guardian, StudentGuardian, Staff
    academics.py        # AcademicYear, Term, SchoolClass, Section, Subject, TeacherAssignment, Enrollment
  routes/
    auth.py            # login / refresh / me / change-password / forgot-password / reset-password
    platform.py         # super-admin: create/suspend schools
    schools.py          # school setup wizard + settings (rename, logo, etc.)
    students.py, guardians.py, staff.py, academics.py, enrollments.py, users.py
    attendance.py        # configurable statuses, bulk marking, student/class reports
    timetable.py          # CRUD with teacher/room/class conflict detection
  utils/
    tenancy.py          # scoped_query(), permission_required(), must_change_password enforcement
    rbac_seed.py         # idempotent permission/role seeding
    ids.py               # student ID generation (school-configurable format)
sql/schema.sql        # SQL Server DDL, mirrors the models exactly (Phase 1 + 2)
seed.py               # seeds one demo school (KGSS) + core academic data
run.py                # entrypoint + `flask init-db` / `flask seed-demo` CLI commands
requirements.txt
.env.example
```

## Running it locally

```bash
pip install -r requirements.txt --break-system-packages   # or use a venv
cp .env.example .env                                        # edit as needed

# Quick local run against SQLite (no SQL Server needed):
python3 seed.py                # creates dev.db + seeds the demo school
FLASK_APP=run.py flask run
```

Seeded logins (all `must_change_password=True`, force a reset on first
real login):
- Platform super admin: `superadmin@platform.example` / `ChangeMe123!`
- School administrator (KGSS): `admin@kgss.example.sl` / `ChangeMe123!`

## Running against real SQL Server

Set `DATABASE_URL` in `.env`, e.g.:
```
DATABASE_URL=mssql+pyodbc://USER:PASSWORD@HOST:1433/SchoolPlatform?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```
Then either run `sql/schema.sql` directly in SSMS, or run `flask init-db`
to let SQLAlchemy create the tables from the models (schema.sql is
recommended for production since you can review/adjust it in SSMS first).

## What was tested (in this container, against SQLite)

**Phase 1:**
1. App factory boots, all blueprints register with no import errors.
2. `seed.py` runs clean and creates: 1 school, core academic structure,
   2 staff, 2 students with linked guardians and enrollments.
3. Full login → JWT → RBAC-checked request flow works.
4. `PATCH /api/school` actually renames the school and sets a logo URL.
5. Created a second school and confirmed tenant isolation (0 cross-school
   data leakage, distinct identity per school).

**Phase 1 gap-fix (found on review, fixed before moving to Phase 2):**
6. `must_change_password` is now actually enforced, a flagged user gets
   403'd on every protected endpoint except change-password, until they
   change it, verified with a live request against `/api/students`.
7. Forgot-password → reset-password flow tested end to end, including
   confirming a used token cannot be replayed (second attempt returns
   "Invalid or expired reset token").

**Phase 2:**
8. Attendance: seeded default statuses, bulk-marked a class's attendance
   for a date, confirmed the class report returns the correct percentage
   (1 present / 2 marked = 50%) and the student report correctly shows 0%
   for the student marked absent.
9. Timetable conflict detection, tested all four cases: teacher
   double-booked (blocked, 409), room double-booked (blocked, 409),
   same teacher on a different day (allowed), and back-to-back
   non-overlapping periods for the same teacher (allowed).

**Phase 3:**
10. Assignments: created a draft assignment, confirmed a student can't see
    it until published, then confirmed a published assignment appears
    correctly scoped to that student's own enrolled class.
11. Submissions security boundary, the important one: created two
    student login accounts, had student 1 submit their own work, then
    confirmed student 1's submissions list contains only their own row,
    and confirmed student 2 (who hasn't submitted) sees zero rows, never
    student 1's. Also confirmed grading works and updates status to
    "graded".

**Phase 4 (Exams, Grading, Results, Report Cards):**
12. Grading engine: seeded default A-F bands, computed a class's results
    from raw marks, confirmed 85% correctly graded A (pass) ranked 1st,
    45% correctly graded F (fail) ranked 2nd.
13. Full approval workflow (draft → teacher_submitted → exam_officer_review
    → principal_approved → published), confirmed the state machine
    actually rejects out-of-order transitions (tried to approve a draft
    result directly, got a 409), then walked the correct sequence end to
    end.
14. Visibility gate: confirmed a linked student sees zero results before
    publish, and sees their own full result (with remarks, grade,
    position) immediately after publish.
15. Report card assembly: pulled a full report card (school info, student
    identity, every subject's marks/grade, overall summary) for a
    published result and confirmed every field populated correctly.

**Phase 5 (Finance):**
16. Full billing lifecycle: created a fee category and structure, bulk-
    generated invoices for every student in a class in one call (2
    students → 2 invoices), made a partial payment and confirmed the
    invoice correctly moved to "partially_paid", then paid the remainder
    and confirmed it moved to "paid" and the ledger balance hit exactly 0.
17. Refund flow: refunded a fully-paid payment and confirmed the invoice
    correctly reverted to "unpaid", status is always re-derived from
    live payments, never hand-flipped.
18. **Found and fixed a real security gap during testing**: the student
    ledger endpoint (`/api/finance/ledger/<student_id>`) didn't apply the
    same self-scoping used everywhere else, a linked student account
    could pull a classmate's financial ledger by changing the ID in the
    URL. Fixed and re-verified: the same request now correctly 404s for
    another student's ledger while a student's own ledger still works.

**Phase 7 (HR/Payroll):**
19. Leave request lifecycle: teacher requests leave (correctly starts
    "pending"), admin approves it, re-approving an already-approved
    request correctly refused (409).
20. Payroll lifecycle: created a run, generated a payslip with real
    numbers (base 2,000,000 + allowances 200,000 − taxes 150,000), and
    confirmed the computed net salary was exactly 2,050,000. Marked the
    run paid and confirmed the payslip status followed.
21. **Found and fixed a self-scoping bug introduced in this same
    phase**: the teacher role was accidentally given both
    `hr.leave.request` (intended: request your own leave) AND
    `hr.leave.view` (intended: HR/admin-only, see everyone's leave) -
    the second one defeated the self-scoping check entirely. Verified the
    bug directly (a second teacher could see the first teacher's leave
    request), fixed the role definition, and re-verified the same request
    now correctly returns empty.

**Phase 8 (Discipline):**
22. Full incident lifecycle: teacher reports an incident (correctly
    attributed to their own linked staff record), teacher tries to resolve
    it directly and is correctly refused (403, resolution is admin/
    principal territory), admin resolves it and the follow-up staff
    attribution records correctly.
23. Positive recognition tested as its own category, the spec's "support
    positive recognition rather than only punishment" isn't just a comment
    here, `positive_recognition` is a real category with no severity
    required.
24. Cross-school validation (from gap-fix pass #5's pattern) applied from
    the start this time rather than needing a follow-up fix: tried
    creating a discipline record against another school's student and
    got a clean 404.

## Where discipline visibility to students/parents stands

Deliberately staff-only for now, `discipline.view` is not granted to the
student or parent roles. Whether a student should see their own
disciplinary record directly in a self-service portal (versus only
through a phone call or meeting with the school) is a school-policy
question, not just a technical scoping one, so I left it as an explicit
decision to revisit with you rather than silently picking either default.

**Phase 9 (Library):**
25. Full circulation lifecycle: created a book with 1 copy, borrowed it
    (available copies correctly dropped to 0), a second borrow attempt on
    the same book correctly refused (409, no copies left), returned it
    on time (fine correctly 0, copy correctly restocked to 1).
26. Overdue + fines: borrowed again, backdated the due date to 3 days
    past, confirmed it showed up in the overdue list, returned it and
    confirmed the fine calculated correctly (3 days × Le 500 = Le 1,500).
27. Self-scoping and cross-tenant validation applied from the start,
    following this session's established pattern: a linked student sees
    only their own borrow history (and can't see another's by passing
    their ID in a filter, it's silently ignored, not honored or leaked),
    and borrowing a book that belongs to a different school is correctly
    refused with 404.

**Phase 10 (Analytics):**
28. Dashboard overview, enrollment-by-class, and attendance-trend endpoints
    all verified against real data (marked attendance, confirmed the
    day's percentage and the 14-day trend both computed correctly).
29. Academic performance analytics verified with a deliberately uneven
    dataset (one student at 90%, one at 40%, across two subjects) -
    confirmed correct average (65%), highest/lowest, and pass rates at
    both class and subject level.
30. **Found and fixed a real bug while testing this phase, introduced
    during gap-fix pass #4**: the earlier fix that made mark-entry derive
    `entered_by_staff_id` from the caller's own staff record left a
    redundant inline `from app.utils.tenancy import current_user` inside
    the function, which shadowed the top-level import and broke mark
    entry entirely (`UnboundLocalError`), a bug that regression sweeps
    hadn't caught because they only checked read (`GET`) endpoints, not
    this specific `POST` flow. Found immediately when trying to build
    academic-performance analytics on top of mark data. Fixed in both
    `marks.py` and the identical pattern in `assignments.py`.
31. **Found and fixed a second real gap in the same testing pass**:
    `compute_results()` never ensured a school's grade scale existed
    before computing, it depended on `GET /api/grading/scale` having
    been called first to lazy-seed the default A-F bands. A school that
    computed results via the API without ever loading the grade-scale
    settings screen got every result silently ungraded (`grade=None,
    is_pass=None`), which then made every pass-rate calculation
    downstream (including the new Analytics endpoint) silently wrong.
    Fixed: `compute_results()` now seeds the default scale itself if none
    exists, verified by computing results *without* ever touching the
    scale endpoint first and confirming grades and pass rates came out
    correct.

**Phase 11 (Inventory):**
32. Full asset lifecycle: created a supplier, created an item linked to
    it, logged a maintenance event (confirmed the item's own status
    correctly flipped to "under_maintenance" as a side effect, not just
    the maintenance record existing on its own), restored it to service.
33. Cross-school validation applied from the start: an item creation
    referencing another school's supplier correctly 404s.

**Account model + self-service profile (explicit confirmation requested):**
34. Confirmed there is no self-registration route anywhere in the API -
    every account is created by an admin via `POST /api/users`. Verified
    directly: `POST /api/auth/signup` and `POST /api/auth/register` both
    404 (they don't exist).
35. Added `PATCH /api/auth/me`, a user can update their own name, phone,
    and photo without needing an admin permission, but cannot touch their
    own email, roles, or active status through this route (verified: sent
    both in the same request, both silently ignored, original values
    unchanged). This was genuinely missing before, the only self-service
    action available was changing your password.

**Phase 12 (Transport, final phase from the original spec):**
36. Full lifecycle: created a driver, a vehicle linked to that driver, a
    route linked to both, added two stops in order, assigned a student to
    the route/stop. Duplicate assignment to the same route correctly
    refused (400).
37. Self-scoping verified: a linked student sees only their own transport
    assignment. Cross-school validation verified: assigning a student
    from a different school to this school's route correctly 404s.

## Gap-fix pass #7 (live-testing bug report)

Shaw ran the seeded app himself across every role and reported a large,
specific list of real bugs. Fixed in this pass:

- **Root cause of most "blank page"/"empty dropdown" reports**: every
  academics endpoint (browsing classes/subjects/years AND creating them)
  required the same `academics.manage` permission, which only admin-tier
  roles had. Split into `academics.view` (all GET routes, granted
  broadly) and `academics.manage` (mutations only, unchanged). This alone
  explained the teacher's empty class dropdown in Mark Attendance and
  Timetable, and several other roles' blank academic-data screens.
- **Cross-user stale state**, "if one user is last using this dashboard
  when other user logs in they will see that dashboard that was last
  seeing." Root cause: client-side navigation after login/logout let
  component state persist across users. Fixed by forcing a full page
  reload on both login and logout, guaranteeing no component in the tree
  can carry another user's fetched data.
- **Superadmin's fundamentally broken experience**, they have no
  `school_id`, so nearly the entire school-scoped app was inapplicable
  (blank/403 everywhere). Built a dedicated Platform Admin view
  (list/create/suspend schools) and routed platform-level accounts there
  directly instead of the normal dashboard.
- **Timetable data exposure**, a student could browse any class's
  schedule via a full dropdown (unlike attendance/results/invoices, this
  endpoint never got a self-scoping pass). Backend now resolves the
  caller's own enrollment and ignores any class_id override; frontend
  drops the picker entirely for student/parent and auto-loads their own.
- **Mark Attendance UI shown to students/parents**, they'd land on the
  teacher's class-marking screen. Now shows a simple read-only "my
  attendance" view instead.
- **Missing HR frontend entirely**, backend leave/payroll routes existed
  since Phase 7 but had zero UI. Built a Leave + Payroll page.
- **Ungated create buttons**, "Add student" and several other
  create/manage buttons were shown to every role regardless of
  permission (backend correctly 403'd, but the button appearing at all
  was misleading, and specifically raised the concern "it looks like all
  staff can add a student"). Gated Students, Academics, Inventory,
  Transport, and Discipline creation UI behind the same permission the
  backend requires.
- **Audit logging was silently writing nothing**, `record_audit()` only
  calls `db.session.add()`, relying on the caller to commit afterward
  (matches the existing pattern in every other call site). My new
  student-creation call site was missing that second commit, so the log
  row was added to the session and then discarded at request end,
  silently. Fixed, and audited every other call site to confirm none had
  the same bug. Also discovered there was no viewing endpoint for audit
  logs at all, write-only logging is nearly useless, so built
  `GET /api/audit-logs` (filterable by entity) plus an Activity tab on
  the student profile page, gated behind a new `audit.view` permission.
- **No edit capability for classes/subjects**, add-only before; the
  PATCH routes already existed, just had no frontend UI. Added an edit
  modal.
- **No click-through from a guardian to their children**, `Guardian.to_dict()`
  was missing `first_name`/`last_name`/`photo_url` entirely (only a
  combined `full_name` string), which also broke building a guardian
  avatar. Fixed the serializer and built a GuardianProfile page.
- **Principal missing view permissions** for materials, assignments,
  library, inventory, transport, added.
- **Global error boundary** added around routed content, so one crashing
  page shows a fallback instead of blanking the whole app, a real risk
  given how many "blank page" reports came in, some of which may have
  been genuine render crashes rather than permission 403s.
- **Avatars** added to Students/Staff/Guardians list rows (initials, or
  photo if `photo_url` is set).
- **Password show/hide toggle** built as a reusable component, wired
  into Login and Change Password.
- **Seed data**: added timetable entries for JSS1 across the week (was
  the one module with zero seed data, called out explicitly).
- **A real architectural note for future updates**: `ensure_system_roles()`
  only sets a role's permissions at creation time, if `DEFAULT_ROLES`/
  `DEFAULT_PERMISSIONS` gains new entries later, an already-existing
  school's roles are never retroactively updated. Not a bug in this
  release (a fresh `seed.py` run always gets the current definitions),
  but worth knowing before making permission changes against a
  long-running production database, a migration script would need to
  diff and add missing permissions to existing roles.

## Gap-fix pass #8 (post-fix deep verification)

After pass #7, ran actual workflows end-to-end (not just endpoint
availability) and did a precise cross-reference of every role's visible
nav items against their backing endpoints, rather than just checking
"does this return 200" in isolation. Found and fixed:

- **Suspending a school did nothing**, a school marked suspended via
  Platform Admin still let every one of its users log in with full
  access; the flag was set but never checked anywhere. Fixed at both
  login and token-refresh, so a suspended school is actually locked out,
  not just cosmetically flagged. Confirmed: login blocked while
  suspended, an in-flight refresh token also blocked, both work again
  immediately on reactivation, and the platform-level super-admin login
  is unaffected (they have no school to suspend).
- **Parent was missing `timetable.view` entirely**, a parent couldn't
  see their child's class schedule at all (nav item correctly hidden,
  so not a visible blank page, but a real missing capability). Added,
  and confirmed the self-scoping fix from pass #7 correctly resolves it
  to the child's own class.
- **Student and parent were missing `exams.view`**, they could see
  their own results (`results.view`) but not the exam schedule itself
  (dates, subjects, rooms) since that's a separate, narrower permission.
  Confirmed the underlying route only returns exam metadata, no other
  student's marks, so granting it broadly is safe. Added to both roles.
- **Principal was missing `parents.view`**, inconsistent with the
  role's otherwise-broad oversight (finance, HR, inventory, transport)
  to not be able to look up a guardian's contact info. Added.
- Verified the full HR workflow end-to-end: teacher requests leave → HR
  officer approves → status updates correctly; HR creates a payroll run
  → teacher (no payroll.manage) sees only their own payslip.
- Verified the AcademicsAdmin edit feature (class/subject rename) works
  end-to-end via the actual PATCH routes.
- Verified full tenant isolation on a freshly-created second school via
  Platform Admin: zero students/staff/classes visible from the seeded
  KGSS data, confirming `scoped_query` correctly isolates by school_id
  even for a brand-new tenant.
- Ran a precise sweep, for every one of the 11 non-wildcard roles,
  checking specifically "is this nav item visible to this role, and if
  so does its backing endpoint actually return 200", rather than
  flagging every 403 (most are correct permission boundaries, e.g. a
  teacher correctly can't see Finance and correctly doesn't see that nav
  item either). After the two permission additions above, this comes
  back completely clean across all 11 roles.

## Gap-fix pass #9 (root-cause fixes from continued live testing)

Shaw kept testing against the previous package and reported the same
permission errors persisting despite earlier fixes, plus new issues
found through actual use. Root-caused and fixed:

- **THE core bug**: `ensure_system_roles()` only set a role's
  permissions the first time it was created, if the role already
  existed in the database, it was left untouched forever, even after
  `DEFAULT_ROLES` changed in the code. This meant **every permission fix
  made earlier in this project may have silently never reached an
  already-running installation** unless the database was fully wiped.
  Confirmed this was very likely the actual explanation for 403s Shaw
  was still seeing on endpoints already "fixed" in earlier passes. Fixed
  two ways: (1) `ensure_system_roles`/`ensure_super_admin_role` now
  re-sync a role's full permission set on every call, not just at
  creation, and (2) this sync now runs automatically on every backend
  startup (in `create_app()`), not only when `seed.py` is run manually.
  Verified by deliberately corrupting a role's permissions in the
  database and confirming a plain app restart, no reseed needed -
  repaired it.
- **Dropdowns rendering behind other content instead of in front** -
  found the cause: both the page-transition wrapper (`AppShell.jsx`) and
  the `Modal` component animated position via CSS `transform`
  (`framer-motion`'s `y`/`scale`), and that transform is left applied
  indefinitely even after the animation finishes. An ancestor with an
  active `transform` can make Chromium render native `<select>` popups
  incorrectly relative to other content. Removed the transform-based
  motion from both (now a plain fade), which should resolve this for
  every dropdown on every page, not just one screen.
- **Leave requests, discipline records, payslips, library loans,
  transport assignments, and attendance records only stored raw IDs,
  never a resolved name or photo**, exactly the concern that "leave
  requests should show who's asking and their profile." Fixed at the
  model level (`LeaveRequest`, `Payslip`, `DisciplinaryRecord`,
  `BorrowRecord`, `TransportAssignment`, `Attendance` `to_dict()` now
  all include the relevant person's name/photo/position), and updated
  the HR and Discipline screens to actually display it, the Discipline
  table previously didn't even show which student a record was about.
- **No way to add an Academic Year or a Timetable period from the UI at
  all**, the backend routes existed (including real scheduling-conflict
  detection for timetable periods), just had zero frontend UI. Built
  both. Tested end-to-end including conflict detection (double-booking
  the same teacher at an overlapping time correctly 409s with a clear
  message).
- **`timetable.manage` existed as a permission but was never actually
  granted to principal**, despite principal already having
  `academics.manage`. Added, and confirmed a principal can now create
  academic years and timetable periods.

## Gap-fix pass #10 (realistic scale: 180 students, full weekly timetable, multi-class teachers)

Requested: 20-50 students per class, a full timetable (five subject
periods plus lunch, every day) for every class, and teachers who
realistically teach more than one class.

- **Rewrote `seed.py`'s student generation**: 30 students per class (180
  total across all 6 classes) instead of 2. The two original named
  students (Abdul Sesay, Isata Koroma) stay first in JSS 1 with all their
  existing rich demo data (published result, invoice, attendance,
  discipline record, library loan, transport assignment), everything
  else is realistic Sierra Leonean names drawn from name pools, split
  evenly across each class's two sections. Idempotent by *count* per
  class rather than by name (repeated names across 180 students are
  expected and realistic, the student number is the real unique
  identifier), confirmed running `seed.py` twice still leaves exactly
  180 students, 180 enrollments, 180 timetable entries, nothing
  duplicated.
- **Added 8 more teaching staff** (no login needed, they're supporting
  cast) so five subjects, Math, English, Science, Social Studies,
  French, each have two real teachers, split so one covers four classes
  and the other covers the remaining two. This is what actually makes
  "a teacher teaches more than one class" true and conflict-free: with
  six classes and only five daily periods, one teacher per subject
  can't cover all six without being double-booked, so this mirrors how
  a real school actually staffs a subject across grade levels (a JSS
  teacher and an SSS teacher, say) rather than one specialist for the
  whole school.
- **Full weekly timetable for every class**: five subject periods a day
  (rotated by a fixed offset per class so the same subject-and-period
  pairing never repeats across classes sharing a teacher) plus a lunch
  period at a fixed time, Monday-Friday, using a real `Subject` row
  ("Lunch Break") rather than a schema change, six periods × five days
  × six classes = 180 timetable entries total.
- Verified directly, not just assumed: wrote a standalone conflict
  checker across every staff member's full week and confirmed **zero
  double-booking conflicts** anywhere in the seeded schedule. Also
  confirmed concretely, e.g. the seeded Math teacher teaches four
  different classes on a single Monday (JSS 1, JSS 2, JSS 3, SSS 1) at
  four different times, with zero overlap.
- Re-ran the full 39-endpoint regression, all 13 logins, and confirmed
  student/parent self-scoping still correctly isolates the showcase
  student's own 30-period timetable and single result from the other
  179 students now in the database. Pagination confirmed correct at
  180 students (12 pages of 15).

## Gap-fix pass #11 (dashboard, parent scoping, timetable editing, staff data)

- **Settings page was completely missing**, the sidebar linked to
  `/settings` but no route or page component existed at all, which is
  exactly why it showed blank. Built a real settings page wired to the
  `PATCH /api/school` endpoint that already existed.
- **Two dashboard cards were hardcoded to the literal string "N/A"** -
  "Attendance today" and "Open assignments" never fetched real data at
  all, which is exactly the "wrong analysis" bug reported. Fixed with
  real, correctly self-scoped data: attendance uses the existing
  `GET /api/attendance?date=` filter (already self-scoped per role), and
  open assignments is computed from the caller's own already-scoped
  assignment list. Replaced the "Quick start" boilerplate paragraph with
  a real "due soon" list drawn from that same data.
- **Parent dashboard over-exposure**, parent had `library.view`, which
  is genuinely not "their child's data." Removed. Also found and fixed a
  correctness bug: a guardian with more than one child could only ever
  see the *first* linked child's timetable (`guardian_children[0]`
  hardcoded) with no way to pick another. Added a proper child selector
 , `GET /api/students/my-children`, a `resolve_guardian_selected_child()`
  helper that validates any requested `student_id` against the caller's
  own children before trusting it, and a switcher in the sidebar that
  appears only when a parent actually has more than one child.
- **Timetable now shows the teacher's name for every period**, not just
  the subject, a real, immediately-noticeable gap. Also added edit and
  delete for existing periods (the backend routes already existed with
  full conflict re-checking; there was just no UI for it).
- **Staff data**: found that `first_name`/`last_name`/`photo_url` were
  never included in `Staff.to_dict()` at all, which silently broke the
  avatar-initials fallback everywhere staff are listed. Fixed. Added a
  `title` field (Mr/Mrs/Miss/Madam/Dr) that now flows through
  `full_name` everywhere a staff member's name is shown (leave requests,
  payslips, discipline records, attendance). Seed data now gives every
  staff member a title and a real phone number, the phone column
  existed in the UI already, it just had nothing to display.
- Updated the run commands here to `py seed.py` / `py -m flask --app
  run.py run`, which is what's actually been reliable on Windows.

**Known schema change**: this pass added a `title` column to the staff
table. If you're upgrading an existing `dev.db` rather than starting
fresh, delete it and re-run `seed.py`, SQLite's `create_all()` only
creates missing tables, not missing columns on ones that already exist.

## What I did NOT get to in this pass, flagged honestly

This round of feedback included a lot more than the above, and I don't
want to claim more than what's actually done and tested:

- **The reported crashes on Assignments/Exams/Messages/Announcements/
  Discipline/Inventory/fee ledger**, I reviewed the relevant page code
  carefully and found no static bug (all handle missing/empty data
  safely). Combined with the backend logs showing every one of those
  requests actually succeeding (200) right before the error screen
  appeared, my best diagnosis is a stale Vite dev-server / HMR state
  after a very long single `npm run dev` session across dozens of file
  edits, not a code defect I can find by inspection. Worth trying: stop
  the frontend dev server fully (Ctrl+C), delete `frontend/node_modules/.vite`,
  restart `npm run dev`, and hard-refresh the browser (Ctrl+Shift+R).
  If it still happens after a clean restart, that would tell us it's a
  real code bug, and the browser's dev console (F12) would show the
  actual JavaScript error, that detail would let me find it directly
  instead of guessing.
- Per-period attendance (each teacher marking their own period,
  separate from a homeroom "class master" whole-day check), not
  started; this is a real structural change to the attendance model,
  not a small fix.
- Materials seeded for every subject/class level, more library books,
  more leave/payroll history, driver profiles, not done.
- Real file-upload for profile photos (currently URL-only) and Excel
  (as opposed to CSV) export, not done; both need new infrastructure
  (file storage for the former, an XLSX-writing dependency for the
  latter) rather than a quick fix.

## Gap-fix pass #12 (confirmed frontend bugs found via exhaustive code review)

Went back through the reported crashing pages (Assignments, Exams/Results,
Messages, Announcements, Discipline, Inventory, fee ledger) far more
rigorously than the previous pass. Found and fixed **real, confirmed
bugs** in four of the seven:

- **Discipline, Inventory, the student fee ledger, and Results-for-exam
  all called `.replace('_', ' ')` directly on a status/category field
  with no null-guard** (e.g. `r.status.replace(...)`). Every current
  backend code path happens to always populate those fields, so this
  wasn't reproducible from fresh seed data, but it's a real, live crash
  risk the moment any record ever has an empty value there (including,
  plausibly, leftover data from an earlier version of this project
  before some of these fields had defaults, sitting in an existing
  `dev.db`). Fixed all six instances with a `(value || 'unknown')`
  guard, plus one more in the student profile Activity tab found by the
  same search.
- For **Assignments, Messages, and Announcements**, went through the
  complete source of each line by line, and separately confirmed the
  shared `Table`/`Badge`/`Modal` components used everywhere are safe
  with missing data (`Badge`'s `tone` prop falls back to `'slate'` via a
  JS default parameter even when a status lookup misses). Found no bug.
  Since `npm run build` completes cleanly, there's no syntax-level issue
  either. If this recurs, the browser console (F12) on the broken page
  will show the exact error and line, that's the fastest way to close
  this out for good rather than guessing further.
- **Materials now seeded for every subject, in every class** (30 total -
  5 core subjects × 6 classes), each attributed to whichever teacher
  actually teaches that subject in that class per the timetable, not
  just the one original Math note.
- **Library catalog expanded to 15 books** across literature, math,
  science, and reference, with two active loans instead of one.
- **Leave requests and payroll expanded**: 5 leave requests across
  different staff and every status (pending/approved/rejected), and
  3 months of payroll history with every one of the 17 staff members
  paid in each run (51 payslips total) instead of one staff member in
  one run.
- **Driver profiles**: added `photo_url` and `address` to the driver
  record, a `GET /api/transport/drivers/<id>` detail endpoint (returns
  the driver's assigned routes too) and a matching `PATCH` for editing,
  a real profile page with a photo/initials avatar, and a second driver
  on the roster so the list isn't just one row.

## Gap-fix pass #13 (per-period attendance, class masters, Excel export)

- **Per-period attendance, for real**, the model already had a nullable
  `subject_id` on `Attendance` supporting this, but the actual marking
  workflow only ever produced one blanket daily mark. Rebuilt the
  workflow: a teacher's Mark Attendance screen now shows *their own*
  timetable periods for today (`GET /api/timetable/mine`) and they mark
  each one separately, so a student's daily record is built from every
  period they were actually in, not one guess for the whole day.
- **Class masters**, added `class_master_staff_id` to the class model.
  A class's homeroom teacher gets an additional whole-day check on top
  of the per-period marks, which is how "did this student attend the
  whole day" actually gets answered rather than inferred from one
  subject. **Confirmed the principal can assign this** (they already
  have `academics.manage`) via the class edit form, tested directly:
  principal successfully reassigns a class's head, a teacher attempting
  the same is correctly blocked with a 403.
- **Found and fixed a real staff-attribution spoofing bug while
  building this**: the attendance-marking endpoint trusted a
  client-supplied `marked_by_staff_id` with no validation, any teacher
  could attribute their marking to a different staff member entirely.
  Fixed: it's now always resolved from the caller's own linked staff
  record, with a client-supplied override honored only for wildcard
  (admin) accounts making a correction on someone else's behalf.
  Verified directly: a spoof attempt with a fabricated staff id is
  silently ignored and the real caller's own id is saved instead.
- **Real Excel export**, written with the Python standard library only
  (`app/utils/xlsx_export.py`: zip plus XML), with a styled header row,
  frozen header and auto-sized columns. It replaced an `openpyxl`
  version that returned a 500 on any machine where `pip` could not
  download that package. Verified by loading the generated file back
  with `openpyxl` as an independent reader.

## Gap-fix pass #14 (the actual root cause of recurring "pages don't load")

Shaw sent a server traceback showing the real error behind the latest
round of broken pages: `no such column: classes.class_master_staff_id`
and `no such column: staff.title`. This is **not a frontend bug** -
every previous schema change in this project (adding a column to a
model) required deleting `dev.db` and reseeding for an already-running
installation to pick it up, and that was never realistic to expect
someone to remember every time. This is very likely a real contributing
cause of some of the earlier scattered "page won't load" reports too -
many pages depend on Staff or Class data somewhere in their fetch chain,
and a 500 there can cascade.

**Fixed properly, not with another "please delete dev.db" note**: added
`app/utils/auto_migrate.py`, which runs on every app startup (right
before the role-permission sync from pass #9) and compares each model's
declared columns against what the actual SQLite file has, adding any
that are missing via `ALTER TABLE ... ADD COLUMN`. A no-op once schemas
already match, so it costs nothing on a healthy database.

**Verified this rigorously, not just written and assumed correct**:
built a genuinely old-style database by temporarily stripping the two
new columns from the model code, seeding real data into it (a staff
member, a class), restoring the current model code, and confirming a
plain app restart, no reseed, no manual step, both added the missing
columns AND left the pre-existing data completely intact (existing
rows correctly got `NULL` for the new columns, nothing was dropped or
corrupted). This is the scenario Shaw was actually hitting, reproduced
directly rather than inferred.

Ran the full 42-endpoint regression and all 13 logins again after this
fix to confirm nothing else regressed.

## Account model (explicit design confirmation)

Every account, student, parent, teacher, any role, is created by an
admin via `POST /api/users`. There is no self-registration route anywhere
in this API; `/api/auth/signup` and `/api/auth/register` don't exist and
return 404. Once an account exists, the person themself can change their
own password (`POST /api/auth/change-password`) and update their own
phone/photo (`PATCH /api/auth/me`), but **not their own name**. Official
names are locked: `PATCH /api/auth/me` silently ignores `first_name`/
`last_name` even if sent, so a student can never swap in a nickname and
have it diverge from what's on their academic record. Verified directly -
sent a name-change attempt through the self-update endpoint and confirmed
the name stayed exactly what the admin set, while phone updated normally
in the same request. Correcting an official name (e.g. a genuine spelling
mistake) is an admin action only, via `PATCH /api/users/<id>`.

## Final pre-handoff pass

Before handing this off for real testing, did one more clean sweep:

- **Rewrote `seed.py` from a 2-account minimal seed into a full test
  fixture**: one login per role (13 accounts total, see the top-level
  README's test account table), all correctly linked to real Staff/
  Student/Guardian records (not just bare logins), plus real sample data
  in every module, a computed and published exam result, a paid and an
  unpaid invoice, a pending leave request, a processed payroll run, a
  discipline record, an active library loan, an inventory item, a full
  transport route with stops and a rider, an announcement, and a message.
  The goal: open any screen and see something real, not an empty state.
- **Verified idempotency**, ran `seed.py` twice in a row and confirmed
  student/invoice/discipline counts stayed the same rather than
  duplicating.
- **Verified every one of the 13 seeded accounts actually logs in** with
  the correct role and without a forced password change (test-only
  convenience, real accounts still force a change, as tested throughout
  this project).
- **Verified real HTTP end-to-end, not just the Flask test client** -
  started the actual server with `flask --app run.py run` and hit it with
  a raw `curl` login request over the network, confirming the exact
  command in the README works and returns a correct token.
- **Confirmed CORS is configured** (`CORS_ORIGINS=*` on `/api/*`) so the
  frontend can actually reach the backend from a different port.
- Fixed a small deprecation warning (`datetime.utcnow()`) in the new seed
  script while in there.

## What's deliberately NOT built yet

Assignments/learning materials, exams/results, finance, communication, and
every "Operations" module (library, transport, inventory, HR/payroll,
discipline) are scoped for later phases, per the build order, designing
those now, before a real school is using what exists, means designing on
guesses rather than on an actual admin/teacher/parent workflow.

## Gap-fix pass (before Phase 4)

Before starting Phase 4, I audited Phases 1-3 against the master spec and
found real gaps, fixed all of them:

- **Logout/session management (spec §5, §71)**, tokens didn't actually
  revoke before. Now: `POST /api/auth/logout` revokes the current session
  immediately (tested: same token gets a 401 "Token has been revoked"
  straight after), `GET /api/auth/sessions` lists active sessions,
  `POST /api/auth/sessions/<id>/revoke` force-logs-out a specific one.
- **Email verification (spec §5)**, `send-verification` / `verify-email`,
  same one-time-token pattern as password reset. Tested end to end.
- **Audit logs (spec §75)**, `AuditLog` model + `record_audit()` helper,
  wired into student/staff deletion, school settings changes, role
  assignment, and bulk import. Not yet wired into every mutation, see
  gaps below.
- **CSV export/import for students (spec §14, §77-79)**, `GET
  /api/students/export`, `GET /api/students/import/template`, `POST
  /api/students/import`. Tested with a mixed valid/invalid CSV: valid rows
  import, invalid rows are reported by line number, nothing silently drops.
- **Found and fixed a real bug while testing the above**: `seed.py` was
  hard-coding student numbers instead of calling the ID generator, so
  `next_student_seq` never advanced, the very first real CSV import
  collided with a seeded student number. Fixed `seed.py` to use
  `generate_student_number()` like every other code path does.
- **Pagination consistency (spec §126)**, staff and guardian list
  endpoints returned a bare array while students returned a proper
  paginated envelope. Both now match the students pattern.
- **Basic security hardening (spec §88)**, rate limiting on
  login (10/min) and forgot-password (5/min) via Flask-Limiter, plus
  baseline security headers (X-Content-Type-Options, X-Frame-Options,
  Referrer-Policy) on every response.

**Deliberately still not built, flagging explicitly rather than skipping
quietly:** 2FA. It's a materially bigger feature (TOTP secrets, backup
codes, an enrollment flow, enforcement logic) than the gap-fixes above, and
better scheduled as its own task closer to real deployment rather than
folded into a cleanup pass.

## Gap-fix pass #2 (after Phase 5, before Phase 6)

Went looking specifically for the *same class* of bug the ledger fix
caught, self-scoping gaps, rather than a general spec re-read. Found
three real ones:

- **Attendance self-scoping was missing entirely.** `attendance.view` was
  granted to the student role back in Phase 2, but `GET /api/attendance`
  and `GET /api/attendance/reports/student/<id>` never restricted which
  student's rows came back, a student could pass another student's ID in
  the query string/URL and see their attendance. Fixed: both now silently
  substitute the caller's own scope (or their linked child's) regardless
  of what's requested. The class-wide report endpoint now flatly refuses
  self-scoped callers (a student has no legitimate need for whole-class
  aggregates). Verified: requesting another student's attendance now
  transparently returns your own data instead of theirs; the class and
  cross-student report requests both correctly 404.
- **A student had no way to view even their own SIS profile.**
  `GET /api/students/<id>` required the staff-only `students.view`
  permission with no exception, so a student account, which by design
  doesn't hold that permission, couldn't see their own basic info (DOB,
  address, admission date). Fixed: the endpoint now allows a student or
  guardian through for their own (or their child's) record specifically,
  while still requiring `students.view` for anyone else's. Verified.
- **Teachers couldn't actually mark attendance in practice.** The
  frontend's Mark Attendance flow loads the class roster via
  `GET /api/enrollments`, which required `enrollment.manage`, a
  permission the teacher role never had (only school admins/principals
  did). The write operations (create/update enrollment) correctly stayed
  admin-only, but the read got caught in the same permission by mistake.
  Split into `enrollment.view` (now granted to teacher and principal) and
  `enrollment.manage` (unchanged, admin/principal only for actual
  mutations). Verified a teacher account can now fetch a class roster.

**Noted but not fixed, lower severity, flagging rather than silently
skipping:** `staff_id` on assignment/mark-entry creation is taken directly
from the request body rather than derived from the caller's own linked
staff record, so a teacher could technically attribute a mark entry or
assignment to a different staff member's name. This is a data-integrity/
attribution question, not a privacy leak (no student data is exposed by
it), so it's queued behind the results/payment reconciliation test
coverage rather than fixed in this pass.

**Operational note:** role permission changes (like the `enrollment.view`
split above) only apply to newly-created schools/roles, `ensure_system_
roles()` is idempotent and won't retroactively update an already-seeded
school's existing roles. A real multi-school deployment would need a
small "resync roles to current definitions" script; for the current
single-school-per-deployment model this mainly matters if you reseed
rather than wipe and restart, so it's low-urgency but worth remembering.

## Gap-fix pass #3 (during Phase 6 build, before Phase 7)

Went looking for gaps while building Phase 6, since Communication's
messaging feature immediately depended on things that turned out to be
missing:

- **Staff and guardian records could not be linked to login accounts at
  all.** Students got this fix in an earlier pass; staff and guardians
  never did. This silently broke the entire staff/guardian side of any
  self-scoping check (messaging, and anything else that would ever ask
  "is this account linked to this person"). Fixed: `user_id` is now
  editable via `PATCH /api/staff/<id>` and `PATCH /api/guardians/<id>`,
  same as students. Verified by linking two teacher accounts and a parent
  account and confirming the messaging relationship rule (below) actually
  worked once they were linked.
- **`TeacherAssignment` had a model but no API routes at all** (spec
  section 28), found while trying to test the messaging rule, since "does
  this teacher teach this student" depends on it existing. Added list/
  create/delete routes with the spec's "prevent invalid or conflicting
  assignments" enforced via the model's existing unique constraint.
  Verified.
- **No way for an ordinary teacher or parent to find a valid message
  recipient.** The only user-lookup endpoint (`/api/users`) requires the
  staff-only `users.view` permission, so most roles had no way to compose
  a message at all. Added `GET /api/messages/contacts?q=`, deliberately
  *not* a general directory: it only ever returns people `can_message()`
  already permits, so it can't be used to enumerate the school's roster.
  Verified: a teacher searching for "parent" finds the parent of a student
  they teach, and finds nobody when searching as an unrelated teacher.

With those three fixed, the actual Phase 6 feature, the messaging
relationship rule (spec section 56: "a teacher should not automatically be
able to privately message every parent in the school"), was verified
directly: a teacher who teaches a student can message that student's
parent; an unrelated teacher cannot; staff can always message other staff;
a parent can always reach any staff member. Announcement audience
targeting was verified both positively (a parent sees a class-targeted
announcement for their child's class) and negatively (an unrelated teacher
does not see it, only the school-wide one).

## Gap-fix pass #4 (full audit from Phase 1, before Phase 7)

A from-the-beginning audit rather than a Phase-6-specific one. Found and
fixed three more real issues:

- **Invoices and payments, the two tables that will grow largest over a
  school's lifetime, were never paginated**, even though staff and
  guardians got that fix two passes ago. Fixed: both now return the same
  `{items, page, per_page, total, pages}` envelope. Verified.
- **`staff_id` on assignment creation and `entered_by_staff_id` on mark
  entry were flagged as gaps in earlier passes but never actually fixed.**
  A teacher could attribute an assignment or a mark entry to a different
  staff member just by changing an ID in the request body. Fixed: both
  now derive the acting staff member from the caller's own linked staff
  record whenever one exists, ignoring whatever the client sent. Verified
  directly, a teacher account tried to attribute a new assignment to a
  *different* staff member's ID, and the created record correctly showed
  their own staff ID instead.
- **Invoice cancellation had no route.** The model has always supported a
  `cancelled` status; nothing ever set it. Added `PATCH /api/invoices/
  <id>/cancel`, which correctly refuses to cancel an invoice that already
  has successful payments against it (refund those first), verified both
  the allowed and refused cases.

Ran a full regression sweep across all 19 core read endpoints spanning all
six completed phases immediately after, everything still responds
correctly together.

## Gap-fix pass #5 (fresh audit before Phase 8)

A different angle this time: checked whether write endpoints validate that
foreign-key IDs from the request body actually belong to the caller's own
school, not just whether reads are scoped. Found real gaps:

- **`Invoice.student_id`, payslip generation's `staff_id`, attendance
  bulk-marking's `student_id`, and mark entry's `student_id` were all
  taken directly from the request body with no check that they belonged
  to the caller's own school.** In the single-school-per-deployment model
  this mostly can't be reached by a real user, but it's still a
  correctness gap worth closing, an admin API client bug, a stale ID from
  a slow frontend, or ever running multi-school could otherwise silently
  attach one school's financial/academic records to another school's
  student or staff member. Fixed all four to validate against the
  caller's own school and return 404 rather than silently succeeding.
  Verified directly: created a second school with its own student, then
  tried to invoice that student using the first school's admin credentials
 , correctly rejected with 404; a normal same-school invoice still
  succeeds.
- **`LeaveRequest.reviewed_by_staff_id` was in the model and the intent,
  but never actually set** by the approve/reject routes, and, a second
  layer of the same bug, even after setting it correctly, `to_dict()`
  never included it in the response, so the fix would have looked broken
  even once applied. Fixed both: the field is now populated from the
  caller's own linked staff record, and exposed in the API response.
  Verified end to end.

## Gap-fix pass #6 (full sweep, Phase 1 through Phase 10)

Went back through every phase with the two specific patterns this
session's earlier passes had established, checking whether they'd been
applied *consistently* everywhere rather than just where I happened to
look before:

- **Materials had the identical staff-attribution gap assignments and
  marks were fixed for, but never got the fix itself.** A teacher could
  attribute a learning material to a different staff member by changing
  `staff_id` in the request body. Fixed the same way: derived from the
  caller's own linked staff record. Verified directly, a teacher tried
  to attribute a new material to a different staff member's ID, and the
  created record correctly showed their own.
- **Two structural nesting endpoints trusted a URL path parameter without
  validating it belonged to the caller's school**: `POST /api/academics/
  classes/<class_id>/sections` and `POST /api/academics/years/<year_id>/
  terms`. Both now validate the parent (class/year) belongs to the
  caller's school before creating the child row. Verified: creating a
  section or term against another school's class/year now correctly
  404s, while normal same-school creation still works.

**A broader systemic pattern, found but deliberately not fixed
everywhere**: many other `create`/`update` endpoints across this codebase
still take structural IDs (academic_year_id, term_id, class_id,
section_id, subject_id, administrative/scheduling entities, not people)
directly from the request body without validating they belong to the
caller's school (examples: assignment creation's class/subject/term IDs,
exam schedule creation's class/subject/invigilator IDs, timetable entry
creation's class/subject IDs, fee structure creation's class/year IDs,
announcement creation's audience_class_id). I fixed every instance
involving a **person** (staff_id, student_id) across every phase, since
those touch privacy/attribution directly. I did not do a mechanical sweep
of every purely-structural reference, because:
1. In the single-school-per-deployment model this code actually runs in,
   these fields can only ever reference something inside the same
   database anyway, there's no second school's data to leak into.
2. Fixing all of them by hand would mean touching a large fraction of the
   codebase's create/update routes for a correctness edge case (a stale
   ID or an API client bug) rather than a real reachable vulnerability
   in the deployment model you've told me you're using.

If you ever do run multiple schools from one deployment, this is worth a
dedicated pass, ideally as a shared decorator/validator (e.g.
`@validates_fk("class_id", SchoolClass)`) rather than hand-repeating the
same four lines in another dozen routes, which is what created this
inconsistency in the first place.

## Where parent (guardian) account scoping stands

Guardian accounts can be linked the same way (`Guardian.user_id`), and
assignments/materials/results/invoices/payments/attendance/library routes
all scope for guardians via `linked_guardian_children_ids()`, tested
directly for assignments, materials, results, and invoices; the same code
path is used for attendance and library, so it's covered by the same
logic even where a dedicated guardian-specific test wasn't run.



Guardian accounts can be linked the same way (`Guardian.user_id`), and
assignments/materials routes already scope for guardians via
`linked_guardian_children_ids()`, but this hasn't been tested end-to-end
the way the student path was above. Worth verifying before relying on it
for a parent-facing rollout.

## Honest gaps to know about before you rely on this

- **No Alembic/migrations yet**, schema changes currently mean editing
  models + `sql/schema.sql` by hand and re-running.
- **No file upload endpoint**, `logo_url` / `photo_url` are string fields;
  wiring to real object storage is a follow-up once you pick a provider.
- **No email/SMS delivery wired up**, `/api/auth/forgot-password` creates
  a real, single-use, expiring token, but returns it directly in the
  response (`_dev_only_token`) instead of emailing/texting it, since no
  provider is configured yet. Remove that field and wire in real delivery
  before any real user relies on this.
- **No PDF report cards yet**, `/api/results/report-card/<student_id>/
  <examination_id>` returns structured JSON with everything a report card
  needs; rendering that into an actual printable/downloadable PDF is a
  follow-up task (there's a PDF-generation skill available for this when
  we get there). The same applies to `/api/payments/<id>/receipt`.
- **No PDF invoices/receipts**, same story as report cards: structured
  JSON exists and is correct, printable PDF rendering is a follow-up.
- **Library fine rate is a fixed module constant** (Le 500/day), not a
  per-school configurable setting yet, same pattern as the grade scale
  before it was made configurable; worth doing the same treatment if this
  matters to you.
- **No automated test suite**, only the manual smoke tests above. Worth
  adding pytest coverage for the RBAC/tenancy boundary, timetable conflict
  logic, and the results/payment reconciliation logic specifically.


## Fix pass: attendance, finance, HR, parents and logging

- **No more install failures.** `requirements.txt` now lists only what
  the app needs to run and that installs everywhere. Postgres and
  Supabase Storage packages moved to `requirements-prod.txt`. Excel
  export and the period reminder scheduler use only the standard
  library (no `openpyxl`, no `apscheduler`).
- **Activity log.** Every successful create, update or delete is
  recorded automatically with who did it and a plain English summary
  (`app/utils/activity_log.py`). Admin and principal read it under
  *Activity log*. Reads are not logged.
- **Real attendance figures.** `GET /api/attendance/summary` and
  `/overview` count whole-day records only, against enrolled students.
  Dashboards use them. Principal and admin get a school and per-class
  overview instead of the student view. Marking a student absent had a
  latent crash (`status_obj.name`), now fixed.
- **Finance.** Payments record who paid (name, phone, relationship), what
  it was for, and who received it. Invoices can be created by choosing a
  class and then a student, and any class can be billed in one action
  (`POST /api/invoices/bill-class`, safe to press twice).
- **Ownership rules.** Only the teacher who set an assignment can delete
  it. A material can be deleted by whoever shared it, or by admin and
  principal (`materials.moderate`).
- **HR.** Leave approval and payroll (generate payslips, mark paid) are
  visible actions. Staff have a home address and a base salary.
- **Parents with several children.** A banner on every page says which
  child is being viewed. The selected child is sent automatically with
  every child-scoped request, and the server validates it.
- **Class masters** can see the parents of their own class only.
- **Permissions are read at sign in.** After pulling these changes, sign
  out and in again so the new permissions (for example library access
  for more staff, `materials.moderate` for the principal) take effect.


## Security and testing (latest audit)

Full report: `SECURITY-AUDIT.md` at the project root.

Run the automated tests (they use their own temporary database, never `dev.db`):

    py -m pip install -r requirements-dev.txt
    py -m pytest -q

Environment variables added or changed:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY`, `JWT_SECRET_KEY` | Required in production, 32+ characters, different from each other. The app refuses to start otherwise. |
| `CORS_ORIGINS` | Exact frontend URL(s). `*` is refused in production. Local default is `http://localhost:5173`. |
| `TRUST_PROXY_COUNT` | Number of trusted proxies in front of the app (1 on Render) so real client IPs are used. |
| `JWT_ACCESS_MINUTES` | Access token life, default 60. The frontend renews it silently. |
| `RATELIMIT_STORAGE_URI` | Shared store (e.g. Redis) for rate limits when running more than one worker. |
| `EXPOSE_DEV_TOKENS` | Set to `0` to hide the local-only reset token even on your own machine. |
| `ALLOW_DEMO_SEED` | Must be `1` to run `seed.py` in a production setup. Do not. |

Forgotten passwords: Staff page, key icon on a row (administrators), or `POST /api/users/<id>/reset-password`.
