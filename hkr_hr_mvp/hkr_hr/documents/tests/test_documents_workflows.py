from tools.profile_revision import profile_revision
import io
import json
import re
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from sqlalchemy import inspect, text
from werkzeug.datastructures import FileStorage

from app import create_app
from models import (
    AuditLog,
    AttendanceBatch,
    AttendanceBatchItem,
    AttendanceMonthlySummary,
    AttendanceSegment,
    AttendanceSpecialDay,
    Employee,
    EmployeeAttendancePolicy,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveAllocation,
    EmployeeAnnualLeaveRecord,
    EmployeeAllowance,
    EmployeeBankAccount,
    EmployeeCertificate,
    EmployeeCompLeaveAllocation,
    EmployeeCompLeaveCredit,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeFinalPaymentCase,
    EmployeeIdentity,
    EmployeeAssignment,
    EmployeeQualification,
    EmployeeSalary,
    EmployeeMpfEnrollment,
    EmployeeVisa,
    EmployeeWorkInjuryPeriod,
    EmployeeWorkInjuryMonthlyExpense,
    GeneratedContract,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollRun,
    MpfScheme,
    ReferenceList,
    ReferenceValue,
    User,
    WorkProject,
    WorkCalendarHoliday,
    db,
)
from tools.hr_core import (
    annual_leave_buckets,
    annual_leave_days_between,
    annual_leave_summary,
    create_mpf_enrollment,
    employee_type_by_code,
    ensure_reference_seed,
    reference_by_code,
    store_employee_file,
    uploaded_file_sha256,
)
from tools.hk_statutory_holidays import (
    parse_hong_kong_public_holidays,
    parse_hong_kong_statutory_holidays,
)
from tools.final_payment import (
    calculate_benefit,
    calculate_final_payment,
    service_portion_days,
)
from tools.payroll_engine import (
    calculate_payroll,
    casual_daily_mpf,
    employee_warnings,
    forecast_tail,
)
from tools.attendance_policy import (
    automatic_attendance_rows,
    is_legacy_inferred_special_day_summary,
    special_work_day_units,
)
from routes.payroll import mpf_preview_rows, result_lines
from routes.attendance import (
    validate_attendance_segment_totals,
    validate_sunday_holiday_entries,
)
from tools.completeness import employee_data_items
from tools.releases import CURRENT_VERSION, NEXT_VERSION, RELEASES
from tools.schema_migrations import (
    apply_additive_migrations,
    repair_legacy_inferred_special_day_attendance,
    retire_obsolete_audit_events,
    retire_legacy_tables,
    schema_compatibility_issues,
)
from tools.security import (
    LoginRateLimiter,
    UploadValidationError,
    safe_next_url,
    validate_uploaded_file,
)


from tests.fixtures import (
    APP_ROOT,
    HrAppTestCase,
    current_profile_revision,
    pdf_bytes,
)


class DocumentsWorkflowTests(HrAppTestCase):
    def test_identical_document_and_attendance_require_confirmation(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "雜湊測試",
            "HASH TEST",
        )
        with self.app.app_context():
            project_id = WorkProject.query.filter_by(code="TMC046").one().id

        document_bytes = pdf_bytes("identical-document-content")
        first = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": "staff_record",
                "title": "First Staff Record",
                "file": (io.BytesIO(document_bytes), "first.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(first.status_code, 302)
        duplicate = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": "staff_record",
                "title": "Second Staff Record",
                "file": (io.BytesIO(document_bytes), "renamed-copy.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(duplicate.status_code, 200)
        duplicate_page = duplicate.get_data(as_text=True)
        self.assertIn("偵測到完全相同的文件", duplicate_page)
        token_match = re.search(
            r'name="duplicate_token" value="([^"]+)"',
            duplicate_page,
        )
        self.assertIsNotNone(token_match)
        with self.app.app_context():
            documents = EmployeeDocument.query.filter_by(
                employee_id=employee_id,
                category="staff_record",
            ).all()
            self.assertEqual(len(documents), 1)
            self.assertEqual(len(documents[0].content_sha256), 64)

        confirmed = self.client.post(
            f"/employees/{employee_id}/documents/duplicate",
            data={
                "duplicate_token": token_match.group(1),
                "action": "replace",
            },
            follow_redirects=False,
        )
        self.assertEqual(confirmed.status_code, 302)
        with self.app.app_context():
            documents = EmployeeDocument.query.filter_by(
                employee_id=employee_id,
                category="staff_record",
            ).order_by(EmployeeDocument.id).all()
            self.assertEqual(len(documents), 2)
            self.assertEqual(
                {document.content_sha256 for document in documents},
                {documents[0].content_sha256},
            )
            self.assertEqual(documents[0].status, "replaced")
            self.assertEqual(documents[1].status, "active")

        attendance_bytes = pdf_bytes("identical-attendance-content")
        for sequence in (1, 2):
            response = self.client.post(
                "/attendance/batches",
                data={
                    "year_month": "2026-07",
                    "files": [
                        (
                            io.BytesIO(attendance_bytes),
                            f"attendance-copy-{sequence}.pdf",
                        )
                    ],
                },
                content_type="multipart/form-data",
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            with self.app.app_context():
                item = AttendanceBatchItem.query.order_by(
                    AttendanceBatchItem.id.desc()
                ).first()
                self.assertEqual(len(item.content_sha256), 64)
                item_id = item.id
            form = {
                "employee_id": employee_id,
                "current_1_20_project_id": [str(project_id)],
                "current_1_20_working_days": ["17"],
                "current_1_20_ot_hours": ["2"],
                "current_1_20_holiday_days": ["0"],
                "current_1_20_large_ecall_count": ["0"],
                "current_1_20_ecall_count": ["0"],
                "previous_21_end_project_id": [str(project_id)],
                "previous_21_end_working_days": ["8"],
                "previous_21_end_ot_hours": ["0"],
                "previous_21_end_holiday_days": ["0"],
                "previous_21_end_large_ecall_count": ["0"],
                "previous_21_end_ecall_count": ["0"],
            }
            saved = self.client.post(
                f"/attendance/items/{item_id}/save",
                data=form,
                follow_redirects=False,
            )
            self.assertEqual(saved.status_code, 302)
            if sequence == 2:
                self.assertIn(
                    "duplicate_document_id=",
                    saved.headers["Location"],
                )
                warning = self.client.get(saved.headers["Location"])
                warning_page = warning.get_data(as_text=True)
                self.assertIn(
                    "此 PDF 與該員工本月已歸檔的考勤表完全一致",
                    warning_page,
                )
                form["confirm_duplicate"] = "1"
                confirmed_attendance = self.client.post(
                    f"/attendance/items/{item_id}/save",
                    data=form,
                    follow_redirects=False,
                )
                self.assertEqual(confirmed_attendance.status_code, 302)

        with self.app.app_context():
            attendance_documents = EmployeeDocument.query.filter_by(
                employee_id=employee_id,
                category="attendance_pdf",
                effective_month="2026-07",
            ).order_by(EmployeeDocument.id).all()
            self.assertEqual(len(attendance_documents), 2)
            self.assertEqual(attendance_documents[0].status, "replaced")
            self.assertEqual(attendance_documents[1].status, "active")
            self.assertEqual(
                attendance_documents[0].content_sha256,
                attendance_documents[1].content_sha256,
            )

    def test_staff_record_updates_profile_and_effective_bank_history(self):
        employee_id, _ = self.create_employee(
            "HKR", "site_monthly", "職員表測試", "STAFF RECORD TEST"
        )
        document_id = self.upload_document(
            employee_id,
            "staff_record",
            "staff-record-profile.pdf",
        )
        review_page = self.client.get(
            f"/documents/{document_id}/review"
        ).get_data(as_text=True)
        for field_name in (
            "residential_address",
            "emergency_contact_name",
            "emergency_contact_region_code",
            "emergency_contact_phone",
            "emergency_contact_relation",
            "bank_effective_from",
            "bank_currency",
        ):
            self.assertIn(f'name="{field_name}"', review_page)

        invalid = self.client.post(
            f"/documents/{document_id}/review",
            data={
                "title": "Staff Record profile",
                "residential_address": "88 Staff Record Road",
                "bank_name": "TEST BANK",
                "bank_effective_from": "2026-02-01",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(
            "銀行名稱及賬戶號碼必須同時填寫",
            invalid.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(
                EmployeeBankAccount.query.filter_by(
                    employee_id=employee_id
                ).count(),
                0,
            )

        response = self.client.post(
            f"/documents/{document_id}/review",
            data={
                "title": "Staff Record profile",
                "chinese_name": "職員表已核對",
                "english_name": "STAFF RECORD CONFIRMED",
                "gender": "female",
                "mobile_region_code": "+852",
                "mobile_number": "68889999",
                "email": "staff.record@example.test",
                "residential_address": "88 Staff Record Road",
                "emergency_contact_name": "緊急聯絡人",
                "emergency_contact_region_code": "+86",
                "emergency_contact_phone": "13800138000",
                "emergency_contact_relation": "家人",
                "education_level": "大學",
                "major": "工程",
                "graduation_school": "測試大學",
                "bank_effective_from": "2026-02-01",
                "bank_currency": "HKD",
                "bank_name": "TEST BANK",
                "bank_account_no": "99887766",
                "start_date": "2026-02-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            bank = EmployeeBankAccount.query.filter_by(
                employee_id=employee_id
            ).one()
            self.assertEqual(employee.chinese_name, "職員表已核對")
            self.assertEqual(employee.residential_address, "88 Staff Record Road")
            self.assertEqual(employee.emergency_contact_name, "緊急聯絡人")
            self.assertEqual(employee.emergency_contact_region_code, "+86")
            self.assertEqual(employee.emergency_contact_phone, "13800138000")
            self.assertEqual(employee.emergency_contact_relation, "家人")
            self.assertEqual(employee.current_period.start_date, date(2026, 2, 1))
            self.assertEqual(bank.effective_from, date(2026, 2, 1))
            self.assertEqual(bank.bank_name, "TEST BANK")
            self.assertEqual(bank.account_no, "99887766")
            self.assertEqual(bank.evidence_document_id, document_id)
            self.assertEqual(employee.bank_name, "TEST BANK")
            self.assertTrue(
                AuditLog.query.filter_by(
                    action="bank_account_added",
                    entity_type="EmployeeBankAccount",
                    entity_id=bank.id,
                ).first()
            )


if __name__ == "__main__":
    unittest.main()
