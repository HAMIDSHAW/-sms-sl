"""
Check your production settings from your own computer BEFORE you deploy.

It never changes anything in your database. It only reads, and (if you ask) uploads then deletes one
tiny test file. Run it from the backend folder:

    py preflight.py --secrets                          prints two fresh secret keys to paste into Render
    py preflight.py --env-file .env.production         checks the settings in that file
    py preflight.py --env-file .env.production --test-upload      also tests the Supabase file storage

Keep the production values in a file called .env.production (it is ignored by git, so it can never be
committed by accident). Never name it just ".env": the app and `flask` load that one automatically,
and you would end up running local experiments against your real database.
"""
import argparse
import os
import secrets
import sys

OK, FIX, WARN = "  OK   ", "  FIX  ", "  WARN "
problems = 0


def say(tag, text):
    global problems
    if tag == FIX:
        problems += 1
    print(f"{tag}{text}")


def load_env_file(path):
    from dotenv import dotenv_values
    if not os.path.exists(path):
        sys.exit(f"Cannot find {path}. Create it next to this script (see the top of this file).")
    for key, value in dotenv_values(path).items():
        if value is not None:
            os.environ[key] = value


def check_secrets():
    secret, jwt = os.environ.get("SECRET_KEY", ""), os.environ.get("JWT_SECRET_KEY", "")
    for name, value in (("SECRET_KEY", secret), ("JWT_SECRET_KEY", jwt)):
        if not value:
            say(FIX, f"{name} is not set. Make one with:  py preflight.py --secrets")
        elif value.startswith("change-me") or len(value) < 32:
            say(FIX, f"{name} is a placeholder or shorter than 32 characters. Make one with:  py preflight.py --secrets")
        else:
            say(OK, f"{name} looks strong")
    if secret and secret == jwt:
        say(FIX, "SECRET_KEY and JWT_SECRET_KEY are the same. They must be two different values.")


def check_database():
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url
    from app.config import normalize_database_url

    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        say(FIX, "DATABASE_URL is not set. On Render this would silently become a throwaway file that is erased on every redeploy.")
        return
    if "[YOUR-PASSWORD]" in raw or "YOUR-PASSWORD" in raw:
        say(FIX, "DATABASE_URL still contains [YOUR-PASSWORD]. Replace it, brackets included, with your real database password.")
        return
    if raw.count("@") > 1:
        say(FIX, "DATABASE_URL has more than one @. A password containing @ # / : ? or % must be URL-encoded "
                 "(@ becomes %40, # becomes %23, / becomes %2F, : becomes %3A). Or reset the password to letters and numbers only.")
        return
    url = normalize_database_url(raw)
    if url.startswith("sqlite"):
        say(FIX, "DATABASE_URL points at SQLite. Production must use your Supabase Postgres address.")
        return
    try:
        parsed = make_url(url)
    except Exception as exc:
        say(FIX, f"DATABASE_URL could not be read: {exc}")
        return

    host = parsed.host or ""
    if host.startswith("db.") and host.endswith(".supabase.co"):
        say(FIX, f"{host} is Supabase's DIRECT connection. Render's free tier cannot reach it (it is IPv6 only). "
                 "In Supabase press Connect, choose the Session pooler or Transaction pooler, and copy that address "
                 "(it contains 'pooler.supabase.com').")
        return
    if "pooler.supabase.com" in host and parsed.username == "postgres":
        say(FIX, "With the pooler address the username must be postgres.<your-project-ref> (for example postgres.abcdefghijkl), "
                 "not just postgres. Copy the full address from Supabase's Connect panel.")
        return
    if "pooler.supabase.com" in host:
        say(OK, f"Using Supabase's connection pooler ({host}, port {parsed.port})")
    else:
        say(WARN, f"{host} is not a Supabase pooler address. That is fine only if you know it is reachable from Render.")

    try:
        engine = create_engine(url, connect_args={"connect_timeout": 12})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            version = conn.execute(text("SELECT version()")).scalar()
            tables = inspect(conn).get_table_names()
        say(OK, f"Connected to the database ({str(version).split(',')[0]})")
        if not tables:
            say(OK, "The database is empty, which is right for a first deploy (the app creates its own tables on first start)")
        else:
            say(WARN, f"The database already has {len(tables)} tables. That is expected only if this site is already live. "
                      "Take a Supabase backup before deploying a new version.")
    except Exception as exc:
        message = str(exc).splitlines()[0] if str(exc) else repr(exc)
        low = message.lower()
        if "password authentication failed" in low:
            hint = "The password is wrong. If it has special characters, URL-encode them, or reset the database password to letters and numbers."
        elif "tenant or user not found" in low:
            hint = "The username must be postgres.<your-project-ref> when using the pooler."
        elif "could not translate host" in low or "name or service not known" in low:
            hint = "The host name is misspelled. Copy the whole address again from Supabase."
        elif "network is unreachable" in low or "timeout" in low or "timed out" in low:
            hint = "Could not reach the server. Use the pooler address (not the direct one) and check your internet connection."
        elif "no module named" in low and "psycopg2" in low:
            hint = "Install the Postgres driver on this computer first:  py -m pip install -r requirements-prod.txt"
        elif "connection refused" in low:
            hint = "Nothing is listening at that host and port. Check the port (6543 or 5432) and the host."
        else:
            hint = "See the message above."
        say(FIX, f"Could not connect to the database: {message}")
        print(f"         -> {hint}")


def check_cors():
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        say(FIX, "CORS_ORIGINS is not set. Set it to your Netlify address, for example https://kgss.netlify.app")
        return
    for origin in [o.strip() for o in raw.split(",") if o.strip()]:
        if origin == "*":
            say(FIX, "CORS_ORIGINS must name your site, not *")
        elif origin.endswith("/"):
            say(FIX, f"{origin} ends with a slash. Remove it: browsers send the address without one, so it would never match.")
        elif not origin.startswith("https://") and "localhost" not in origin:
            say(FIX, f"{origin} must start with https://")
        elif "/" in origin.split("://", 1)[-1]:
            say(FIX, f"{origin} must be just the site address, with no path after it")
        else:
            say(OK, f"CORS allows {origin}")


def check_uploads(test_upload):
    names = ["UPLOAD_S3_ENDPOINT", "UPLOAD_S3_BUCKET", "UPLOAD_S3_ACCESS_KEY", "UPLOAD_S3_SECRET_KEY", "UPLOAD_PUBLIC_BASE_URL"]
    present = [n for n in names if os.environ.get(n, "").strip()]
    if not present:
        say(FIX, "File storage is not set up. Photos, logos and assignment files would be saved on Render's disk and "
                 "erased on every redeploy. Set the five UPLOAD_S3_* values (and UPLOAD_S3_REGION).")
        return
    missing = [n for n in names if n not in present]
    if missing:
        say(FIX, "Missing: " + ", ".join(missing))
        return
    endpoint = os.environ["UPLOAD_S3_ENDPOINT"]
    if not endpoint.startswith("https://") or not endpoint.rstrip("/").endswith("/storage/v1/s3"):
        say(FIX, "UPLOAD_S3_ENDPOINT should look like https://<project-ref>.supabase.co/storage/v1/s3")
    base = os.environ["UPLOAD_PUBLIC_BASE_URL"]
    bucket = os.environ["UPLOAD_S3_BUCKET"]
    if "/storage/v1/object/public/" not in base or not base.rstrip("/").endswith(bucket):
        say(FIX, f"UPLOAD_PUBLIC_BASE_URL should look like https://<project-ref>.supabase.co/storage/v1/object/public/{bucket}")
    if not os.environ.get("UPLOAD_S3_REGION", "").strip():
        say(WARN, "UPLOAD_S3_REGION is not set. Supabase signs uploads with your project's region (shown on its Storage "
                  "S3 connection page, for example eu-west-2). Set it, or uploads may be rejected.")
    if not test_upload:
        say(WARN, "Not tested yet. Add --test-upload to upload and delete one tiny test file.")
        return
    try:
        import io
        import uuid
        import boto3
        client = boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=os.environ["UPLOAD_S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["UPLOAD_S3_SECRET_KEY"], region_name=os.environ.get("UPLOAD_S3_REGION", "auto") or "auto",
        )
        key = f"_preflight/{uuid.uuid4().hex}.txt"
        client.upload_fileobj(io.BytesIO(b"preflight"), bucket, key, ExtraArgs={"ContentType": "text/plain"})
        public = f"{base.rstrip('/')}/{key}"
        reachable = None
        try:
            import urllib.request
            with urllib.request.urlopen(public, timeout=15) as resp:
                reachable = resp.status == 200
        except Exception:
            reachable = False
        client.delete_object(Bucket=bucket, Key=key)
        say(OK, "Uploaded and deleted a test file in your bucket")
        if reachable:
            say(OK, "The uploaded file was publicly readable, so photos will display")
        else:
            say(FIX, "The upload worked but the file was NOT readable at its public address. Make the bucket Public in Supabase "
                     "(Storage, click the bucket, Edit bucket, tick Public).")
    except Exception as exc:
        text = str(exc)
        hint = ""
        if "SignatureDoesNotMatch" in text or "AuthorizationHeaderMalformed" in text or "InvalidRegion" in text:
            hint = "The keys or the region are wrong. Check UPLOAD_S3_REGION against Supabase's S3 connection page, and re-create the access key if unsure."
        elif "NoSuchBucket" in text:
            hint = "That bucket name does not exist. UPLOAD_S3_BUCKET must match the bucket's name exactly."
        elif "AccessDenied" in text or "InvalidAccessKeyId" in text:
            hint = "The access key was not accepted. Create a new one under Storage, S3 Access Keys."
        say(FIX, f"Upload test failed: {text.splitlines()[0] if text else repr(exc)}")
        if hint:
            print(f"         -> {hint}")


def main():
    parser = argparse.ArgumentParser(description="Check production settings before deploying.")
    parser.add_argument("--secrets", action="store_true", help="print two new secret keys and exit")
    parser.add_argument("--env-file", help="a file of KEY=value lines to check, such as .env.production")
    parser.add_argument("--test-upload", action="store_true", help="also upload and delete one test file in Supabase Storage")
    args = parser.parse_args()

    if args.secrets:
        print("Paste these into Render as two separate environment variables (never share or commit them):\n")
        print("SECRET_KEY     =", secrets.token_urlsafe(48))
        print("JWT_SECRET_KEY =", secrets.token_urlsafe(48))
        return 0

    if args.env_file:
        load_env_file(args.env_file)
    elif os.path.exists(".env.production"):
        load_env_file(".env.production")
        print("(using .env.production)")
    else:
        print("(no --env-file given: checking the settings already in this window)")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    print("\nChecking production settings:\n")
    check_secrets()
    check_database()
    check_cors()
    check_uploads(args.test_upload)
    if os.environ.get("TRUST_PROXY_COUNT", "") != "1":
        say(WARN, "TRUST_PROXY_COUNT is not 1. On Render set it to 1 so rate limits and logs see each visitor's real address.")
    print()
    if problems:
        print(f"{problems} thing(s) to FIX before deploying.")
        return 1
    print("All good. Safe to deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
