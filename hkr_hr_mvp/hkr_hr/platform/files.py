"""File storage and SHA-256 helpers shared across modules."""
from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import shutil

from flask import current_app
from werkzeug.utils import secure_filename

from hkr_hr.platform.security import validate_uploaded_file


def safe_employee_folder(employee):
    name = secure_filename(employee.employee_no or f"employee_{employee.id}")
    return name or f"employee_{employee.id}"


def unique_filename(original_filename):
    source = secure_filename(original_filename or "file")
    stem = Path(source).stem[:100] or "file"
    suffix = Path(source).suffix.lower()
    return f"{datetime.utcnow():%Y%m%d_%H%M%S_%f}_{stem}{suffix}"


def store_employee_file(employee, uploaded_file, category):
    validate_uploaded_file(uploaded_file)
    root = Path(current_app.config["HKR_HR_UPLOAD_ROOT"])
    folder = root / safe_employee_folder(employee) / category
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / unique_filename(uploaded_file.filename)
    uploaded_file.save(target)
    return target


def copy_file_to_employee(employee, source_path, original_filename, category):
    root = Path(current_app.config["HKR_HR_UPLOAD_ROOT"])
    folder = root / safe_employee_folder(employee) / category
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / unique_filename(original_filename)
    shutil.copy2(source_path, target)
    return target


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uploaded_file_sha256(uploaded_file):
    stream = uploaded_file.stream
    position = stream.tell()
    stream.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    stream.seek(position)
    return digest.hexdigest()


def employee_files_path(employee):
    return (
        Path(current_app.config["HKR_HR_UPLOAD_ROOT"])
        / safe_employee_folder(employee)
    )


def delete_employee_files(employee=None, folder=None):
    folder = Path(folder) if folder else employee_files_path(employee)
    if folder.exists():
        shutil.rmtree(folder)
