import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://localhost/hkr_hr_db",
)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    HKR_HR_ENV = os.getenv("HKR_HR_ENV", "development").strip().lower()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_ENABLED = True

    HKR_HR_UPLOAD_ROOT = Path(
        os.getenv("HKR_HR_UPLOAD_ROOT", str(BASE_DIR / "uploads"))
    )
    GENERATED_CONTRACT_ROOT = Path(
        os.getenv("GENERATED_CONTRACT_ROOT", str(BASE_DIR / "generated_contracts"))
    )
    CONTRACT_TEMPLATE_ROOT = Path(
        os.getenv("CONTRACT_TEMPLATE_ROOT", str(BASE_DIR / "contract_templates"))
    )
    PAYROLL_TEMPLATE_ROOT = Path(
        os.getenv("PAYROLL_TEMPLATE_ROOT", str(BASE_DIR / "payroll_templates"))
    )
    ATTENDANCE_BATCH_ROOT = Path(
        os.getenv(
            "ATTENDANCE_BATCH_ROOT",
            str(BASE_DIR / "uploads" / "_attendance_batches"),
        )
    )
    PAYROLL_OUTPUT_ROOT = Path(
        os.getenv("PAYROLL_OUTPUT_ROOT", str(BASE_DIR / "generated_payroll"))
    )

    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
