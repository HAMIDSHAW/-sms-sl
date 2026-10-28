# SchoolOS production-readiness audit

Scope: the existing Flask API (`backend/`) and React app (`frontend/`), audited against a throwaway copy of the
database. Nothing here touched your own `dev.db`. Only features and roles that actually exist were tested: the 12
seeded accounts (admin, principal, 2 teachers, accountant, exam officer, HR officer, librarian, inventory,
transport, student, parent), the platform super admin, and a second school created to test tenant isolation.
There is no payment gateway, no AI feature, no marketing email and no analytics in this app, so those phases are
marked not applicable.

## A. Executive summary

**Verdict: NOT ready to launch as it was. Ready to launch once the external items in section I are done.**

The audit found and confirmed **2 Critical, 6 High and 15 Medium** problems in the code you gave me. All of
them are fixed and covered by automated tests (42 backend tests, all passing) plus browser tests of the real screens.
What still stands between this and a public launch is not code: production secrets and CORS must be set,
a privacy policy and data-protection review are needed for a system holding children's records, and backups have
never been restore-tested. Details in sections H and I.

The two Critical findings, both demonstrated before fixing:

1. **Account takeover.** `POST /api/auth/forgot-password` returned the live reset token in its response. A logged-in
   student found a teacher's id and email through the messaging contact list, requested a reset, and set the teacher's
   password. Fixed: the token is never returned (only to a direct request from the developer's own machine in a
   non-production setup). Because no email service exists, recovery now works through an admin-issued one-time
   temporary password (new button on the Staff page).
2. **Fee fraud.** A parent could `POST /api/payments` with status "successful" on their own child's invoice. No money
   moved and the balance went to zero. Fixed twice over: the permission was removed from the parent role and the route
   refuses student and parent accounts.

## B. Architecture inspected

- Backend: Flask 3, SQLAlchemy (SQLite locally, Postgres on Render), JWT (flask-jwt-extended), bcrypt, Flask-Limiter,
  Flask-CORS, gunicorn. Multi-tenant by `school_id` on every record, scoped in `scoped_query`. Permissions are baked
  into the JWT. Uploads go to local disk or an S3-compatible bucket (Supabase).
- Frontend: React 18, Vite 5, Tailwind 3, React Router 6, framer-motion. Static site on Netlify. Tokens are kept in
  `localStorage`.
- Hosting config: `backend/render.yaml` (Render), `frontend/netlify.toml`. No Docker, no CI, no git repository in the
  zip.
- Not present: payments, AI, email delivery, SMS, analytics or advertising trackers, webhooks. The only third party
  the browser contacts is Google Fonts.

## C. Baseline findings and fixes

Severity is mine. "Evidence" is what I actually ran or read.

| # | Sev | Finding | Evidence | Status |
|---|-----|---------|----------|--------|
| 1 | Critical | Reset token returned by forgot-password (account takeover) | Student reset a teacher's password in a test | FIXED AND VERIFIED |
| 2 | Critical | Parent could mark own child's fees paid | Balance went to 0 in a test | FIXED AND VERIFIED |
| 3 | High | `/uploads/..` read files outside the uploads folder | Canary file in `instance/` was returned | FIXED AND VERIFIED |
| 4 | High | `/api/marks` returned all 900 marks to any student or parent | 900 rows, 180 distinct students | FIXED AND VERIFIED |
| 5 | High | `/api/finance/expenses` readable by anyone with `finance.view` (students, parents) | Code read; my test database had no expenses, so exposure was shown by the permission check, not by leaked rows | FIXED AND VERIFIED (now 403) |
| 6 | High | Logout revoked the newest session, not the one being signed out | Code read, then tested two devices after the fix | FIXED AND VERIFIED |
| 7 | High | Deactivated accounts and old tokens stayed valid for up to 8 hours | Tested after the fix | FIXED AND VERIFIED |
| 8 | High | Built-in default `SECRET_KEY`/JWT key and `CORS_ORIGINS=*` accepted in production | Config tests in 6 scenarios | FIXED AND VERIFIED |
| 9 | Medium | Behind Render's proxy every user would share one rate-limit bucket (login lock-out for everyone) | Code read | FIXED (ProxyFix + `TRUST_PROXY_COUNT`); real proxy NOT VERIFIED |
| 10 | Medium | Login limited by IP only; reset/verify endpoints unlimited | Tested | FIXED AND VERIFIED (per-account and per-IP) |
| 11 | Medium | Weak password rules (length 8 only, no maximum, school owner password unchecked) | Tested | FIXED AND VERIFIED |
| 12 | Medium | Password change/reset did not sign other devices out | Tested | FIXED AND VERIFIED |
| 13 | Medium | Unknown email answered faster than a wrong password | 293 ms vs 283 ms after fix, same message | FIXED AND VERIFIED |
| 14 | Medium | Uploads trusted the extension only; S3 stored the client's MIME type | HTML renamed `.png` was accepted | FIXED AND VERIFIED |
| 15 | Medium | No request size limit | 11 MB body accepted | FIXED AND VERIFIED (413) |
| 16 | Medium | No CSP/security headers on API or site | Headers checked | FIXED AND VERIFIED (API); site headers in `netlify.toml`, tested against the production build, real Netlify NOT VERIFIED |
| 17 | Medium | `/api/attendance` returned the whole history unbounded (2.1 s, 1 MB, grows daily) | Measured | FIXED AND VERIFIED (0.5 s, 0.3 MB) |
| 18 | Medium | Malformed numbers or dates in query strings caused HTTP 500 | 767 fuzz requests | FIXED AND VERIFIED (0 server errors) |
| 19 | Medium | One email could exist in two schools; login picks the first | Code read | FIXED AND VERIFIED |
| 20 | Medium | User-management routes could hand out administrator rights to any holder of those permissions (no such custom role exists today) | Code read | FIXED (defence in depth), covered by tests |
| 21 | Medium | `render.yaml` would not install the Postgres driver after last round's requirements split | Code read (my own regression) | FIXED AND VERIFIED (file parses; deploy NOT VERIFIED) |
| 22 | Medium | Forgot-password page told users an email was sent. No email exists. | UI read | FIXED AND VERIFIED |
| 23 | Medium | Demo seed (one public password for every account) could run in production | Code read | FIXED AND VERIFIED (refuses unless `ALLOW_DEMO_SEED=1`) |
| 24 | Low | `run.py` always ran with debug on | Code read | FIXED |
| 25 | Low | Silent `except: pass` around startup schema sync | Code read | FIXED (logged) |
| 26 | Dependencies | pip-audit: Flask, Flask-Cors, python-dotenv had known advisories | Scanner output | FIXED AND VERIFIED (re-scan: none) |

## D. Checklist

**Functionality and UX**
- Every page loads for every role (11 roles x their pages, 0 crashes, 0 server errors): PASS
- Interactive flows (notification click, message reply, library edit, discipline, HR approve, payroll, staff reset): PASS
- Custom 404 page: FIXED AND VERIFIED (did not exist)
- Page title, favicon, meta description: FIXED AND VERIFIED (favicon and description were missing)
- Misleading reset-by-email message: FIXED AND VERIFIED
- Phone numbers and emails as `tel:` / `mailto:` links: FIXED AND VERIFIED on Students, Staff, Guardians, assignment teacher card
- Destructive actions ask for confirmation: PASS (assignment, invoice cancel, inventory, library, staff archive, password reset)
- Offline state and automatic retry: NOT VERIFIED
- Footer, social previews, testimonials, pricing: NOT APPLICABLE (private app, none exist). Basic Open Graph tags added.

**Responsive and accessibility**
- Phone width (375 px): content area was 119 px wide and every page overflowed. Now full width, no horizontal overflow on any tested page at 375, 768, 1280: FIXED AND VERIFIED (mobile menu added)
- axe-core (WCAG 2.2 AA ruleset) on 13 pages plus the open dialog and open mobile menu: started at 562 contrast nodes plus labelling gaps, now 0: FIXED AND VERIFIED
- Keyboard: skip link, dialog focus move, Tab trap, Escape, focus return: FIXED AND VERIFIED
- Lighthouse accessibility 98 on the login page: PASS
- Real screen-reader testing (NVDA, VoiceOver, TalkBack): NOT VERIFIED. Automated tools find only part of the problems.
- Fixing labels at source for every form: partly. A small runtime helper (`src/lib/a11y.js`) links labels to controls for the many forms that did not. New forms should use `htmlFor` or `aria-label`.

**Authentication and authorization**
- Password hashing (bcrypt): PASS
- Reset flow, throttling, session invalidation: FIXED AND VERIFIED
- Email verification: exists but unused by the UI. NOT VERIFIED beyond throttling and the token leak fix.
- Vertical and horizontal privilege checks: every write route tried as 10 roles, every list route as student and parent: PASS after fixes (findings 2, 4, 5)
- IDOR: student to student, parent to unrelated child, school B to school A (read, edit, delete, lists): PASS
- Mass assignment: updates use field allowlists. Spot-checked on users, students, staff, payments: PASS
- Forged JWTs (`alg=none`, bad signature), refresh/access token mix-ups: PASS
- CSRF: NOT APPLICABLE. Tokens travel in the `Authorization` header, not cookies.
- Token storage in `localStorage`: accepted risk, see section H.

**API security**
- SQL injection probes across all list endpoints: PASS (no errors, data intact). The code uses the ORM with bound parameters throughout; bandit found only low severity notes.
- XSS: no `dangerouslySetInnerHTML`, `innerHTML` or `eval` anywhere in the frontend: PASS
- CORS: explicit origins, never `*`: FIXED AND VERIFIED
- Headers (nosniff, frame deny, no-store, strict API CSP, HSTS over HTTPS): FIXED AND VERIFIED
- Pagination caps: PASS (`per_page` capped at 200)
- Open redirects: PASS (login redirect comes from router state, not the URL)

**Secrets and dependencies**
- detect-secrets over the whole tree: only placeholders and the documented demo password: PASS
- Git history scan: NOT VERIFIED (the zip has no git repository)
- `.gitignore` covers `.env`, database, uploads: PASS (a `.gitignore` is also needed at the project root if you create the repo there)
- Python dependencies: FIXED AND VERIFIED (pip-audit clean)
- npm: `npm audit fix` applied. 11 advisories remain (6 high, 5 moderate), listed in section H. FAIL (accepted, see H)
- Licences review: NOT VERIFIED

**Privacy and legal**
- Privacy policy, terms, consent, data export and deletion: NOT PRESENT. REQUIRES EXTERNAL ACTION (section I)
- Third parties: Google Fonts only (sends visitors' IP addresses to Google). Self-hosting the fonts removes this.
- Child data and parental consent rules: REQUIRES EXTERNAL ACTION

**Database and integrity**
- Tenant isolation: PASS (tested)
- Row-level security, least-privilege database role, restore test: REQUIRES EXTERNAL ACTION (these live in the Postgres host)
- Constraints: unique and foreign keys present. Duplicate invoices prevented by the bill-class endpoint. PASS
- Migrations: the app adds missing columns at startup (`password_changed_at` was added this way). There is no migration history; a proper tool (Alembic) is advisable before the first real data. RECOMMENDED

**Uploads**: allowlist, size cap, content check, safe names, `nosniff` and sandbox CSP on download, rate limit: FIXED AND VERIFIED. Malware scanning: NOT PRESENT. Files are public to anyone who has the unguessable URL, which is acceptable for photos and class materials; private documents would need signed URLs.

**Payments**: NOT APPLICABLE (no gateway; the accountant records payments). Server-side validation of amount, overpayment and cancelled invoices: PASS.
**AI**: NOT APPLICABLE. **Email/SMS**: NOT APPLICABLE (not built). **SEO**: private app, indexing blocked on purpose (`robots.txt`, `noindex`).

**Performance** (section J) and **Deployment** (section I) follow.

## E. Changed files (significant)

Backend: `app/__init__.py` (hardening wiring, error handlers, safe uploads route, token checks), `app/utils/security.py`
(new: startup rules, headers, proxy, security log), `app/utils/passwords.py` (new), `app/utils/activity_log.py`,
`app/routes/auth.py`, `users.py` (reset-password, admin guards), `payments.py`, `marks.py`, `finance_reports.py`,
`uploads.py`, `attendance.py`, `platform.py`, `app/models/auth.py` (permissions, token version), `app/utils/storage.py`,
`app/utils/tenancy.py`, `app/extensions.py`, `app/config.py`, `run.py`, `seed.py`, `render.yaml`, `.env.example`,
`requirements.txt`, `requirements-dev.txt` (new), `tests/` (new, 42 tests).
Frontend: `index.html`, `public/favicon.svg` and `robots.txt` (new), `netlify.toml`, `src/App.jsx` (lazy loading, 404),
`components/layout/AppShell.jsx` (mobile menu, skip link), `components/ui/index.jsx` (accessible dialog, contact links),
`src/lib/a11y.js` (new), `tailwind.config.js` (contrast), `pages/auth/ForgotPassword.jsx`, `ChangePassword.jsx`,
`pages/staff/StaffList.jsx`, `pages/NotFound.jsx` (new), plus labels on several filter controls.

Behaviour changes you will notice: parents no longer see "Record payment"; access tokens last 60 minutes and renew
silently (verified); CORS allows only `http://localhost:5173` and `http://127.0.0.1:5173` unless you set
`CORS_ORIGINS`; "Password123!" and other common passwords cannot be chosen as a new password; muted text is lighter.

## G. Tests run

| Command | Result |
|---------|--------|
| `py -m pytest -q` in `backend` | 42 passed |
| Authorization sweep, all 189 route and method pairs, 10 roles | reviewed; matches each role's job |
| Fuzz: 767 malformed or injection style GET requests (59 endpoints x 13 payloads), plus 472 more inside the test suite | 0 server errors |
| Browser sweep, 11 roles x their pages | 0 crashes, 0 server errors, 0 JS errors |
| Browser flows (reply, notification, library, discipline, HR, staff reset) | pass |
| axe-core WCAG 2.2 AA, 13 pages + dialog + mobile menu | 0 violations |
| Production build served under the real CSP, login, 7 pages | 0 CSP violations |
| Token expiry (1 minute token, 75 s wait) | silent refresh, stayed signed in |
| pip-audit / npm audit / bandit / detect-secrets | see sections C, H |
| Startup safety in 6 configurations | as designed |

Could not run: real Postgres, real S3, real HTTPS or proxy, email, Netlify/Render dashboards, restore test, screen
readers, load test, git history scan.

## H. Remaining issues

No known Critical or High issue remains in the code. Accepted or open:

1. **npm advisories (11 remain: 6 high, 5 moderate; only 2 moderate ones are in code that ships to users).** The shipped
   ones are `react-router` and `react-router-dom` (open redirect when a link target comes from user input). This app only navigates to fixed internal paths and paths the server controls, so I judge it low
   practical risk. The rest, including all 6 high ones, are build-time tools (Tailwind, Vite, esbuild, glob helpers) that run on a developer's
   machine or CI and never ship to users.
   Every remaining fix is a major version jump (React Router 7, Vite 8, Tailwind 4) that could break the app, so I did
   not force them. Plan the upgrade as its own task with a test pass.
2. **Tokens in `localStorage`.** A script injection would expose them. There is no XSS sink in the code today and the
   CSP restricts scripts, but httpOnly cookies (with CSRF protection) would be stronger. It is an architecture change.
3. **Password recovery needs a human.** Until email or SMS is connected, an administrator issues temporary passwords.
   Students and parents have no button for it yet (the endpoint works for any user id).
4. **Rate limits are per process.** Fine with the single gunicorn worker in `render.yaml`. Set
   `RATELIMIT_STORAGE_URI` to a Redis URL before adding workers.
5. **A person can be slowed down on purpose.** The per-account login limit (8 per minute) lets an attacker delay a
   victim's sign-in; it does not lock them out.
6. **Schema changes have no migration history.**

## I. External actions before launch

1. In Render set `SECRET_KEY` and `JWT_SECRET_KEY` (different, 48+ random characters; generate with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`), `DATABASE_URL`, `CORS_ORIGINS` (your exact Netlify
   URL), and the S3 variables. The app refuses to start in production without them.
2. Set `VITE_API_URL` in Netlify to the Render URL. If the backend is not on `*.onrender.com`, add its origin to
   `connect-src` and `img-src` in `netlify.toml`.
3. Do not run `seed.py` against production data. Create the real school through the platform admin, then change the
   super admin password. Anything ever sent in chat or email as a password should be treated as exposed.
4. Confirm HTTPS and HSTS on the real domains. Confirm the proxy count (1 on Render).
5. Postgres: use a database user that cannot create or drop other databases, restrict network access, turn on automated
   backups, and **perform one restore test** before relying on it.
6. Privacy: get a lawyer or data-protection adviser to review what you collect (children's names, dates of birth,
   photos, grades, discipline records, guardian contact details), write a privacy policy and terms, and decide on
   consent, retention, data export and deletion. This is a launch blocker for a system of this kind.
7. Decide how password recovery will work long term (email or SMS provider).
8. Review the licences of fonts and images you ship. Consider self-hosting the fonts.
9. Add uptime monitoring on `/api/health` (already registered in `render.yaml`) and an alert on repeated
   `security_event=` log lines.

## J. Performance

| Measure | Before | After |
|---------|--------|-------|
| First script download | 526.6 kB (146.4 kB compressed) | 344.6 kB (110.4 kB compressed), each page loads on demand |
| `/api/attendance` (1,668 rows) | 2,135 ms, 1.0 MB | 523 ms, 0.3 MB |
| Phone layout | unusable (119 px content) | full width |

Lighthouse on the production build's login page, offline sandbox, default mobile profile: performance 76,
accessibility 98, best-practices 96, SEO 63 (blocked on purpose). FCP 3.2 s and LCP 3.3 s are inflated because Google
Fonts cannot load offline and the stylesheet blocks rendering. I did not measure Lighthouse before my changes, so I make
no before and after claim for it. Real-device and real-network numbers are NOT VERIFIED.

## K. Launch checklist

Blockers: items 1, 2, 3, 5 and 6 of section I.
Soon after launch: self-host fonts, Alembic migrations, email or SMS recovery, httpOnly cookie sessions, React Router
and Vite upgrades, signed URLs for private documents, a real screen reader pass, a CI job that runs `pytest`,
`pip-audit` and `npm audit`.
