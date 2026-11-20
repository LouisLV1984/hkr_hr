import hmac
import io
import secrets
import threading
import time
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, request, session
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


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


def document_file_issue(document):
    """Physical availability is separate from a record's active/voided state."""
    try:
        path = Path(document.stored_path)
        if not path.is_file():
            return "review.file_unavailable"
        if path.stat().st_size == 0:
            return "upload.empty_file"
    except (OSError, TypeError, ValueError):
        return "review.file_unavailable"
    return None


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


def _validate_image(uploaded_file, image_format):
    """Decode without rewriting evidence; tolerate metadata after JPEG EOI.

    Work on a private buffer so Pillow cannot close/advance the upload stream.
    Do not enable LOAD_TRUNCATED_IMAGES or disable decompression-bomb limits.
    """
    stream = uploaded_file.stream
    position = stream.tell()
    try:
        stream.seek(0)
        content = stream.read()
        with Image.open(io.BytesIO(content), formats=[image_format]) as image:
            # Explicit bound, without changing process-wide Pillow settings in
            # the threaded server. The normal Pillow hard limit also remains.
            if image.width * image.height > 40_000_000:
                raise UploadValidationError("upload.image_too_large")
            image.verify()
        with Image.open(io.BytesIO(content), formats=[image_format]) as image:
            image.load()
    except Image.DecompressionBombError as exc:
        raise UploadValidationError("upload.image_too_large") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        if isinstance(exc, UploadValidationError):
            raise
        raise UploadValidationError("upload.invalid_file") from exc
    finally:
        stream.seek(position)


def validate_uploaded_file(uploaded_file, allowed_extensions=None):
    if not uploaded_file or not uploaded_file.filename:
        raise UploadValidationError("upload.file_required")
    allowed = set(allowed_extensions or ALLOWED_UPLOAD_EXTENSIONS)
    suffix = Path(uploaded_file.filename).suffix.lower()
    if suffix not in allowed:
        raise UploadValidationError("upload.pdf_only" if allowed == {".pdf"} else "upload.unsupported_type")
    head, tail, size = _read_head_and_tail(uploaded_file)
    if size <= 0:
        raise UploadValidationError("upload.empty_file")
    if suffix == ".pdf" and (not head.startswith(b"%PDF-") or b"%%EOF" not in tail):
        raise UploadValidationError("upload.invalid_pdf" if allowed == {".pdf"} else "upload.invalid_file")
    if suffix == ".pdf":
        position = uploaded_file.stream.tell()
        try:
            uploaded_file.stream.seek(0)
            reader = PdfReader(uploaded_file.stream)
            if reader.is_encrypted or not len(reader.pages):
                raise ValueError("PDF must contain readable pages")
            for page in reader.pages:
                # Resolve the page tree and page dimensions without rewriting evidence.
                if page.mediabox.width <= 0 or page.mediabox.height <= 0:
                    raise ValueError("Invalid PDF page")
        except Exception as exc:
            raise UploadValidationError("upload.invalid_pdf") from exc
        finally:
            uploaded_file.stream.seek(position)
    if suffix in {".jpg", ".jpeg", ".png"}:
        _validate_image(uploaded_file, "PNG" if suffix == ".png" else "JPEG")
    if suffix == ".docx":
        _validate_office_zip(uploaded_file, "word/document.xml")
    if suffix == ".xlsx":
        _validate_office_zip(uploaded_file, "xl/workbook.xml")
    return {
        "extension": suffix,
        "mime_type": CANONICAL_MIME_TYPES[suffix],
        "size": size,
    }
