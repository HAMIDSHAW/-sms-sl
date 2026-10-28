# SchoolOS Frontend

A React + Vite + Tailwind frontend for the school platform backend, covering
everything built so far: auth (with forced password change, forgot/reset
password), dashboard, students, staff, guardians, academic structure,
attendance, timetable, assignments, materials, and exams/results/report
cards. Built, and verified to actually build and serve without errors, see
"What was tested."

## Design direction

Grounded in the subject rather than a generic SaaS look: the palette pulls
from Sierra Leone's own colors (leaf green, sky blue, marigold as a warm
accent), the layout borrows the exercise-book vernacular (ruled-paper
textures, a notebook-tab sidebar), and data (student IDs, grades, marks)
is set in monospace to read as *data*, distinct from prose. The signature
moment is the login page's 3D scene, a rotating medallion orbited by
drifting subject cards (Math, English, Science...) built in React Three
Fiber, not a stock gradient hero. The report card page gets its own
signature: a real 3D flip-reveal (perspective + rotateY) when a
student opens their result, rather than a plain fade-in, the one place
in the app that leans into a bigger moment, on purpose, rather than
animating everything equally.

## Stack

- **React 18 + Vite**, fast dev server, simple build
- **Tailwind CSS**, utility classes driven by the token system in `tailwind.config.js`
- **Framer Motion**, page transitions, staggered list reveals, the report card flip
- **React Three Fiber + drei**, the login page's 3D scene
- **React Router v6**, client-side routing + protected routes
- **lucide-react**, icons

## Running it

```bash
npm install
cp .env.example .env    # set VITE_API_URL to your Flask backend
npm run dev              # http://localhost:5173
```

Point `VITE_API_URL` at wherever the Flask backend from `school-platform.zip`
is running (default `http://localhost:5000`). Log in with the seeded
KGSS admin (`admin@kgss.example.sl` / `ChangeMe123!`), the app will force
a password change on first login, matching the backend's actual behavior.

## What was tested

1. `npm install` completes cleanly (214 packages, no unresolved peer deps
   beyond expected `three.js` deprecation warnings).
2. `npm run build` succeeds with zero errors, only a bundle-size warning
   (see gaps below).
3. Served the production build with `vite preview` and confirmed the HTML,
   JS bundle, and CSS all return 200 and the HTML correctly references
   the built assets.

**Not yet tested: actually clicking through the running app against a live
backend in a real browser.** I verified it builds and serves without
errors, and every API call matches an endpoint that's already been tested
from the backend side, but I have not driven the UI myself end to end.
Please treat the first real run as part of your testing pass, not as
something already fully confirmed.

## Honest gaps

- **Bundle size**, the production JS bundle is ~1.1MB (326KB gzipped),
  mostly `three.js`. Since only the login page uses 3D, this should be
  code-split with `React.lazy()` so the rest of the app doesn't pay for it.
  Not done yet.
- **No error boundaries**, an unexpected API shape or a thrown render
  error will currently produce a blank page rather than a graceful
  fallback. Worth adding a top-level error boundary before this goes in
  front of real users.
- **No offline/slow-connection handling**, given the Sierra Leone
  connectivity context noted in your profile, this matters more than it
  would elsewhere. Right now a failed request just throws; there's no
  retry logic, no offline banner, no optimistic UI. Worth prioritizing
  before real rollout given your low-end-Android/inconsistent-connectivity
  design constraint.
- **Academics admin page is intentionally lightweight**, class/subject
  creation uses browser `prompt()` dialogs rather than proper modals,
  since that module wasn't the focus here. Fine to leave as-is if this is
  rarely used, but flagging it as visibly rougher than the rest.
- **No pytest/frontend test suite**, same gap as the backend, for the
  same reason: nothing here has automated regression coverage yet.
