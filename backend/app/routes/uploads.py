"""
Generic authenticated file upload endpoint.

Profile photos, the school logo, and assignment/submission attachments all
used to be plain text "paste a URL" fields with nothing behind them. This
gives the frontend one real place to POST a file and get back a URL it can
store on whichever record (user.photo_url, school.logo_url,
assignment.attachment_url, submission.attachment_url), the upload itself
doesn't know or care which.

Two storage backends, chosen automatically by whether S3-style env vars are
set (see storage.py):
  - Local disk (<instance>/uploads/<school_id>/...), served back from
    /uploads/<...>, the default, zero-config path, used whenever those env
    vars are absent. Fine for local dev. NOT fine for Render or any host
    with an ephemeral/non-shared filesystem: a file saved this way is lost
    on the next deploy or restart, and isn't visible to a second instance.
  - S3-compatible object storage (Supabase Storage, or literally any other
    S3-compatible provider), used automatically once UPLOAD_* env vars are
    set. This is the one to use for anything actually deployed.
"""
from flask import Blueprint, jsonify, request

from app.extensions import limiter
from app.utils.tenancy import current_school_id, jwt_required_scoped
from app.utils.storage import save_upload, StorageError

bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "zip"}
MAX_BYTES = 8 * 1024 * 1024  # 8 MB


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _content_matches_extension(head, ext, whole_size):
    """
    Check the first bytes of the file really look like what the extension claims, so a script or web
    page renamed to .png (or .pdf) is rejected. Not a virus scan, but it stops the common spoofing tricks.
    """
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if ext == "webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == "pdf":
        return head.lstrip().startswith(b"%PDF-")
    if ext in ("docx", "xlsx", "pptx", "zip"):
        return head.startswith((b"PK\x03\x04", b"PK\x05\x06"))
    if ext in ("doc", "xls", "ppt"):
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if ext == "txt":
        return b"\x00" not in head
    return False


@bp.post("")
@jwt_required_scoped
@limiter.limit("30 per minute")
def upload_file():
    """
    kind=image restricts to image types (profile photo, school logo).
    kind=document (default) additionally allows common document/archive
    types (assignment attachments, submissions).
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    kind = request.args.get("kind", "document")
    allowed = IMAGE_EXTENSIONS if kind == "image" else (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS)
    ext = _ext(file.filename)
    if ext not in allowed:
        return jsonify({"error": f"Unsupported file type: .{ext}"}), 400

    import os
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_BYTES:
        return jsonify({"error": "File too large (max 8MB)"}), 400

    head = file.read(16)
    file.seek(0)
    if size == 0 or not _content_matches_extension(head, ext, size):
        return jsonify({"error": f"This file does not look like a real .{ext} file"}), 400

    school_id = current_school_id() or "platform"
    try:
        url = save_upload(file, school_id, ext)
    except StorageError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify({"url": url, "filename": file.filename, "size": size}), 201
