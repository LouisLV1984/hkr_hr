import hmac
import secrets
import threading
import time
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, request, session


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx"}
CANONICAL_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class UploadValidationError(ValueError):
    pass


class LoginRateLimiter:
    def __init__(self, limit=5, window_seconds=15 * 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts = defaultdict(deque)
        self._lock = threading.Lock()

    def _key(self, username, remote_addr):
        return (
            str(username or "").strip().casefold(),
            str(remote_addr or "unknown"),
        )

    def _trim(self, attempts, now):
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()

    def retry_after(self, username, remote_addr):
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[self._key(username, remote_addr)]
            self._trim(attempts, now)
            if len(attempts) < self.limit:
                return 0
            return max(1, int(self.window_seconds - (now - attempts[0])))

    def record_failure(self, username, remote_addr):
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[self._key(username, remote_addr)]
            self._trim(attempts, now)
            attempts.append(now)

    def clear(self, username, remote_addr):
        with self._lock:
            self._attempts.pop(self._key(username, remote_addr), None)


login_rate_limiter = LoginRateLimiter()


def safe_next_url(candidate, fallback):
    if not candidate:
        return fallback
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return fallback
    if parsed.path.startswith("//") or "\\" in candidate:
        return fallback
    return candidate


def get_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def protect_csrf():
    if request.method in SAFE_METHODS:
        return
    supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRFToken")
    expected = session.get("_csrf_token")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        abort(400, description="security.csrf_failed")


def _read_head_and_tail(uploaded_file):
    stream = uploaded_file.stream
    position = stream.tell()
    stream.seek(0)
    head = stream.read(16)
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(max(0, size - 4096))
    tail = stream.read(4096)
    stream.seek(position)
    return head, tail, size


def _validate_office_zip(uploaded_file, required_member):
    stream = uploaded_file.stream
    position = stream.tell()
    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or required_member not in names:
                raise UploadValidationError("upload.invalid_file")
            bad_member = archive.testzip()
            if bad_member:
                raise UploadValidationError("upload.invalid_file")
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadValidationError("upload.invalid_file") from exc
    finally:
        stream.seek(position)


def validate_uploaded_file(uploaded_file, allowed_extensions=None):
    if not uploaded_file or not uploaded_file.filename:
        raise UploadValidationError("upload.file_required")
    allowed = set(allowed_extensions or ALLOWED_UPLOAD_EXTENSIONS)
    suffix = Path(uploaded_file.filename).suffix.lower()
    if suffix not in allowed:
        raise UploadValidationError("upload.unsupported_type")
    head, tail, size = _read_head_and_tail(uploaded_file)
    if size <= 0:
        raise UploadValidationError("upload.empty_file")
    if suffix == ".pdf" and (not head.startswith(b"%PDF-") or b"%%EOF" not in tail):
        raise UploadValidationError("upload.invalid_file")
    if suffix == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise UploadValidationError("upload.invalid_file")
    if suffix in {".jpg", ".jpeg"} and not (
        head.startswith(b"\xff\xd8\xff") and tail.rstrip().endswith(b"\xff\xd9")
    ):
        raise UploadValidationError("upload.invalid_file")
    if suffix == ".docx":
        _validate_office_zip(uploaded_file, "word/document.xml")
    if suffix == ".xlsx":
        _validate_office_zip(uploaded_file, "xl/workbook.xml")
    return {
        "extension": suffix,
        "mime_type": CANONICAL_MIME_TYPES[suffix],
        "size": size,
    }
