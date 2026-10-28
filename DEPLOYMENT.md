# Going live: Supabase + Render + Netlify + UptimeRobot

Follow the steps in order. Allow about an hour for the first time. Button names on these websites change
now and then, so if one looks slightly different, look for the closest match.

**What each service does**

| Service | Job | Free tier catch |
|---|---|---|
| GitHub | Holds your code. Render and Netlify rebuild from it. | None |
| Supabase | The database, and storage for photos and attachments. | Free projects pause after about a week with no activity (UptimeRobot prevents this, step 7). |
| Render | Runs the backend (the API). | The free server goes to sleep after about 15 minutes with no visitors and takes up to a minute to wake (UptimeRobot prevents this, step 7). |
| Netlify | Serves the website people open. | None for this size. |
| UptimeRobot | Checks the backend every 5 minutes, keeps it awake, and emails you if it goes down. | Free plan checks every 5 minutes. |

**The order matters**, because the website needs the backend's address and the backend needs the website's address.
The order below avoids getting stuck: Supabase, then Render, then Netlify, then one small fix on Render.

---

## Step 1. On your computer

### 1a. Make your two secret keys

Open a terminal in the `backend` folder and run:

```
py -m pip install -r requirements.txt -r requirements-prod.txt
py preflight.py --secrets
```

It prints a `SECRET_KEY` and a `JWT_SECRET_KEY`. Copy both somewhere private (a password manager is ideal).
They are different on purpose. Never put them in the code or send them to anyone.

### 1b. Make a private settings file

In the `backend` folder create a plain text file named exactly `.env.production` and put this in it,
filling in the blanks as you go through steps 2 and 3. **The name must not be just `.env`**: that one is loaded
automatically and you could end up running experiments on your real database. `.env.production` is already
ignored by git, so it can never be uploaded to GitHub by accident.

```
SECRET_KEY=paste-the-first-key
JWT_SECRET_KEY=paste-the-second-key
DATABASE_URL=
CORS_ORIGINS=https://YOUR-SITE-NAME.netlify.app
TRUST_PROXY_COUNT=1
UPLOAD_S3_ENDPOINT=
UPLOAD_S3_BUCKET=
UPLOAD_S3_ACCESS_KEY=
UPLOAD_S3_SECRET_KEY=
UPLOAD_S3_REGION=
UPLOAD_PUBLIC_BASE_URL=
DEMO_PASSWORD=choose-a-private-password-for-the-demo-accounts
```

Choose your Netlify site name now (letters, numbers and dashes, for example `kgss-sms`). Its address will be
`https://kgss-sms.netlify.app`. Use that in `CORS_ORIGINS` (no slash at the end).

### 1c. Put the code on GitHub

Create a **private** repository on github.com, then in the project's top folder (the one that contains `backend`
and `frontend`):

```
git init
git add .
git commit -m "School platform"
git branch -M main
git remote add origin https://github.com/YOUR-NAME/YOUR-REPO.git
git push -u origin main
```

Run `git status` before committing and check that `.env.production` and `dev.db` are **not** listed.

---

## Step 2. Supabase (database and file storage)

1. Sign in at supabase.com, press **New project**. Give it a name, and a **database password**. Use letters and
   numbers only (symbols such as `@` or `#` must be specially encoded in the address and cause confusing errors).
   Save the password.
2. **Region**: choose a Europe region (Frankfurt is a good choice). Use the same area for Render in step 3, so the
   backend and database are close together. Wait a couple of minutes for the project to be ready.
3. **Database address.** Press **Connect** at the top of the project. Under connection strings, pick the
   **Transaction pooler** and copy the address. It looks like:

   `postgresql://postgres.abcdefghijkl:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres`

   Replace `[YOUR-PASSWORD]` (square brackets included) with your password. This is your `DATABASE_URL`.
   Do **not** use the "Direct connection": Render's free tier cannot reach it.
4. **Storage bucket.** Open **Storage**, **New bucket**, name it `school-files`, and turn **Public bucket** on.
5. **Storage keys.** In Storage, open the **S3 connection** settings. Note the **Endpoint** and **Region** shown
   there, then create a **New access key**. Copy the **Access key ID** and **Secret access key** straight away: the
   secret is shown only once.
6. Find your project's **Reference ID** (Project Settings, General). Fill in your `.env.production`:

   | Setting | Value |
   |---|---|
   | `DATABASE_URL` | the address from step 3 |
   | `UPLOAD_S3_ENDPOINT` | `https://REFERENCE-ID.supabase.co/storage/v1/s3` |
   | `UPLOAD_S3_BUCKET` | `school-files` |
   | `UPLOAD_S3_ACCESS_KEY` | the Access key ID |
   | `UPLOAD_S3_SECRET_KEY` | the Secret access key |
   | `UPLOAD_S3_REGION` | the region shown on that page, for example `eu-central-1` |
   | `UPLOAD_PUBLIC_BASE_URL` | `https://REFERENCE-ID.supabase.co/storage/v1/object/public/school-files` |

7. **Check it all before going further.** In the `backend` folder:

   ```
   py preflight.py --env-file .env.production --test-upload
   ```

   It tests the database login and uploads then deletes one tiny file. Fix every line marked `FIX` (each says what
   to do) and run it again until it says **All good**. This one check catches nearly every mistake people make.

---

## Step 3. Render (the backend)

1. Sign in at render.com. **New**, then **Web Service**, then connect your GitHub account and pick the repository.
2. Fill in:

   | Field | Value |
   |---|---|
   | Name | `kgss-sms-api` (this becomes part of its address) |
   | Region | Frankfurt (or the one nearest your Supabase region) |
   | Branch | `main` |
   | **Root Directory** | `backend` |
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt -r requirements-prod.txt` |
   | Start Command | `gunicorn --workers 1 --bind 0.0.0.0:$PORT run:app` |
   | Instance type | Free |

   Keep `--workers 1`. The reminder scheduler lives inside the process, and more workers would send every reminder twice.
3. Under **Advanced**, set **Health Check Path** to `/api/health`.
4. Under **Environment Variables**, add each of these (you can paste your `.env.production` lines in using
   **Add from .env**):

   | Variable | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.12.8` (if Render says that exact version is unavailable, use any `3.12.x`) |
   | `FLASK_ENV` | `production` |
   | `SECRET_KEY`, `JWT_SECRET_KEY` | your two keys |
   | `DATABASE_URL` | your Supabase address |
   | `CORS_ORIGINS` | `https://YOUR-SITE-NAME.netlify.app` (no slash at the end) |
   | `TRUST_PROXY_COUNT` | `1` |
   | `SCHEDULER_ENABLED` | `1` |
   | the six `UPLOAD_...` values | from step 2 |
   | `SEED_DEMO_ON_BOOT` | `1` (loads the demo school the first time, see step 6) |
   | `DEMO_PASSWORD` | your private demo password |

5. Press **Create Web Service** and watch the **Logs**. The first build takes a few minutes. When it works you will
   see the service go **Live**, and, because of `SEED_DEMO_ON_BOOT`, lines starting `Demo data: seeding started`
   and later `seeding finished`.
6. Copy the service's address from the top of the page (for example `https://kgss-sms-api.onrender.com`).
   If the name was already taken it will have extra letters, so copy the real one.
7. Open `https://YOUR-RENDER-ADDRESS/api/health/db` in a browser. You should see `"database":"ok"`.

---

## Step 4. Netlify (the website)

1. Sign in at netlify.com. **Add new site**, then **Import an existing project**, then GitHub, then pick the repository.
2. Fill in:

   | Field | Value |
   |---|---|
   | **Base directory** | `frontend` |
   | Build command | `npm run build` |
   | Publish directory | `dist` |

3. Add environment variables (Site configuration, Environment variables):

   | Variable | Value |
   |---|---|
   | `VITE_API_URL` | your Render address from step 3, **no slash at the end** |
   | `NODE_VERSION` | `20` |

4. Deploy. When it finishes, go to **Site configuration**, **Change site name**, and set it to the name you chose in
   step 1b, so the address is exactly the one you put in `CORS_ORIGINS`.

> `VITE_API_URL` is baked into the website when it is built. If you ever change it, trigger a new deploy
> (Deploys, **Trigger deploy**) or the old value stays.

---

## Step 5. Make sure the two agree

The address in the browser bar of your live website must be **exactly** the same as `CORS_ORIGINS` on Render
(same `https://`, same name, no slash at the end). If they differ, fix `CORS_ORIGINS` on Render. Render restarts by itself.

---

## Step 6. First login and the demo data

Open your Netlify address. On the very first start of an empty database, the backend creates every table and,
because you turned `SEED_DEMO_ON_BOOT` on, loads the demo school (Kenema Government Secondary School: 180 students,
17 staff, timetable, fees, library and more). On a free server this can take a few minutes after Render says Live.
You can watch Render's Logs for `Demo data: seeding finished`.

Sign in with:

| Who | Email |
|---|---|
| Administrator | `admin@kgss.example.sl` |
| Principal | `principal@kgss.example.sl` |
| Teacher | `teacher@kgss.example.sl` |
| Student | `student@kgss.example.sl` |
| Parent | `parent@kgss.example.sl` |
| Others | `accountant@`, `examofficer@`, `hrofficer@`, `librarian@`, `inventory@`, `transport@` (all `...@kgss.example.sl`) |
| Platform owner | `superadmin@platform.example` |

The password for **all** of them is the `DEMO_PASSWORD` you chose. (Not `Password123!`: the app refuses to
seed a real site with that public password.)

**After it has worked once, remove `SEED_DEMO_ON_BOOT` from Render's environment variables.** It only ever
seeds an empty database, but there is no reason to leave it on.

**Optional: your own platform owner login** (so you are not using the demo one). From the `backend` folder:

```
py -m flask --env-file .env.production --app run.py create-superadmin
```

It asks for an email and a hidden password and creates only that login.

**When you start using this for real students:** every demo account shares one password, so do not enter real
children's records into the demo school. Use the Platform Admin screen to create the real school, or start a
fresh Supabase project without `SEED_DEMO_ON_BOOT`.

---

## Step 7. UptimeRobot (keep it awake and get alerts)

1. Register free at uptimerobot.com and confirm your email.
2. **Add New Monitor**:

   | Field | Value |
   |---|---|
   | Monitor Type | HTTP(s) |
   | Friendly Name | `School API` |
   | URL | `https://YOUR-RENDER-ADDRESS/api/health/db` |
   | Monitoring Interval | 5 minutes |
   | Alert contacts | tick your email |

3. Add a second monitor, `School website`, with your Netlify address. It tells you if the website itself is down.
4. Optional: install the UptimeRobot app on your phone to get push alerts.

Why `/api/health/db` and not just `/api/health`: it also runs one trivial database query. That keeps Supabase's
free project in use, and if the database ever stops answering you are told instead of finding out from a teacher.
It returns an error status when the database is unreachable, which UptimeRobot reports as **Down**.

Good to know:

- Render's free plan gives about 750 server hours a month **shared across all your free Render web services**.
  One service kept awake all month uses about 730. If you already run other free services on the same Render account,
  keeping this one awake can use up the allowance and Render pauses services until next month. Check Render's
  usage page, or upgrade this service when you can.
- If Supabase ever shows your project as paused, open it and press **Restore**.
- Free plans change. If a limit above no longer matches what you see, trust the service's own page.

---

## Step 8. Check everything works

Log in as the **administrator** and:

1. Open **Students**. You should see 180. Press **Export to Excel** and open the file.
2. Open your profile and upload a photo. Reload the page: it should still show. (This proves file storage.)
3. As the **HR officer**: HR, Payroll, **New payroll run**. Staff and Total net pay fill in straight away.
4. As the **librarian**: lend a book and choose a loan length. Take an overdue one back.
5. As a **teacher**: set an assignment. As the **principal**: it appears, read only.
6. Click a notification: it marks as read and closes.
7. Wait 10 minutes without touching the site, then open it again. It should load at normal speed
   (that is UptimeRobot doing its job).

---

## Step 9. Updating later

Make your changes, then `git add .`, `git commit -m "what changed"`, `git push`. Render and Netlify rebuild by
themselves. When a new version adds database columns, they are added automatically on start (the Render log says
"Auto-migration added N missing column(s)"). **Before deploying a version that changes the database, take a backup** in Supabase
(Database, Backups; what is offered depends on your plan).

---

## If something goes wrong

| What you see | Most likely cause and fix |
|---|---|
| Render log: "Refusing to start with an unsafe production configuration" | It names the problem: a short or default key, a missing or `*` `CORS_ORIGINS`, or a missing `DATABASE_URL`. Fix that variable. |
| Render build fails while installing `psycopg2` | Render is on a newer Python. Set `PYTHON_VERSION` to `3.12.8` (or any `3.12.x`). |
| Login page shows a network or CORS error | `CORS_ORIGINS` does not exactly match your Netlify address (check `https`, spelling, no trailing slash). Or `VITE_API_URL` is wrong or has a slash; fix it and trigger a new Netlify deploy. |
| Everything is slow, only the first time | The free server was asleep. UptimeRobot (step 7) stops this. |
| "Could not connect" or password errors in the Render log | Run `py preflight.py --env-file .env.production`. It points at the cause. Usual causes: symbols in the password, or the Direct connection address instead of the pooler. |
| Photos or the school logo do not appear | The bucket is not **Public**, or `UPLOAD_S3_REGION` / `UPLOAD_PUBLIC_BASE_URL` is wrong. Run the preflight with `--test-upload`. |
| No demo data | Look in Render's Logs for `Demo data`. Either `DEMO_PASSWORD` is missing or weak (the log says so), or the database already had a school. |
| Cannot log in as `admin@kgss.example.sl` | The password is your `DEMO_PASSWORD`, not `Password123!`. |
| UptimeRobot says Down but the site works | The API took longer than UptimeRobot waits (a cold start) or the database is unreachable. Open `/api/health/db` yourself to see which. |

---

## What was and was not tested

Tested on a real PostgreSQL 16 server, running the app exactly as Render does (gunicorn, production mode): first start on
an empty database creating every table, first-start demo seeding with a private password, upgrading an older database
in place, the full set of 154 end to end checks, and every pre-flight check above.

**Not testable from here, so confirm them yourself on the day:** Supabase's own pooler and storage (the pre-flight
check in step 2 tests exactly these from your computer), Render and Netlify's dashboards, and UptimeRobot.
