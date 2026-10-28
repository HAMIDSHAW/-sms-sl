"""
Where an uploaded file actually ends up.

Local disk works for dev but is wrong for Render (or any host without a
persistent, shared filesystem): a file saved to local disk is gone on the
next deploy/restart, and a second instance can't see what the first one
saved. Set these three env vars once a Supabase Storage bucket (or any
other S3-compatible bucket) exists, and uploads switch over automatically -
no code or route changes needed, nothing to flip by hand:

    UPLOAD_S3_ENDPOINT    e.g. https://<project-ref>.supabase.co/storage/v1/s3
    UPLOAD_S3_BUCKET      the bucket name (create it in the Supabase dashboard)
    UPLOAD_S3_ACCESS_KEY  / UPLOAD_S3_SECRET_KEY  (Storage → S3 Access Keys)
    UPLOAD_S3_REGION      optional, defaults to "auto" (Supabase doesn't care)
    UPLOAD_PUBLIC_BASE_URL  the public base URL files are served from, for
                            a public Supabase bucket this is
                            https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>

Leave all of these unset locally and nothing changes from how this worked
before, files keep saving to <instance>/uploads/ and serving from /uploads/.
"""
import os
import uuid

IS_S3_CONFIGURED = bool(os.environ.get("UPLOAD_S3_BUCKET"))


_CONTENT_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
    "pdf": "application/pdf", "txt": "text/plain", "zip": "application/zip",
    "doc": "application/msword", "xls": "application/vnd.ms-excel", "ppt": "application/vnd.ms-powerpoint",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class StorageError(Exception):
    pass


def save_upload(file_storage, school_id, ext):
    """file_storage: a werkzeug FileStorage (Flask's request.files[...]).
    Returns the URL the file is now reachable at."""
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    if IS_S3_CONFIGURED:
        return _save_to_s3(file_storage, school_id, stored_name)
    return _save_to_disk(file_storage, school_id, stored_name)


def _save_to_disk(file_storage, school_id, stored_name):
    from flask import current_app
    from werkzeug.utils import secure_filename

    folder = os.path.join(current_app.instance_path, "uploads", school_id)
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(stored_name)
    file_storage.save(os.path.join(folder, safe_name))
    return f"/uploads/{school_id}/{safe_name}"


def _save_to_s3(file_storage, school_id, stored_name):
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    key = f"{school_id}/{stored_name}"
    try:
        client = boto3.client(
            "s3",
            endpoint_url=os.environ["UPLOAD_S3_ENDPOINT"],
            aws_access_key_id=os.environ["UPLOAD_S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["UPLOAD_S3_SECRET_KEY"],
            region_name=os.environ.get("UPLOAD_S3_REGION", "auto"),
        )
        file_storage.stream.seek(0)
        client.upload_fileobj(
            file_storage.stream,
            os.environ["UPLOAD_S3_BUCKET"],
            key,
            # The content type comes from the (validated) extension, never from what the client claimed,
            # so an upload can never be served as a web page from the storage domain.
            ExtraArgs={"ContentType": _CONTENT_TYPES.get(stored_name.rsplit(".", 1)[-1], "application/octet-stream"),
                       "ContentDisposition": "inline" if stored_name.rsplit(".", 1)[-1] in ("png", "jpg", "jpeg", "gif", "webp") else "attachment"},
        )
    except (BotoCoreError, ClientError, KeyError) as e:
        # KeyError means one of the UPLOAD_S3_* env vars above is missing
        # even though UPLOAD_S3_BUCKET was set, a half-finished config,
        # surfaced clearly rather than as an unrelated 500.
        raise StorageError(f"Could not upload file to storage: {e}") from e

    base = os.environ.get("UPLOAD_PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        raise StorageError("UPLOAD_PUBLIC_BASE_URL is not set, file was uploaded but has no public URL")
    return f"{base}/{key}"
