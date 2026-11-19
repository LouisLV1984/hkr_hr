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


APP_ROOT = Path(__file__).resolve().parents[1]


def current_profile_revision(app, employee_id, scope="all"):
    with app.app_context():
        return profile_revision(db.session.get(Employee, employee_id), scope)



def pdf_bytes(label):
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_metadata({"/Title": label})
    content = io.BytesIO()
    writer.write(content)
    return content.getvalue()


class V1WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": (
                    f"sqlite:///{(temp_root / 'test.db').as_posix()}"
                ),
                "HKR_HR_UPLOAD_ROOT": temp_root / "uploads",
                "GENERATED_CONTRACT_ROOT": temp_root / "contracts",
                "CONTRACT_TEMPLATE_ROOT": APP_ROOT / "contract_templates",
                "PAYROLL_TEMPLATE_ROOT": APP_ROOT / "payroll_templates",
                "ATTENDANCE_BATCH_ROOT": temp_root / "attendance",
                "PAYROLL_OUTPUT_ROOT": temp_root / "payroll",
            }
        )
        with self.app.app_context():
            db.create_all()
            ensure_reference_seed()
            admin = User(username="admin", role="admin", active=True)
            admin.set_password("test-admin-password")
            hr_user = User(username="hr_test", role="hr", active=True)
            hr_user.set_password("test-hr-password")
            db.session.add_all([admin, hr_user])
            db.session.commit()
        self.client = self.app.test_client()
        self.login("admin", "test-admin-password")

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login(self, username, password):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def create_employee(self, type_code, group, chinese_name, english_name):
        with self.app.app_context():
            employee_type_id = employee_type_by_code(type_code).id
        response = self.client.post(
            "/employees/new",
            data={
                "employee_type_id": employee_type_id,
                "payroll_group": group,
                "chinese_name": chinese_name,
                "english_name": english_name,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = Employee.query.filter_by(
                chinese_name=chinese_name
            ).one()
            return employee.id, employee.employee_no

    def complete_employee(
        self,
        employee_id,
        group,
        project_code,
        salary_basis,
        salary_amount,
        identity_number,
        mobile,
        birth_date="1985-01-10",
        mpf_mode="regular",
    ):
        with self.app.app_context():
            project = WorkProject.query.filter_by(code=project_code).one()
            region = reference_by_code("work_region", "HK")
            department = reference_by_code(
                "department",
                "MANAGEMENT" if group == "management" else "SITE",
            )
            position = reference_by_code(
                "position",
                "PROJECT_MANAGER" if group == "management" else "WORKER",
            )
            employer = reference_by_code("employer", "HK_RIVER")
            payroll_entity = reference_by_code("payroll_entity", "HK_RIVER")
            none_social = reference_by_code(
                "social_insurance_entity",
                "NONE",
            )
            none_dispatch = reference_by_code(
                "labour_dispatch_entity",
                "NONE",
            )
            ids = {
                "project": project.id,
                "region": region.id,
                "department": department.id,
                "position": position.id,
                "employer": employer.id,
                "payroll_entity": payroll_entity.id,
                "social": none_social.id,
                "dispatch": none_dispatch.id,
            }
        response = self.client.post(
            f"/employees/{employee_id}/assignment",
            data={
                "effective_from": "2026-01-01",
                "region_id": ids["region"],
                "project_id": ids["project"],
                "department_id": ids["department"],
                "position_ids": [str(ids["position"])],
                "employer_id": ids["employer"],
                "payroll_entity_id": ids["payroll_entity"],
                "social_insurance_entity_id": ids["social"],
                "labour_dispatch_entity_id": ids["dispatch"],
                "payroll_group": group,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/salary",
            data={
                "effective_from": "2026-01-01",
                "salary_basis": salary_basis,
                "currency": "HKD",
                "amount": salary_amount,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/identities",
            data={
                "identity_type": "hkid",
                "identity_number": identity_number,
                "is_primary": "on",
                "is_long_term": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "all"),
                "gender": "male",
                "date_of_birth": birth_date,
                "mobile_region_code": "+852",
                "mobile_number": mobile,
                "email": f"{mobile}@example.test",
                "residential_address": "Acceptance test address",
                "bank_name": "BANK OF CHINA (HONG KONG) LIMITED",
                "bank_account_no": f"QA-{identity_number}",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            scheme_code = (
                "BCT_DAILY" if mpf_mode == "casual" else "BCOM_MONTHLY"
            )
            scheme = MpfScheme.query.filter_by(code=scheme_code).one()
            create_mpf_enrollment(
                employee,
                date(2026, 1, 1),
                scheme=scheme,
                member_account_no=f"MPF-{employee.employee_no}",
                contribution_mode=mpf_mode,
            )
            db.session.commit()
        return ids["project"]

    def upload_document(self, employee_id, category, filename):
        if category not in {
            "three_treasures",
            "staff_record",
            "signed_contract",
            "cv",
            "other",
        }:
            with self.app.app_context():
                employee = db.session.get(Employee, employee_id)
                uploaded = FileStorage(
                    stream=io.BytesIO(pdf_bytes(filename)),
                    filename=filename,
                    content_type="application/pdf",
                )
                digest = uploaded_file_sha256(uploaded)
                path = store_employee_file(employee, uploaded, category)
                document = EmployeeDocument(
                    employee=employee,
                    category=category,
                    title=filename,
                    original_filename=filename,
                    stored_path=str(path),
                    mime_type="application/pdf",
                    file_ext=".pdf",
                    file_size=path.stat().st_size,
                    content_sha256=digest,
                    status="active",
                    document_date=date(2026, 7, 1),
                )
                db.session.add(document)
                db.session.commit()
                return document.id
        response = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": category,
                "title": filename,
                "document_date": "2026-07-01",
                "file": (io.BytesIO(pdf_bytes(filename)), filename),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            document = EmployeeDocument.query.filter_by(
                employee_id=employee_id,
                category=category,
            ).order_by(EmployeeDocument.id.desc()).first()
            self.assertIsNotNone(document)
            self.assertTrue(Path(document.stored_path).is_file())
            return document.id

    def add_attendance(self, employees_and_projects):
        files = [
            (io.BytesIO(pdf_bytes(f"attendance-{index}")), f"attendance-{index}.pdf")
            for index in range(1, len(employees_and_projects) + 1)
        ]
        response = self.client.post(
            "/attendance/batches",
            data={"year_month": "2026-07", "files": files},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        batch_page = self.client.get(response.headers["Location"]).get_data(
            as_text=True
        )
        self.assertIn('data-attendance-upload-form', batch_page)
        self.assertIn('data-attendance-drop-zone', batch_page)
        self.assertNotIn('class="context-nav"', batch_page)
        self.assertNotIn('class="attendance-rail"', batch_page)
        self.assertIn("attendance-detail-page", batch_page)
        self.assertIn("data-pdf-viewer data-source=", batch_page)
        self.assertIn("<canvas data-pdf-canvas", batch_page)
        self.assertIn("退出詳情", batch_page)
        self.assertIn("attendance-detail-context", batch_page)
        self.assertIn('class="attendance-context-exit"', batch_page)
        self.assertIn('class="attendance-context-month"', batch_page)
        self.assertIn('class="attendance-context-actions"', batch_page)
        self.assertNotIn("workbench-actions-top", batch_page)
        self.assertIn("保存並下一份", batch_page)
        self.assertIn('id="attendance-project-dialog"', batch_page)
        self.assertNotIn('class="attendance-detail-head"', batch_page)
        self.assertEqual(batch_page.count("退出詳情"), 1)
        self.assertIn('class="attendance-period-table-head"', batch_page)
        self.assertNotIn('class="attendance-payroll-impact"', batch_page)
        self.assertIn("本月考勤", batch_page)
        self.assertIn("上月尾段核對", batch_page)
        self.assertNotIn('class="review-section transfer-box"', batch_page)
        self.assertIn('class="attendance-workbench"', batch_page)
        self.assertNotIn('class="workbench-left"', batch_page)
        with self.app.app_context():
            batch = AttendanceBatch.query.one()
            items = list(batch.items)
            self.assertEqual(len(items), len(employees_and_projects))
            item_ids = [item.id for item in items]
            batch_id = batch.id
        details_page = self.client.get(
            "/attendance?month=2026-07&view=details"
        ).get_data(as_text=True)
        self.assertIn("考勤詳情", details_page)
        self.assertIn('class="attendance-stats"', details_page)
        self.assertNotIn('class="attendance-upload-panel"', details_page)
        collection_page = self.client.get(
            f"/attendance?month=2026-07&view=collection&batch_id={batch_id}"
        ).get_data(as_text=True)
        self.assertIn('class="context-panel attendance-upload-panel"', collection_page)
        self.assertIn('class="intake-resume"', collection_page)
        self.assertIn('class="attendance-pdf-card"', collection_page)
        self.assertNotIn('class="attendance-workbench"', collection_page)
        policies_page = self.client.get(
            "/attendance?month=2026-07&view=policies"
        ).get_data(as_text=True)
        self.assertIn('class="panel attendance-policy-panel"', policies_page)
        self.assertNotIn('class="attendance-upload-panel"', policies_page)
        for index, ((employee_id, project_id), item_id) in enumerate(
            zip(employees_and_projects, item_ids),
            start=1,
        ):
            response = self.client.post(
                f"/attendance/items/{item_id}/save",
                data={
                    "employee_id": employee_id,
                    "current_1_20_project_id": [str(project_id)],
                    "current_1_20_working_days": ["17"],
                    "current_1_20_ot_hours": [str(index * 2)],
                    "current_1_20_holiday_days": ["3"],
                    "current_1_20_large_ecall_count": [str(index)],
                    "current_1_20_ecall_count": [str(index + 1)],
                    "current_21_end_forecast_project_id": [
                        str(project_id)
                    ],
                    "current_21_end_forecast_working_days": ["10"],
                    "current_21_end_forecast_holiday_days": ["0"],
                    "previous_21_end_project_id": [str(project_id)],
                    "previous_21_end_working_days": ["8"],
                    "previous_21_end_ot_hours": ["1"],
                    "previous_21_end_holiday_days": ["2"],
                    "previous_21_end_large_ecall_count": ["1"],
                    "previous_21_end_ecall_count": ["1"],
                    "previous_21_end_forecast_project_id": [
                        str(project_id)
                    ],
                    "previous_21_end_forecast_working_days": ["8"],
                    "previous_21_end_forecast_holiday_days": ["0"],
                    "remarks": f"考勤核對備註 {index}",
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
        if len(employees_and_projects) > 1:
            saved_employee_id = employees_and_projects[0][0]
            wrong_employee_id = employees_and_projects[1][0]
            locked_page = self.client.get(
                f"/attendance?month=2026-08&view=collection"
                f"&batch_id={batch_id}&item_id={item_ids[0]}"
                f"&employee_id={wrong_employee_id}"
            ).get_data(as_text=True)
            with self.app.app_context():
                saved_employee = db.session.get(Employee, saved_employee_id)
                saved_employee_no = saved_employee.employee_no
            self.assertIn("已保存的考勤歸屬", locked_page)
            self.assertIn("更正員工／月份", locked_page)
            self.assertIn("data-cross-project-open", locked_page)
            self.assertIn("跨項目分配", locked_page)
            self.assertIn("2026年7月", locked_page)
            self.assertIn(saved_employee_no, locked_page)
            self.assertIn(
                f'name="employee_id" value="{saved_employee_id}" '
                'data-attendance-employee',
                locked_page,
            )
            self.assertNotIn(
                f'name="employee_id" value="{wrong_employee_id}" '
                'data-attendance-employee',
                locked_page,
            )

    def test_complete_employee_document_attendance_payroll_flow(self):
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "驗收月工",
            "QA MONTHLY",
        )
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "驗收日工",
            "QA DAILY",
        )
        management_id, management_no = self.create_employee(
            "ASMTP",
            "management",
            "驗收管理",
            "QA MANAGEMENT",
        )
        monthly_project = self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA100001",
            "60000001",
        )
        daily_project = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "1600",
            "QA100002",
            "60000002",
            mpf_mode="casual",
        )
        management_project = self.complete_employee(
            management_id,
            "management",
            "UNASSIGNED",
            "monthly",
            "36000",
            "QA100003",
            "60000003",
        )

        staff_document_id = self.upload_document(
            monthly_id,
            "staff_record",
            "qa-staff-record.pdf",
        )
        response = self.client.post(
            f"/documents/{staff_document_id}/review",
            data={
                "title": "QA Staff Record",
                "email": "updated.monthly@example.test",
                "mobile_region_code": "+852",
                "mobile_number": "68810001",
                "start_date": "2026-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        for employee_id, suffix in (
            (monthly_id, "monthly"),
            (daily_id, "daily"),
            (management_id, "management"),
        ):
            self.upload_document(
                employee_id,
                "signed_contract",
                f"qa-{suffix}-signed-contract.pdf",
            )
            self.upload_document(
                employee_id,
                "bank_proof",
                f"qa-{suffix}-bank-proof.pdf",
            )

        self.add_attendance(
            [
                (monthly_id, monthly_project),
                (daily_id, daily_project),
                (management_id, management_project),
            ]
        )

        with self.app.app_context():
            self.assertEqual(
                AttendanceMonthlySummary.query.filter_by(
                    year_month="2026-07",
                    status="received",
                ).count(),
                3,
            )
            for summary in AttendanceMonthlySummary.query.filter_by(
                year_month="2026-07",
                status="received",
            ):
                self.assertEqual(
                    {
                        segment.period_kind
                        for segment in AttendanceSegment.query.filter_by(
                            summary_id=summary.id
                        )
                    },
                    {
                        "current_1_20",
                        "current_21_end_forecast",
                        "previous_21_end",
                        "previous_21_end_forecast",
                    },
                )
            rows = calculate_payroll("2026-07", "all")
            self.assertEqual(len(rows), 3)
            self.assertFalse(any(row["blockers"] for row in rows))
            daily = next(row for row in rows if row["group"] == "site_daily")
            self.assertTrue(
                any(line["ot_divisor"] == 10 for line in daily["lines"])
            )
            self.assertEqual(
                daily["large_ecall_amount"],
                Decimal("3200.00"),
            )
            self.assertEqual(daily["ecall_amount"], Decimal("1200.00"))
            self.assertEqual(
                daily["actual_previous_tail"],
                Decimal("18240.00"),
            )
            daily_forecast_days = sum(
                line["forecast_working_days"] + line["forecast_holiday_days"]
                for line in daily["lines"]
            )
            self.assertEqual(daily_forecast_days, 10)
            self.assertTrue(
                all(
                    line["forecast_holiday_days"] == 0
                    for line in daily["lines"]
                )
            )

        response = self.client.post(
            "/payroll/preview",
            data={"year_month": "2026-07", "payroll_group": "all"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            run = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertIsNotNone(run)
            run_id = run.id
            self.assertEqual(len(run.employee_results), 3)
            expected_payroll = {
                result.employee.employee_no: {
                    "group": (result.calculation_json or {}).get("group"),
                    "overpay": float(result.overpay_amount),
                    "underpay": float(result.underpay_amount),
                    "employee_mpf": float(result.employee_mpf),
                    "net": float(result.net_amount),
                    "ecall": float(
                        result.large_ecall_amount + result.ecall_amount
                    ),
                    "attendance_remarks": (
                        result.calculation_json or {}
                    ).get("attendance_remarks"),
                }
                for result in run.employee_results
            }
            self.assertEqual(
                expected_payroll[monthly_no]["attendance_remarks"],
                "考勤核對備註 1",
            )
        monthly_attendance_page = self.client.get(
            f"/employees/{monthly_id}?tab=attendance&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("考勤備註", monthly_attendance_page)
        self.assertIn("考勤核對備註 1", monthly_attendance_page)
        response = self.client.get(
            f"/payroll/runs/{run_id}/export?payroll_group=all"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names = sorted(archive.namelist())
            self.assertEqual(len(names), 3)
            sheets = set()
            employee_numbers = set()
            for name in names:
                workbook = load_workbook(
                    io.BytesIO(archive.read(name)),
                    data_only=False,
                )
                self.assertEqual(len(workbook.sheetnames), 1)
                self.assertEqual(workbook.calculation.calcMode, "auto")
                self.assertTrue(workbook.calculation.fullCalcOnLoad)
                self.assertTrue(workbook.calculation.forceFullCalc)
                sheets.add(workbook.sheetnames[0])
                sheet = workbook.active
                self.assertEqual(sheet["F4"].value, "2026-07")
                self.assertEqual(sheet["F4"].number_format, "@")
                self.assertEqual(
                    sheet["M4"].value if sheet.title == "日工" else sheet["N4"].value,
                    "01/07/2026 - 20/07/2026",
                )
                employee_numbers.update(
                    sheet.cell(row, 5).value
                    for row in range(7, sheet.max_row + 1)
                    if sheet.cell(row, 5).value
                )
                for row in range(7, sheet.max_row + 1):
                    employee_no = sheet.cell(row, 5).value
                    if employee_no not in expected_payroll:
                        continue
                    expected = expected_payroll[employee_no]
                    if sheet.title == "日工":
                        columns = {
                            "ecall": 19,
                            "overpay": 31,
                            "underpay": 32,
                            "employee_mpf": 36,
                            "employer_mpf": 37,
                            "total": 35,
                            "net": 42,
                        }
                        formula_columns = (12, 15, 18, 19, 22, 25, 26, 30, 35, 36, 37, 42)
                    else:
                        columns = {
                            "ecall": 20,
                            "overpay": 32,
                            "underpay": 33,
                            "employee_mpf": 37,
                            "employer_mpf": 38,
                            "total": 36,
                            "net": 43,
                        }
                        formula_columns = (13, 16, 19, 20, 23, 26, 27, 31, 36, 37, 38, 43)
                    for key in ("overpay", "underpay"):
                        column = columns[key]
                        self.assertAlmostEqual(
                            float(sheet.cell(row, column).value or 0),
                            expected[key],
                            places=2,
                        )
                    for column in formula_columns:
                        self.assertTrue(
                            str(sheet.cell(row, column).value).startswith("="),
                            f"{sheet.title}!{sheet.cell(row, column).coordinate}",
                        )
                    self.assertIn(
                        "400",
                        str(sheet.cell(row, columns["ecall"]).value),
                    )
                    self.assertIn(
                        "SUMIF",
                        str(sheet.cell(row, columns["employee_mpf"]).value),
                    )
                    total_formula = str(
                        sheet.cell(row, columns["total"]).value
                    )
                    if sheet.title == "日工":
                        self.assertEqual(
                            total_formula,
                            (
                                f"=ROUND(L{row}+O{row}+R{row}+S{row}"
                                f"+V{row}+Y{row}+Z{row}+AA{row}+AD{row}"
                                f"-AE{row}+AF{row}+AG{row}+AL{row},2)"
                            ),
                        )
                    else:
                        self.assertEqual(
                            total_formula,
                            (
                                f"=ROUND(M{row}+P{row}+S{row}+T{row}"
                                f"+W{row}+Z{row}+AA{row}+AB{row}+AE{row}"
                                f"-AF{row}+AG{row}+AH{row}+AM{row},2)"
                            ),
                        )
                    if expected["group"] == "site_daily":
                        self.assertIn(
                            "/10*1.5",
                            str(sheet.cell(row, 14).value),
                        )
                        daily_mpf_formula = str(
                            sheet.cell(row, columns["employee_mpf"]).value
                        )
                        self.assertIn("<280", daily_mpf_formula)
                        self.assertIn("<950", daily_mpf_formula)
                        self.assertIn("50", daily_mpf_formula)
                    ecall_header_column = (
                        19 if sheet.title == "日工" else 20
                    )
                    self.assertEqual(
                        sheet.cell(5, ecall_header_column).value,
                        "E-CALL",
                    )
                    self.assertIn(
                        "大 E-CALL",
                        sheet.cell(
                            row,
                            43 if sheet.title == "日工" else 44,
                        ).value,
                    )
                    if expected["attendance_remarks"]:
                        self.assertIn(
                            f"考勤備註：{expected['attendance_remarks']}",
                            sheet.cell(
                                row,
                                43 if sheet.title == "日工" else 44,
                            ).value,
                        )
            self.assertEqual(sheets, {"月工", "OFFICE", "日工"})
            self.assertTrue(
                {monthly_no, daily_no, management_no}.issubset(
                    employee_numbers
                )
            )

        attendance_export = self.client.get(
            "/export/attendance-summary?year_month=2026-07"
        )
        self.assertEqual(attendance_export.status_code, 200)
        attendance_book = load_workbook(io.BytesIO(attendance_export.data))
        attendance_sheet = attendance_book.active
        attendance_headers = [
            cell.value for cell in attendance_sheet[1]
        ]
        self.assertIn("大 E-CALL 次數", attendance_headers)
        self.assertIn("普通 E-CALL 次數", attendance_headers)
        daily_current = next(
            row
            for row in attendance_sheet.iter_rows(
                min_row=2,
                values_only=True,
            )
            if row[1] == daily_no and row[3] == "current_1_20"
        )
        self.assertEqual(daily_current[8:10], (2, 3))

        payroll_summary = self.client.get(
            f"/export/payroll-summary?run_id={run_id}"
        )
        self.assertEqual(payroll_summary.status_code, 200)
        payroll_book = load_workbook(io.BytesIO(payroll_summary.data))
        payroll_sheet = payroll_book.active
        payroll_headers = [cell.value for cell in payroll_sheet[1]]
        self.assertIn("大 E-CALL", payroll_headers)
        self.assertIn("普通 E-CALL", payroll_headers)
        daily_summary = next(
            row
            for row in payroll_sheet.iter_rows(
                min_row=2,
                values_only=True,
            )
            if row[2] == daily_no
        )
        self.assertAlmostEqual(float(daily_summary[8]), 3200.0, places=2)
        self.assertAlmostEqual(float(daily_summary[9]), 1200.0, places=2)

        salary_certificate = self.client.get(
            "/export/salary-certificate"
            f"?employee_id={monthly_id}"
            "&year_month=2026-07"
            "&issue_date=2026-07-31"
        )
        self.assertEqual(salary_certificate.status_code, 200)
        self.assertEqual(
            salary_certificate.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        certificate_book = load_workbook(
            io.BytesIO(salary_certificate.data),
            data_only=False,
        )
        certificate_sheet = certificate_book.active
        self.assertIn(
            "Employee Salary Certificate",
            certificate_sheet["A6"].value,
        )
        self.assertEqual(certificate_sheet["B9"].value, "QA MONTHLY")
        self.assertTrue(
            str(certificate_sheet["J9"].value).startswith("=")
        )
        self.assertIn(
            "31 July 2026",
            certificate_sheet["H19"].value,
        )

        with self.app.app_context():
            period = db.session.get(Employee, monthly_id).current_period
            signed_notice = (period.notice_period_value, period.notice_period_unit)
        response = self.client.post(
            f"/employees/{monthly_id}/contracts/generate",
            data={
                "template_code": "SITE",
                "contract_date": "2026-07-01",
                "effective_date": "2026-07-01",
                "annual_leave_days": "10",
                "notice_period_days": "7",
                "probation_months": "0",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        contract_response = self.client.get(response.headers["Location"])
        self.assertEqual(contract_response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(contract_response.data)) as archive:
            self.assertIn("README.txt", archive.namelist())
            docx_name = next(
                name for name in archive.namelist() if name.endswith(".docx")
            )
            with zipfile.ZipFile(
                io.BytesIO(archive.read(docx_name))
            ) as document:
                xml = document.read("word/document.xml").decode("utf-8")
                self.assertIn("驗收月工", xml)
                self.assertIn("享有10天", xml)
                self.assertIn("提前7天", xml)
                self.assertNotIn("{{ notice_period_text }}", xml)
        with self.app.app_context():
            self.assertEqual(GeneratedContract.query.count(), 1)
            contract = GeneratedContract.query.one()
            self.assertEqual(float(contract.annual_leave_days), 10.0)
            employee = db.session.get(Employee, monthly_id)
            self.assertEqual((employee.current_period.notice_period_value, employee.current_period.notice_period_unit), signed_notice)
        for template_name, annual_count, notice_count in (
            ("HKR_SITE_Employment_Contract_Template.docx", 1, 2),
            ("HKR_OFFICE_Employment_Contract_Template.docx", 1, 1),
        ):
            with zipfile.ZipFile(APP_ROOT / "contract_templates" / template_name) as template_zip:
                template_xml = template_zip.read(
                    "word/document.xml"
                ).decode("utf-8")
            self.assertEqual(
                template_xml.count("contract_annual_leave_text"),
                annual_count,
            )
            self.assertEqual(
                template_xml.count("notice_period_text"),
                notice_count,
            )

        employee_export = self.client.get("/export/employees")
        self.assertEqual(employee_export.status_code, 200)
        workbook = load_workbook(io.BytesIO(employee_export.data))
        self.assertEqual(
            workbook.sheetnames,
            [
                "員工資料總表",
                "證件及資歷",
                "任職及薪酬歷史",
                "附件索引",
            ],
        )
        exported_numbers = {
            workbook.active.cell(row, 1).value
            for row in range(2, workbook.active.max_row + 1)
        }
        self.assertTrue(
            {monthly_no, daily_no, management_no}.issubset(exported_numbers)
        )
        attachment_bundle = self.client.get(
            f"/employees/{monthly_id}/documents/bundle"
        )
        self.assertEqual(attachment_bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(attachment_bundle.data)) as archive:
            self.assertGreaterEqual(len(archive.namelist()), 3)

        attendance_bundle = self.client.get(
            "/export/attachments"
            "?bundle_group=attendance&year_month=2026-07"
        )
        self.assertEqual(attendance_bundle.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(attendance_bundle.data)) as archive:
            attendance_names = archive.namelist()
            self.assertEqual(len(attendance_names), 3)
            self.assertTrue(
                all("/attendance_pdf/" in name for name in attendance_names)
            )

        report_payroll = self.client.get(
            "/export/monthly-payroll"
            "?year_month=2026-07&payroll_group=all",
            follow_redirects=True,
        )
        self.assertEqual(report_payroll.status_code, 200)
        self.assertEqual(report_payroll.request.path, "/attendance-payroll")
        self.assertEqual(report_payroll.mimetype, "text/html")

        delete_id, delete_no = self.create_employee(
            "TE",
            "site_daily",
            "只供刪除測試",
            "DELETE ME",
        )
        response = self.client.post(
            f"/employees/{delete_id}/delete",
            data={"confirm_employee_no": delete_no},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Employee, delete_id))
            self.assertEqual(Employee.query.count(), 3)

    def test_attendance_rejects_period_day_totals_above_calendar_span(self):
        employee_id, _ = self.create_employee(
            "HKR", "site_daily", "考勤校驗測試", "ATTENDANCE VALIDATION"
        )
        created = self.client.post(
            "/attendance/batches",
            data={
                "files": [(
                    io.BytesIO(pdf_bytes("attendance-validation")),
                    "attendance-validation.pdf",
                )]
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(created.status_code, 302)
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.one().id
        response = self.client.post(
            f"/attendance/items/{item_id}/save",
            data={
                "year_month": "2026-07",
                "employee_id": employee_id,
                "current_1_20_project_id": [""],
                "current_1_20_working_days": ["20"],
                "current_1_20_holiday_days": ["1"],
            },
            follow_redirects=True,
        )
        self.assertIn("出勤合計不可超過 20 日", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(AttendanceBatchItem, item_id).summary_id)

    def test_admin_system_status_is_read_only_and_versioned(self):
        page = self.client.get("/admin/system")
        self.assertEqual(page.status_code, 200)
        source = page.get_data(as_text=True)
        self.assertIn("系統運行狀態", source)
        self.assertIn(CURRENT_VERSION, source)
        self.assertIn("此頁不執行備份、還原或資料庫升級", source)
        self.assertNotIn("立即備份", source)
        self.assertNotIn("立即還原", source)

    def test_attendance_pdf_month_can_be_corrected_by_repreview(self):
        employee_id, _ = self.create_employee(
            "HKR", "site_monthly", "月份更正測試", "MONTH CORRECTION"
        )
        project_id = self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-MONTH-001",
            "60000991",
        )
        created = self.client.post(
            "/attendance/batches",
            data={
                "files": [(
                    io.BytesIO(pdf_bytes("attendance-month-correction")),
                    "attendance-month-correction.pdf",
                )]
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(created.status_code, 302)
        with self.app.app_context():
            item = AttendanceBatchItem.query.one()
            item_id = item.id
            batch_id = item.batch_id
            self.assertRegex(item.year_month, r"^\d{4}-\d{2}$")

        form = {
            "year_month": "2026-07",
            "employee_id": employee_id,
            "current_1_20_project_id": [str(project_id)],
            "current_1_20_working_days": ["10"],
            "current_1_20_ot_hours": ["0"],
            "current_1_20_holiday_days": ["0"],
            "current_1_20_large_ecall_count": ["0"],
            "current_1_20_ecall_count": ["0"],
        }
        saved = self.client.post(
            f"/attendance/items/{item_id}/save",
            data=form,
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 302)
        with self.app.app_context():
            item = db.session.get(AttendanceBatchItem, item_id)
            summary_id = item.summary_id
            self.assertEqual(item.year_month, "2026-07")
            self.assertEqual(item.summary.year_month, "2026-07")
            self.assertEqual(item.summary.document.effective_month, "2026-07")
            run = PayrollRun(
                year_month="2026-07",
                payroll_group="site_monthly",
                rule_version="test",
            )
            db.session.add(run)
            db.session.flush()
            db.session.add(PayrollEmployeeResult(
                run=run,
                employee_id=employee_id,
                currency="HKD",
            ))
            db.session.commit()

        overview = self.client.get(
            f"/attendance?view=collection&batch_id={batch_id}"
        ).get_data(as_text=True)
        self.assertIn("重新預覽", overview)
        self.assertNotIn('name="year_month" value="2026-07"', overview)
        repreview = self.client.get(
            f"/attendance?view=collection&batch_id={batch_id}&item_id={item_id}"
        ).get_data(as_text=True)
        self.assertIn("已保存的考勤歸屬", repreview)
        self.assertIn("更正員工／月份", repreview)
        self.assertIn('name="year_month" value="2026-07"', repreview)
        self.assertIn("保存更正", repreview)
        correction_page = self.client.get(
            f"/attendance?view=collection&batch_id={batch_id}"
            f"&item_id={item_id}&correct_identity=1"
        ).get_data(as_text=True)
        self.assertIn("這份考勤所屬月份", correction_page)
        self.assertIn("正在更正考勤歸屬", correction_page)

        form["year_month"] = "2026-08"
        corrected = self.client.post(
            f"/attendance/summaries/{summary_id}/correct",
            data=form,
            follow_redirects=True,
        )
        self.assertEqual(corrected.status_code, 200)
        self.assertIn(
            "請重新核對及導出 Payroll",
            corrected.get_data(as_text=True),
        )
        with self.app.app_context():
            item = db.session.get(AttendanceBatchItem, item_id)
            summary = db.session.get(AttendanceMonthlySummary, summary_id)
            self.assertEqual(item.year_month, "2026-08")
            self.assertEqual(summary.year_month, "2026-08")
            self.assertEqual(summary.document.effective_month, "2026-08")
            audit = AuditLog.query.filter_by(
                action="attendance_corrected",
                entity_id=summary_id,
            ).order_by(AuditLog.id.desc()).first()
            self.assertEqual(audit.before_json["year_month"], "2026-07")
            self.assertEqual(audit.after_json["year_month"], "2026-08")
            db.session.add(AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-09",
                status="received",
            ))
            db.session.commit()

        form["year_month"] = "2026-09"
        conflict = self.client.post(
            f"/attendance/summaries/{summary_id}/correct",
            data=form,
            follow_redirects=True,
        )
        self.assertIn(
            "該員工在 2026-09 已有考勤",
            conflict.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(
                db.session.get(AttendanceMonthlySummary, summary_id).year_month,
                "2026-08",
            )

    def test_attendance_not_required_uses_default_full_attendance_and_is_reversible(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "無需考勤測試",
            "NO ATTENDANCE REQUIRED",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-NO-ATTENDANCE",
            "61110001",
        )

        landing = self.client.get("/attendance?month=2026-07&lang=en").get_data(as_text=True)
        self.assertIn('class="intake-resume"', landing)
        self.assertIn('data-attendance-upload-form>', landing)
        page = self.client.get("/attendance?month=2026-07&view=details&lang=en").get_data(
            as_text=True
        )
        self.assertIn(employee_no, page)
        self.assertNotIn('data-attendance-requirement="not_required"', page)
        self.assertIn('href="/attendance?month=2026-07&amp;view=details&amp;status=expected"', page)
        self.assertIn('href="/attendance?month=2026-07&amp;view=details&amp;status=missing"', page)
        self.assertIn('href="/attendance?month=2026-07&amp;view=details&amp;status=received"', page)
        self.assertNotIn('id="expected"', page)
        self.assertIn('id="missing"', page)
        self.assertNotIn('id="received"', page)
        self.assertIn("Current attendance month", page)
        self.assertIn("2026-07", page)
        self.assertIn(
            'href="/attendance-payroll?year_month=2026-07"',
            page,
        )

        missing_page = self.client.get(
            "/attendance?month=2026-07&view=details&status=missing&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="missing"', missing_page)
        self.assertIn(employee_no, missing_page)
        self.assertIn("Site workers (monthly)", missing_page)
        self.assertIn("TMC046", missing_page)

        expected_page = self.client.get(
            "/attendance?month=2026-07&view=details&status=expected&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="expected"', expected_page)
        self.assertIn(employee_no, expected_page)

        monthly_page = self.client.get(
            "/attendance?month=2026-07&view=monthly_exemptions&lang=en"
        ).get_data(as_text=True)
        self.assertIn(employee_no, monthly_page)
        self.assertIn("Specific-month attendance exemption", monthly_page)
        self.assertIn('id="attendance-policy-dialog"', monthly_page)
        self.assertIn('data-policy-action="exempt"', monthly_page)
        self.assertIn('data-policy-action="require"', monthly_page)

        response = self.client.post(
            "/attendance/monthly-exemptions/batch",
            data={
                "employee_ids": [str(employee_id)],
                "year_month": "2026-07",
                "action": "exempt",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response_html = response.get_data(as_text=True)
        self.assertIn("Exempt this month", response_html)
        received_tab = self.client.get(
            "/attendance?month=2026-07&view=details&status=received&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="received"', received_tab)
        self.assertNotIn('id="missing"', received_tab)
        payroll_page = self.client.get(
            "/attendance-payroll?year_month=2026-07&payroll_group=site_monthly"
        ).get_data(as_text=True)
        self.assertIn("Attendance exemptions: attendance is required by default", payroll_page)
        self.assertIn("No attendance PDF is required this month; payroll uses default full attendance with zero OT and E-CALL", payroll_page)
        dashboard_page = self.client.get(
            "/dashboard?month=2026-07"
        ).get_data(as_text=True)
        self.assertRegex(dashboard_page, r"0(?:<small>)? / 0")
        english_payroll = self.client.get(
            "/attendance-payroll?year_month=2026-07&payroll_group=site_monthly&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Attendance exemptions: attendance is required by default", english_payroll)
        self.client.get("/attendance?month=2026-07&lang=zh-Hant")

        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=employee_id,
                year_month="2026-07",
            ).one()
            self.assertEqual(summary.status, "not_required")
            self.assertIsNone(summary.document_id)
            self.assertEqual(
                {segment.period_kind for segment in summary.segments},
                {
                    "current_1_20",
                    "current_21_end_forecast",
                    "previous_21_end",
                    "previous_21_end_forecast",
                },
            )
            self.assertGreater(
                sum(
                    segment.working_days + segment.sunday_holiday_days
                    for segment in summary.segments
                    if segment.period_kind == "current_1_20"
                ),
                Decimal("0"),
            )
            self.assertTrue(
                all(
                    segment.ot_hours == 0
                    and segment.large_ecall_count == 0
                    and segment.ecall_count == 0
                    and segment.sunday_holiday_days == 0
                    for segment in summary.segments
                )
            )
            previous_actual = sorted(
                (
                    segment.project_id or 0,
                    segment.working_days,
                    segment.sunday_holiday_days,
                )
                for segment in summary.segments
                if segment.period_kind == "previous_21_end"
            )
            previous_forecast = sorted(
                (
                    segment.project_id or 0,
                    segment.working_days,
                    segment.sunday_holiday_days,
                )
                for segment in summary.segments
                if segment.period_kind == "previous_21_end_forecast"
            )
            self.assertEqual(previous_actual, previous_forecast)
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertFalse(payroll_row["blockers"])
            self.assertEqual(payroll_row["ot_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["large_ecall_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["ecall_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["overpay_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["underpay_amount"], Decimal("0.00"))
            self.assertIn(
                "本月無需考勤表，按預設全勤及零 OT／E-CALL 計算",
                payroll_row["warnings"],
            )
            self.assertEqual(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="attendance_not_required",
                ).count(),
                1,
            )

        response = self.client.post(
            "/attendance/monthly-exemptions/batch",
            data={
                "employee_ids": [str(employee_id)],
                "year_month": "2026-07",
                "action": "require",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("本月仍需考勤", response.get_data(as_text=True))
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=employee_id,
                year_month="2026-07",
            ).one()
            self.assertEqual(summary.status, "required")
            self.assertEqual(len(summary.segments), 0)
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertIn("考勤未收", payroll_row["blockers"])
            self.assertEqual(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="attendance_required",
                ).count(),
                1,
            )

        self.add_attendance([(employee_id, project_id)])
        with self.app.app_context():
            summary = AttendanceMonthlySummary.query.filter_by(
                employee_id=employee_id,
                year_month="2026-07",
            ).one()
            self.assertEqual(summary.status, "received")
            self.assertIsNotNone(summary.document_id)
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertFalse(payroll_row["blockers"])
            self.assertNotIn(
                "本月無需考勤表，按預設全勤及零 OT／E-CALL 計算",
                payroll_row["warnings"],
            )

    def test_legacy_calendar_sundays_are_not_paid_as_real_extra_work(self):
        employee_id, _employee_no = self.create_employee(
            "HKR",
            "management",
            "舊版日曆星期日測試",
            "LEGACY CALENDAR SUNDAY",
        )
        project_id = self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "65000",
            "QA-LEGACY-SUNDAY",
            "61110009",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="not_required",
                no_attendance_reason="舊版免交考勤",
            )
            db.session.add(summary)
            db.session.flush()
            for period_kind, ordinary_days, sunday_days in (
                ("current_1_20", "17", "3"),
                ("current_21_end_forecast", "9", "2"),
                ("previous_21_end", "10", "1"),
                ("previous_21_end_forecast", "10", "1"),
            ):
                db.session.add(
                    AttendanceSegment(
                        summary_id=summary.id,
                        period_kind=period_kind,
                        project_id=project_id,
                        working_days=Decimal(ordinary_days),
                        sunday_holiday_days=Decimal(sunday_days),
                    )
                )
            db.session.commit()
            self.assertTrue(is_legacy_inferred_special_day_summary(summary))

            payroll_row = calculate_payroll("2026-08", "management")[0]
            self.assertFalse(payroll_row["blockers"])
            self.assertEqual(payroll_row["holiday_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["overpay_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["underpay_amount"], Decimal("0.00"))
            self.assertEqual(payroll_row["gross_amount"], Decimal("65000.00"))
            self.assertTrue(
                any(
                    "真正額外工作" in warning
                    for warning in payroll_row["warnings"]
                )
            )

            self.assertEqual(
                repair_legacy_inferred_special_day_attendance(),
                1,
            )
            db.session.refresh(summary)
            self.assertTrue(
                all(
                    segment.sunday_holiday_days == 0
                    for segment in summary.segments
                )
            )
            self.assertFalse(is_legacy_inferred_special_day_summary(summary))
            self.assertEqual(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="attendance_legacy_special_days_repaired",
                ).count(),
                1,
            )
            self.assertEqual(
                repair_legacy_inferred_special_day_attendance(),
                0,
            )

            repaired_payroll_row = calculate_payroll(
                "2026-08",
                "management",
            )[0]
            self.assertEqual(
                repaired_payroll_row["gross_amount"],
                Decimal("65000.00"),
            )
            self.assertFalse(
                any(
                    "真正額外工作" in warning
                    for warning in repaired_payroll_row["warnings"]
                )
            )

            actual_segment = next(
                segment
                for segment in summary.segments
                if segment.period_kind == "current_1_20"
            )
            actual_segment.sunday_holiday_days = Decimal("1")
            db.session.add(
                AttendanceSpecialDay(
                    summary_id=summary.id,
                    segment_id=actual_segment.id,
                    period_kind="current_1_20",
                    project_id=project_id,
                    work_date=date(2026, 8, 2),
                    day_kind="sunday",
                    session="full_day",
                    handling="pay",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.commit()
            self.assertFalse(is_legacy_inferred_special_day_summary(summary))
            self.assertEqual(
                repair_legacy_inferred_special_day_attendance(),
                0,
            )
            real_work_payroll_row = calculate_payroll(
                "2026-08",
                "management",
            )[0]
            self.assertGreater(
                real_work_payroll_row["holiday_amount"],
                Decimal("0"),
            )
            self.assertGreater(
                real_work_payroll_row["gross_amount"],
                Decimal("65000"),
            )
            saved_summary_id = summary.id

        profile_page = self.client.get(
            f"/employees/{employee_id}?lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("月薪無需填寫", profile_page)
        self.assertIn("只記錄真正額外工作", profile_page)

        entry_page = self.client.get(
            f"/attendance?month=2026-08&summary_id={saved_summary_id}&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("選擇真正有工作的日期", entry_page)
        self.assertIn("系統自動合計日數", entry_page)

    def test_attendance_employee_search_excludes_departed_and_blocks_wheel_changes(self):
        active_id, active_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黃搜尋",
            "SEARCH ACTIVE",
        )
        departed_id, departed_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黃離職",
            "SEARCH DEPARTED",
        )
        self.complete_employee(
            active_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-SEARCH-ACTIVE",
            "61110101",
        )
        self.complete_employee(
            departed_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-SEARCH-DEPARTED",
            "61110102",
        )
        with self.app.app_context():
            active = db.session.get(Employee, active_id)
            active.current_assignment.effective_from = date(2026, 6, 1)
            departed = db.session.get(Employee, departed_id)
            departed.current_period.end_date = date(2026, 7, 31)
            departed.status = "departed"
            summary = AttendanceMonthlySummary(
                employee_id=active_id,
                year_month="2026-08",
                status="received",
            )
            db.session.add(summary)
            db.session.commit()
            summary_id = summary.id

        locked_page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertNotRegex(locked_page, r'<input[^>]+type="search"')
        self.assertIn("已保存的考勤歸屬", locked_page)
        page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}"
            "&correct_identity=1&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertRegex(page, r'<input[^>]+type="search"')
        self.assertNotIn("支持員工編號、英文姓名及繁簡體中文混合搜尋", page)
        self.assertIn("input.showPicker()", page)
        self.assertIn(active_no, page)
        self.assertIn("SEARCH ACTIVE", page)
        self.assertIn("黃搜尋", page)
        self.assertIn("黄搜寻", page)
        self.assertNotIn(departed_no, page)
        self.assertNotIn("SEARCH DEPARTED", page)
        self.assertIn("input[type='number']", page)
        self.assertIn("document.activeElement === input", page)

        profile = self.client.get(
            f"/employees/{active_id}?tab=employment&lang=zh-Hant"
        ).get_data(as_text=True)
        current_card = re.search(
            r'<article class="panel current-state-card">.*?當前任職.*?</article>',
            profile,
            re.S,
        )
        self.assertIsNotNone(current_card)
        self.assertIn("入職日期", current_card.group(0))
        self.assertIn("2026-01-01", current_card.group(0))
        self.assertNotIn("2026-06-01", current_card.group(0))

    def test_attendance_linked_leave_is_compact_actionable_and_type_specific(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "management",
            "假期聯動提示",
            "LEAVE LINK ALERT",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "31000",
            "QA-LEAVE-LINK",
            "61110109",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="received",
            )
            db.session.add_all(
                [
                    summary,
                    EmployeeAnnualLeaveRecord(
                    employee_id=employee_id,
                    leave_date=date(2026, 7, 14),
                    end_date=date(2026, 7, 21),
                    entitlement_year=2026,
                    days=Decimal("6.5"),
                    leave_type="annual",
                    status="active",
                    ),
                ]
            )
            db.session.commit()
            summary_id = summary.id

        page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}"
            "&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("本次考勤有 1 筆年假", page)
        self.assertIn("上月尾段", page)
        self.assertIn("需核對 2026-07-21–2026-07-21", page)
        self.assertIn("原記錄 2026-07-14–2026-07-21 · 6.5 日", page)
        self.assertIn("全薪 · 不計實際出勤，由系統另計年假薪酬", page)
        self.assertIn("請從實際出勤扣除相應 1 日／0.5 日", page)
        self.assertIn("HR 操作：", page)
        self.assertIn("前往假期與工傷", page)
        self.assertNotIn("病假憑證必須補交", page)

        with self.app.app_context():
            db.session.add(
                EmployeeAnnualLeaveRecord(
                    employee_id=employee_id,
                    leave_date=date(2026, 8, 5),
                    end_date=date(2026, 8, 5),
                    entitlement_year=2026,
                    days=Decimal("1"),
                    leave_type="sick",
                    status="active",
                )
            )
            db.session.commit()

        page = self.client.get(
            f"/attendance?month=2026-08&summary_id={summary_id}"
            "&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("本次考勤有 1 筆年假、1 筆病假", page)
        self.assertIn("依病假規則計薪", page)
        self.assertIn("病假憑證待補", page)

    def test_fixed_allowances_reject_daily_workers_and_show_daily_rate_rule(self):
        daily_id, _ = self.create_employee(
            "HKRD",
            "site_daily",
            "日工補貼限制",
            "DAILY ALLOWANCE BLOCK",
        )
        monthly_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "月工補貼提示",
            "MONTHLY ALLOWANCE NOTE",
        )
        self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "QA-DAILY-ALLOWANCE",
            "61110103",
            mpf_mode="casual",
        )
        self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-MONTHLY-ALLOWANCE",
            "61110104",
        )
        response = self.client.post(
            f"/employees/{daily_id}/allowances",
            data={
                "allowance_type": "meal",
                "effective_from": "2026-08-01",
                "amount": "60",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertIn(
            "固定補貼目前只支持月工及 OFFICE，不支持日工",
            response.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(
                EmployeeAllowance.query.filter_by(employee_id=daily_id).count(),
                0,
            )

        daily_profile = self.client.get(
            f"/employees/{daily_id}?tab=employment&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("固定補貼目前只支持月工及 OFFICE", daily_profile)
        self.assertNotIn('data-dialog-open="add-allowance-dialog"', daily_profile)
        monthly_profile = self.client.get(
            f"/employees/{monthly_id}?tab=employment&lang=zh-Hant"
        ).get_data(as_text=True)
        self.assertIn("每日金額 × 計薪曆日", monthly_profile)
        self.assertIn('data-dialog-open="add-allowance-dialog"', monthly_profile)
        self.assertIn("餐補／交通補貼為每日金額", monthly_profile)

    def test_empty_project_lines_never_create_mpf_only_payroll_rows(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "management",
            "MPF 分行測試",
            "MPF LINE TEST",
        )
        project_id = self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "60000",
            "QA-MPF-LINE",
            "61110105",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="received",
            )
            db.session.add(summary)
            db.session.flush()
            for period_kind in (
                "current_1_20",
                "current_21_end_forecast",
                "previous_21_end",
                "previous_21_end_forecast",
            ):
                db.session.add(
                    AttendanceSegment(
                        summary_id=summary.id,
                        period_kind=period_kind,
                        project_id=None,
                    )
                )
            db.session.commit()
            row = calculate_payroll("2026-08", "management")[0]
            self.assertEqual(row["employee_mpf"], Decimal("1500.00"))
            self.assertEqual(len(row["lines"]), 1)
            self.assertEqual(row["lines"][0]["project"].id, project_id)
            self.assertEqual(row["lines"][0]["base_amount"], Decimal("60000.00"))

            legacy_result = PayrollEmployeeResult(
                calculation_json={
                    "lines": [
                        {
                            "project": None,
                            "working_days": "31",
                            "holiday_days": "5",
                            "base_amount": "0",
                            "gross_amount": "0",
                        },
                        {
                            "project": project_id,
                            "working_days": "31",
                            "base_amount": "60000",
                            "gross_amount": "60000",
                        },
                    ]
                }
            )
            exported_lines = result_lines(legacy_result)
            self.assertEqual(len(exported_lines), 1)
            self.assertEqual(exported_lines[0]["project"], project_id)

    def test_new_employee_can_start_with_long_term_attendance_exemption(self):
        with self.app.app_context():
            employee_type_id = employee_type_by_code("HKR").id
        new_page = self.client.get("/employees/new?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Monthly attendance record required", new_page)
        self.assertIn("Attendance is required by default", new_page)

        response = self.client.post(
            "/employees/new?lang=en",
            data={
                "employee_type_id": employee_type_id,
                "payroll_group": "management",
                "chinese_name": "長期免交新員工",
                "english_name": "NEW LONG TERM EXEMPT",
                "requires_attendance": "0",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Long-term exempt", page)
        with self.app.app_context():
            employee = Employee.query.filter_by(
                english_name="NEW LONG TERM EXEMPT"
            ).one()
            policy = EmployeeAttendancePolicy.query.filter_by(
                employee_id=employee.id
            ).one()
            self.assertFalse(policy.requires_attendance)

    def test_long_term_attendance_policy_is_effective_dated_and_batch_reversible(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "長期免交測試",
            "LONG TERM EXEMPT",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-LONG-TERM",
            "61110002",
        )
        response = self.client.post(
            "/attendance/policies/batch",
            data={
                "employee_ids": [str(employee_id)],
                "effective_from_month": "2026-07",
                "action": "exempt",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn(employee_no, page)
        self.assertIn("長期免交", page)
        with self.app.app_context():
            policy = EmployeeAttendancePolicy.query.filter_by(
                employee_id=employee_id,
                effective_from_month="2026-07",
            ).one()
            self.assertFalse(policy.requires_attendance)
            july = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertFalse(july["blockers"])
            self.assertTrue(
                any("永久無需考勤表" in item for item in july["warnings"])
            )
            self.assertEqual(july["ot_amount"], Decimal("0.00"))
        payroll_page = self.client.get(
            "/attendance-payroll",
            query_string={
                "year_month": "2026-07",
                "payroll_group": "site_monthly",
                "status": "ready",
            },
        ).get_data(as_text=True)
        self.assertIn("payroll-summary-card active", payroll_page)
        self.assertIn(employee_no, payroll_page)
        self.assertIn("導出此員工 Payroll", payroll_page)
        self.assertIn("30,000.00", payroll_page)
        self.assertNotIn("payroll-person-preview", payroll_page)

        response = self.client.post(
            "/attendance/policies/batch",
            data={
                "employee_ids": [str(employee_id)],
                "effective_from_month": "2026-08",
                "action": "require",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertFalse(
                calculate_payroll("2026-07", "site_monthly")[0]["blockers"]
            )
            self.assertIn(
                "考勤未收",
                calculate_payroll("2026-08", "site_monthly")[0]["blockers"],
            )
            self.assertEqual(
                AuditLog.query.filter(
                    AuditLog.employee_id == employee_id,
                    AuditLog.action.in_(
                        [
                            "attendance_policy_exempted",
                            "attendance_policy_required",
                        ]
                    ),
                ).count(),
                2,
            )

    def test_attendance_policy_list_sorts_by_payroll_group(self):
        management_id, management_no = self.create_employee(
            "HKR",
            "management",
            "管理排序測試",
            "POLICY MANAGEMENT",
        )
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "日工排序測試",
            "POLICY DAILY",
        )
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "月工排序測試",
            "POLICY MONTHLY",
        )
        self.complete_employee(
            management_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "QA-POLICY-MGMT",
            "61231001",
        )
        self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "1000",
            "QA-POLICY-DAILY",
            "61231002",
        )
        self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "20000",
            "QA-POLICY-MONTHLY",
            "61231003",
        )

        ascending = self.client.get(
            "/attendance",
            query_string={
                "month": "2026-08",
                "view": "policies",
                "sort": "payroll_group",
                "direction": "asc",
            },
        ).get_data(as_text=True)
        self.assertLess(
            ascending.index(daily_no),
            ascending.index(monthly_no),
        )
        self.assertLess(
            ascending.index(monthly_no),
            ascending.index(management_no),
        )
        self.assertIn("Payroll 組別 ↑", ascending)
        self.assertIn("policy-actions-head", ascending)

        descending = self.client.get(
            "/attendance",
            query_string={
                "month": "2026-08",
                "view": "policies",
                "sort": "payroll_group",
                "direction": "desc",
            },
        ).get_data(as_text=True)
        self.assertLess(
            descending.index(management_no),
            descending.index(monthly_no),
        )
        self.assertLess(
            descending.index(monthly_no),
            descending.index(daily_no),
        )

    def test_employee_search_matches_traditional_and_simplified_names(self):
        traditional_id, traditional_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黃志強",
            "WONG CHI KEUNG",
        )
        simplified_id, simplified_no = self.create_employee(
            "HKR",
            "site_monthly",
            "黄美玲",
            "WONG MEI LING",
        )

        simplified_search = self.client.get(
            "/employees",
            query_string={"q": "黄", "status": "active"},
        ).get_data(as_text=True)
        self.assertIn(traditional_no, simplified_search)
        self.assertIn(simplified_no, simplified_search)

        traditional_search = self.client.get(
            "/employees",
            query_string={"q": "黃", "status": "active"},
        ).get_data(as_text=True)
        self.assertIn(traditional_no, traditional_search)
        self.assertIn(simplified_no, traditional_search)

        self.assertNotEqual(traditional_id, simplified_id)

    def test_departed_employee_is_missing_only_through_departure_month(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "離職考勤測試",
            "DEPARTED ATTENDANCE TEST",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "QA-DEPARTED-ATTENDANCE",
            "61110002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.end_date = date(2026, 7, 15)
            employee.status = "departed"
            db.session.commit()

        departure_month = self.client.get(
            "/attendance?month=2026-07&view=details&status=missing"
        ).get_data(as_text=True)
        self.assertIn(employee_no, departure_month)

        after_departure = self.client.get(
            "/attendance?month=2026-08&view=details&status=missing"
        ).get_data(as_text=True)
        self.assertNotIn(employee_no, after_departure)

    def test_v009_effective_status_leave_documents_and_mpf_scale(self):
        employee_id, employee_no = self.create_employee(
            "HKRD",
            "site_daily",
            "V009 驗收工人",
            "V009 ACCEPTANCE",
        )
        self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "V0090001",
            "61110001",
            mpf_mode="casual",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.notice_period_value = Decimal("7")
            employee.current_period.notice_period_unit = "day"
            db.session.commit()

        response = self.client.post(
            f"/employees/{employee_id}/terminate",
            data={
                "end_date": "2099-08-30",
                "reason": "company_termination",
                "average_wage": "30,000.00",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(employee.derived_status, "active")
            self.assertEqual(employee.status, "active")
            self.assertEqual(
                employee.scheduled_departure_date,
                date(2099, 8, 30),
            )
            self.assertGreater(
                employee.current_period.payment_in_lieu,
                Decimal("0"),
            )
        attendance_page = self.client.get(
            "/attendance?month=2099-08&view=details&status=missing"
        ).get_data(as_text=True)
        self.assertIn(employee_no, attendance_page)

        response = self.client.post(
            f"/employees/{employee_id}/termination/cancel",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertIsNone(employee.current_period.end_date)
            self.assertEqual(employee.derived_status, "active")

        self.assertEqual(
            annual_leave_days_between(
                date(2026, 8, 1),
                date(2026, 8, 2),
                "pm",
                "am",
            ),
            Decimal("1.0"),
        )
        response = self.client.post(
            f"/employees/{employee_id}/annual-leave",
            data={
                "start_date": "2026-08-01",
                "start_session": "pm",
                "end_date": "2026-08-02",
                "end_session": "am",
                "entitlement_year": "2026",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            leave = EmployeeAnnualLeaveRecord.query.one()
            leave_id = leave.id
            # Employee-aware leave excludes Sunday; Saturday PM on a 6-day
            # contract is half a day. The date-only helper above is unchanged.
            self.assertEqual(leave.days, Decimal("0.5"))
            self.assertEqual(leave.status, "active")

        response = self.client.post(
            f"/annual-leave/{leave_id}/update",
            data={
                "start_date": "2026-08-03",
                "start_session": "pm",
                "end_date": "2026-08-03",
                "end_session": "pm",
                "entitlement_year": "2026",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(EmployeeAnnualLeaveRecord, leave_id).days,
                Decimal("0.5"),
            )

        response = self.client.post(
            f"/annual-leave/{leave_id}/void",
            data={"reason": "驗收撤回"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                db.session.get(EmployeeAnnualLeaveRecord, leave_id).status,
                "voided",
            )

        old_document_id = self.upload_document(
            employee_id,
            "identity",
            "v009-old-identity.pdf",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.primary_identity.document_id = old_document_id
            db.session.commit()
        replacement = self.client.post(
            f"/documents/{old_document_id}/replace",
            data={
                "reason": "舊文件錯誤",
                "file": (
                    io.BytesIO(pdf_bytes("v009-replacement")),
                    "v009-new-identity.pdf",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(replacement.status_code, 200)
        with self.app.app_context():
            old_document = db.session.get(
                EmployeeDocument,
                old_document_id,
            )
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(old_document.status, "replaced")
            self.assertIsNotNone(old_document.replaced_by_document_id)
            self.assertEqual(
                employee.primary_identity.document_id,
                old_document.replaced_by_document_id,
            )
            self.assertEqual(
                employee.primary_identity.document.status,
                "active",
            )

        expected_scale = (
            ("279.99", "0", "10"),
            ("280", "15", "15"),
            ("349.99", "15", "15"),
            ("350", "20", "20"),
            ("449.99", "20", "20"),
            ("450", "25", "25"),
            ("549.99", "25", "25"),
            ("550", "30", "30"),
            ("649.99", "30", "30"),
            ("650", "35", "35"),
            ("749.99", "35", "35"),
            ("750", "40", "40"),
            ("849.99", "40", "40"),
            ("850", "45", "45"),
            ("949.99", "45", "45"),
            ("950", "50", "50"),
            ("1200", "50", "50"),
        )
        for income, employee_mpf, employer_mpf in expected_scale:
            self.assertEqual(
                casual_daily_mpf(Decimal(income)),
                (Decimal(employee_mpf), Decimal(employer_mpf)),
            )

    def test_reference_crud_persists_and_admin_acl(self):
        with self.app.app_context():
            education = ReferenceList.query.filter_by(
                code="education_level"
            ).one()
            list_id = education.id
        response = self.client.post(
            f"/references/{list_id}/values",
            data={"display_name": "驗收學歷", "remarks": "temporary"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            value = ReferenceValue.query.filter_by(
                list_id=list_id,
                normalized_name="驗收學歷".casefold(),
            ).one()
            value_id = value.id
        response = self.client.post(
            f"/references/values/{value_id}",
            data={
                "display_name": "驗收學歷已改名",
                "remarks": "",
                "active": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/references/values/{value_id}/archive",
            data={"action": "archive"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertFalse(db.session.get(ReferenceValue, value_id).active)
            self.assertIsNotNone(
                AuditLog.query.filter_by(
                    action="reference_archived",
                    entity_id=value_id,
                ).first()
            )
        self.client.post(
            f"/references/values/{value_id}/archive",
            data={"action": "restore"},
            follow_redirects=True,
        )
        response = self.client.post(
            f"/references/values/{value_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ReferenceValue, value_id))
            project = WorkProject.query.filter_by(code="TMC046").one()
            project_id = project.id
        response = self.client.post(
            f"/references/projects/{project_id}",
            data={
                "name": "HA Acceptance Project",
                "daily_ot_divisor": "10",
                "active": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.client.get("/references?list=projects")
        with self.app.app_context():
            self.assertEqual(
                db.session.get(WorkProject, project_id).name,
                "HA Acceptance Project",
            )
        html = response.get_data(as_text=True)
        self.assertIn('data-dialog-open="project-edit-', html)
        self.assertIn('name="contact_phone"', html)

        self.client.post("/logout")
        self.login("hr_test", "test-hr-password")
        references_page = self.client.get("/references").get_data(
            as_text=True
        )
        self.assertIn("/references/", references_page)
        hr_reference_create = self.client.post(
            f"/references/{list_id}/values",
            data={"display_name": "HR 可維護選項", "remarks": ""},
            follow_redirects=True,
        )
        self.assertEqual(hr_reference_create.status_code, 200)
        with self.app.app_context():
            hr_value = ReferenceValue.query.filter_by(
                list_id=list_id,
                normalized_name="hr 可維護選項",
            ).one()
            hr_value_id = hr_value.id
        hr_reference_delete = self.client.post(
            f"/references/values/{hr_value_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(hr_reference_delete.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(ReferenceValue, hr_value_id))

        hr_project_create = self.client.post(
            "/references/projects",
            data={
                "name": "HR 權限測試項目",
                "daily_ot_divisor": "9",
            },
            follow_redirects=True,
        )
        self.assertEqual(hr_project_create.status_code, 200)
        with self.app.app_context():
            hr_project = WorkProject.query.filter_by(
                name="HR 權限測試項目"
            ).one()
            hr_project_id = hr_project.id
        hr_project_delete = self.client.post(
            f"/references/projects/{hr_project_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(hr_project_delete.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(WorkProject, hr_project_id))
        for admin_path in (
            "/admin/users",
            "/admin/audit",
        ):
            self.assertEqual(self.client.get(admin_path).status_code, 403)
            self.assertNotIn(f'href="{admin_path}"', references_page)
        self.assertEqual(self.client.get("/admin/import").status_code, 404)
        self.assertEqual(
            self.client.get("/admin/import/template").status_code,
            404,
        )

    def test_reference_seed_is_idempotent_after_seed_label_is_renamed(self):
        with self.app.app_context():
            visa_list = ReferenceList.query.filter_by(
                code="visa_category"
            ).one()
            other = ReferenceValue.query.filter_by(
                list_id=visa_list.id,
                code="OTHER",
            ).one()
            other.display_name = "其他工作許可"
            other.normalized_name = other.display_name.casefold()
            db.session.commit()

            ensure_reference_seed()
            db.session.commit()

            rows = ReferenceValue.query.filter_by(
                list_id=visa_list.id,
                code="OTHER",
            ).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].display_name, "其他工作許可")
            self.assertTrue(rows[0].active)

    def test_reference_seed_includes_confirmed_hong_kong_july_holiday(self):
        with self.app.app_context():
            hong_kong = reference_by_code("work_region", "HK")
            holiday = WorkCalendarHoliday.query.filter_by(
                region_id=hong_kong.id,
                holiday_date=date(2026, 7, 1),
            ).one()
            self.assertTrue(holiday.active)
            self.assertEqual(
                holiday.name,
                "香港特別行政區成立紀念日",
            )

            holiday.active = False
            db.session.commit()
            ensure_reference_seed()
            self.assertFalse(
                WorkCalendarHoliday.query.filter_by(
                    region_id=hong_kong.id,
                    holiday_date=date(2026, 7, 1),
                ).one().active
            )

    def test_work_calendar_crud_and_archive_restore(self):
        with self.app.app_context():
            region = ReferenceValue.query.join(ReferenceList).filter(
                ReferenceList.code == "work_region",
                ReferenceValue.active.is_(True),
            ).first()
            self.assertIsNotNone(region)
            region_id = region.id

        page = self.client.get(
            "/references?list=work_calendar&calendar_year=2026"
        )
        self.assertEqual(page.status_code, 200)
        page_text = page.get_data(as_text=True)
        self.assertIn("工作日曆", page_text)
        self.assertIn(
            f"帶入 {date.today().year + 1} 年香港假日日曆",
            page_text,
        )

        created = self.client.post(
            "/references/work-calendar",
            data={
                "region_id": region_id,
                "holiday_date": "2026-12-26",
                "name": "測試法定假日",
                "calendar_scope": "statutory",
                "remarks": "calendar workflow",
            },
            follow_redirects=True,
        )
        self.assertEqual(created.status_code, 200)
        self.assertIn("測試法定假日", created.get_data(as_text=True))
        with self.app.app_context():
            item = WorkCalendarHoliday.query.filter_by(
                region_id=region_id,
                holiday_date=date(2026, 12, 26),
            ).one()
            item_id = item.id

        archived = self.client.post(
            f"/references/work-calendar/{item_id}/archive",
            data={"action": "archive"},
            follow_redirects=True,
        )
        self.assertEqual(archived.status_code, 200)
        with self.app.app_context():
            self.assertFalse(db.session.get(WorkCalendarHoliday, item_id).active)

        restored = self.client.post(
            f"/references/work-calendar/{item_id}/archive",
            data={"action": "restore"},
            follow_redirects=True,
        )
        self.assertEqual(restored.status_code, 200)
        with self.app.app_context():
            self.assertTrue(db.session.get(WorkCalendarHoliday, item_id).active)

    def test_hong_kong_statutory_holiday_parser_and_import(self):
        html = """
        <html><body><p>2027年的2天法定假日是：</p><table>
        <tr><td>1.</td><td>1月1日</td><td>1月1日</td></tr>
        <tr><td>2.</td><td>冬節 或 聖誕節 （由僱主選擇）</td>
        <td>12月22日 或 12月25日</td></tr>
        </table></body></html>
        """
        parsed = parse_hong_kong_statutory_holidays(
            html,
            2027,
        )
        self.assertEqual(
            parsed,
            [
                (date(2027, 1, 1), "1月1日"),
                (date(2027, 12, 25), "聖誕節"),
            ],
        )
        public_html = "<html><body><table>" + "".join(
            f"<tr><td>公眾假期 {day}</td><td>1月{day}日</td><td>星期一</td></tr>"
            for day in range(1, 18)
        ) + "</table></body></html>"
        public_parsed = parse_hong_kong_public_holidays(public_html, 2027)
        self.assertEqual(len(public_parsed), 17)
        imported_public = [
            (date(2027, 1, 1), "1月1日"),
            (date(2027, 4, 2), "耶穌受難節"),
        ]
        with self.app.app_context():
            hong_kong = reference_by_code("work_region", "HK")
            region_id = hong_kong.id
        with patch(
            "routes.references.fetch_hong_kong_statutory_holidays",
            return_value=parsed,
        ), patch(
            "routes.references.fetch_hong_kong_public_holidays",
            return_value=imported_public,
        ):
            response = self.client.post(
                "/references/work-calendar/import-hong-kong",
                data={
                    "calendar_year": "2027",
                },
                follow_redirects=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("新增 3 個日期", response.get_data(as_text=True))
        with self.app.app_context():
            rows = WorkCalendarHoliday.query.filter_by(
                region_id=region_id,
            ).filter(
                db.extract("year", WorkCalendarHoliday.holiday_date) == 2027
            ).order_by(WorkCalendarHoliday.holiday_date).all()
            self.assertEqual(len(rows), 3)
            january_first = next(
                row for row in rows if row.holiday_date == date(2027, 1, 1)
            )
            self.assertTrue(january_first.applies_to_statutory)
            self.assertTrue(january_first.applies_to_public)
            good_friday = next(
                row for row in rows if row.holiday_date == date(2027, 4, 2)
            )
            self.assertFalse(good_friday.applies_to_statutory)
            self.assertTrue(good_friday.applies_to_public)
            audit = AuditLog.query.filter_by(
                action="work_calendar_hk_imported"
            ).one()
            self.assertEqual(audit.after_json["year"], 2027)

    def test_employee_quick_reference_creation_and_return_context(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "快速選項驗收",
            "QUICK REFERENCE QA",
        )
        self.client.post("/logout")
        self.login("hr_test", "test-hr-password")

        created = self.client.post(
            "/references/quick-create",
            json={"list_code": "bank", "display_name": "驗收快速銀行"},
        )
        self.assertEqual(created.status_code, 200)
        created_payload = created.get_json()
        self.assertTrue(created_payload["created"])
        bank_id = created_payload["item"]["id"]

        duplicate = self.client.post(
            "/references/quick-create",
            json={"list_code": "bank", "display_name": "驗收快速銀行"},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.get_json()["created"])
        self.assertEqual(duplicate.get_json()["item"]["id"], bank_id)

        code_conflict = self.client.post(
            "/references/quick-create",
            json={"list_code": "position", "display_name": "Project Manager"},
        )
        self.assertEqual(code_conflict.status_code, 409)
        conflict_payload = code_conflict.get_json()
        self.assertFalse(conflict_payload["ok"])
        self.assertEqual(
            conflict_payload["error_code"],
            "reference_code_exists",
        )
        self.assertEqual(
            conflict_payload["existing_item"]["code"],
            "PROJECT_MANAGER",
        )
        with self.app.app_context():
            position_list = ReferenceList.query.filter_by(code="position").one()
            self.assertEqual(
                ReferenceValue.query.filter_by(
                    list_id=position_list.id,
                    code="PROJECT_MANAGER",
                ).count(),
                1,
            )

        bank_options = self.client.get(
            "/references/quick-options/bank"
        ).get_json()["items"]
        self.assertIn("驗收快速銀行", {
            item["display_name"] for item in bank_options
        })
        self.assertEqual(
            self.client.post(
                "/references/quick-create",
                json={
                    "list_code": "employee_type",
                    "display_name": "不應快速新增",
                },
            ).status_code,
            400,
        )

        with self.app.app_context():
            region_id = reference_by_code("work_region", "HK").id
        project = self.client.post(
            "/references/projects/quick-create",
            json={
                "name": "驗收快速項目",
                "region_id": region_id,
                "daily_ot_divisor": "10",
            },
        )
        self.assertEqual(project.status_code, 200)
        self.assertTrue(project.get_json()["created"])
        self.assertEqual(
            project.get_json()["item"]["daily_ot_divisor"], "10.00"
        )

        profile = self.client.get(
            f"/employees/{employee_id}?tab=personal"
        ).get_data(as_text=True)
        self.assertIn('data-ref-code="bank"', profile)
        self.assertIn('data-ref-code="projects"', profile)
        self.assertIn('class="quick-add-reference" type="button" hidden', profile)
        self.assertIn('data-add-label="新增銀行名稱"', profile)
        self.assertNotIn('aria-label="快速新增 銀行名稱">+</button>', profile)
        self.assertIn('id="quick-reference-dialog"', profile)

        return_to = f"/employees/{employee_id}?tab=personal"
        references = self.client.get(
            "/references",
            query_string={"list": "bank", "return_to": return_to},
        ).get_data(as_text=True)
        self.assertIn(f'href="{return_to.replace("&", "&amp;")}"', references)
        with self.app.app_context():
            education = ReferenceList.query.filter_by(
                code="education_level"
            ).one()
            education_id = education.id
        response = self.client.post(
            f"/references/{education_id}/values",
            data={
                "display_name": "返回路徑驗收",
                "return_to": return_to,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("return_to=", response.headers["Location"])

    def test_current_assignment_uses_position_and_prefills_adjustment(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "當前任職驗收",
            "CURRENT ASSIGNMENT QA",
        )
        empty_page = self.client.get(
            f"/employees/{employee_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("尚未建立任職資料", empty_page)
        self.assertIn("新增任職紀錄", empty_page)

        with self.app.app_context():
            region = reference_by_code("work_region", "HK")
            department = reference_by_code("department", "ENGINEERING")
            position = reference_by_code("position", "PROJECT_MANAGER")
            employer = reference_by_code("employer", "HK_RIVER")
            payroll_entity = reference_by_code("payroll_entity", "HK_RIVER")
            social = reference_by_code("social_insurance_entity", "NONE")
            dispatch = reference_by_code("labour_dispatch_entity", "NONE")
            ids = {
                "region": region.id,
                "department": department.id,
                "position": position.id,
                "employer": employer.id,
                "payroll": payroll_entity.id,
                "social": social.id,
                "dispatch": dispatch.id,
            }

        saved = self.client.post(
            f"/employees/{employee_id}/assignment",
            data={
                "effective_from": "2015-04-13",
                "region_id": ids["region"],
                "project_id": "",
                "department_id": ids["department"],
                "position_ids": [str(ids["position"])],
                "employer_id": ids["employer"],
                "payroll_entity_id": ids["payroll"],
                "social_insurance_entity_id": ids["social"],
                "labour_dispatch_entity_id": ids["dispatch"],
                "payroll_group": "management",
            },
            follow_redirects=True,
        )
        html = saved.get_data(as_text=True)
        self.assertIn("初始任職已保存，當前任職已建立。", html)
        self.assertIn("當前任職</span><h2>項目經理</h2>", html)
        self.assertIn("項目：未分配", html)
        self.assertIn("未分配", html)
        self.assertIn("5 天工作制", html)
        self.assertIn('data-dialog-open="add-assignment-dialog"', html)
        self.assertIn('id="add-assignment-dialog"', html)
        self.assertRegex(
            html,
            rf'(?s)name="region_id">.*?<option value="{ids["region"]}" selected>',
        )
        self.assertRegex(
            html,
            rf'(?s)<select class="multi-select-source" name="position_ids" multiple hidden.*?<option value="{ids["position"]}" selected>',
        )
        self.assertNotIn('name="position_ids" multiple size="4"', html)
        self.assertGreaterEqual(html.count('name="employer_id"'), 2)
        self.assertNotIn('type="hidden" name="employer_id"', html)

        future = self.client.post(
            f"/employees/{employee_id}/assignment",
            data={
                "effective_from": "2099-01-01",
                "region_id": ids["region"],
                "department_id": ids["department"],
                "position_ids": [str(ids["position"])],
                "employer_id": ids["employer"],
                "payroll_entity_id": ids["payroll"],
                "social_insurance_entity_id": ids["social"],
                "labour_dispatch_entity_id": ids["dispatch"],
                "payroll_group": "management",
                "workweek_days": "5.5",
            },
            follow_redirects=True,
        )
        future_html = future.get_data(as_text=True)
        self.assertIn("將於 2099-01-01 生效；目前任職暫不變", future_html)
        self.assertIn("當前任職</span><h2>項目經理</h2>", future_html)
        self.assertIn("5.5 天工作制", future_html)
        with self.app.app_context():
            future_assignment = EmployeeAssignment.query.filter_by(
                employee_id=employee_id,
                effective_from=date(2099, 1, 1),
            ).one()
            self.assertEqual(
                future_assignment.workweek_days,
                Decimal("5.5"),
            )

    def test_language_switch_and_page_smoke(self):
        routes = (
            "/dashboard",
            "/employees",
            "/employees/new",
            "/annual-leave",
            "/attendance",
            "/attendance-payroll?year_month=2026-07",
            "/exports",
            "/references",
            "/admin/users",
            "/admin/audit",
            "/updates",
            "/guide",
        )
        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, route)
        dashboard = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn('class="app-layout no-sidebar"', dashboard)
        self.assertIn('class="system-tabs"', dashboard)
        self.assertNotIn('class="app-shell"', dashboard)
        self.assertNotIn('class="context-nav"', dashboard)
        self.assertIn("考勤錄入", dashboard)
        self.assertIn("出糧", dashboard)
        self.assertIn('aria-current="page"', dashboard)
        attendance = self.client.get("/attendance").get_data(as_text=True)
        self.assertIn('class="app-layout"', attendance)
        self.assertIn('class="app-shell"', attendance)
        self.assertIn('class="context-nav"', attendance)
        self.assertIn("考勤詳情", attendance)
        self.assertIn("拖放 PDF 到此或點擊選擇", attendance)
        attendance_collection = self.client.get(
            "/attendance?view=collection"
        ).get_data(as_text=True)
        self.assertIn('data-attendance-upload-form', attendance_collection)
        self.assertIn("拖放 PDF 到此或點擊選擇", attendance_collection)
        self.assertIn(
            "批次只管理已上傳 PDF",
            attendance_collection,
        )
        payroll = self.client.get(
            "/attendance-payroll?year_month=2026-07"
        ).get_data(as_text=True)
        self.assertIn('class="app-shell"', payroll)
        self.assertIn("payroll-controls", payroll)
        self.assertIn("data-payroll-filter", payroll)
        self.assertNotIn("確認並保存本次計算", payroll)
        self.assertNotIn('class="payroll-layout"', payroll)
        english = self.client.get(
            "/employees/new?lang=en"
        ).get_data(as_text=True)
        self.assertIn("Create employee file", english)
        self.assertIn("Site workers (daily)", english)
        self.assertIn("HR workbench", english)
        self.assertNotIn("建立員工檔案", english)
        english_references = self.client.get(
            "/references?list=education_level&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Education level", english_references)
        self.assertIn("Archive option", english_references)
        self.assertNotIn("學歷", english_references)
        self.assertIn("Renaming updates existing displays and history", english_references)
        self.assertNotIn("System codes are hidden", english_references)
        project_references = self.client.get(
            "/references?list=projects&lang=en"
        ).get_data(as_text=True)
        self.assertNotIn("<th>Code</th>", project_references)
        self.assertNotIn('name="code"', project_references)
        english_payroll = self.client.get(
            "/attendance-payroll?year_month=2026-07&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Payroll period:", english_payroll)
        self.assertIn("each ordinary E-CALL adds HKD 400", english_payroll)
        self.assertIn("XLSX exports retain calculation formulas", english_payroll)
        self.assertIn(
            "Contractually explicit exceptions use monthly salary / calendar days",
            english_payroll,
        )
        self.assertNotIn("出糧週期", english_payroll)
        english_attendance = self.client.get(
            "/attendance?view=collection&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Drop PDFs here or click to choose", english_attendance)
        self.assertIn("A batch only groups uploaded PDFs", english_attendance)
        simplified = self.client.get(
            "/employees?lang=zh-Hans"
        ).get_data(as_text=True)
        self.assertIn("员工档案", simplified)
        self.assertIn("考勤录入", simplified)
        self.assertIn("每月工资表", simplified)
        self.assertNotIn("員工總覽", simplified)
        self.assertIn("退出登录", simplified)

    def test_effective_ranges_identity_uniqueness_and_reference_protection(self):
        first_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "資料可信測試一",
            "DATA TRUST ONE",
        )
        second_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "資料可信測試二",
            "DATA TRUST TWO",
        )
        today = date.today()
        earlier = today - timedelta(days=20)
        later = today - timedelta(days=10)
        future = today + timedelta(days=30)

        for effective_from, group in (
            (later, "site_monthly"),
            (earlier, "site_daily"),
            (future, "management"),
        ):
            response = self.client.post(
                f"/employees/{first_id}/assignment",
                data={
                    "effective_from": effective_from.isoformat(),
                    "payroll_group": group,
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)

        for effective_from, amount in (
            (later, "30000"),
            (earlier, "900"),
            (future, "33000"),
        ):
            response = self.client.post(
                f"/employees/{first_id}/salary",
                data={
                    "effective_from": effective_from.isoformat(),
                    "salary_basis": (
                        "daily" if effective_from == earlier else "monthly"
                    ),
                    "currency": "HKD",
                    "amount": amount,
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)

        duplicate = self.client.post(
            f"/employees/{first_id}/assignment",
            data={
                "effective_from": later.isoformat(),
                "payroll_group": "management",
            },
            follow_redirects=True,
        )
        self.assertIn("已有任職記錄", duplicate.get_data(as_text=True))

        with self.app.app_context():
            employee = db.session.get(Employee, first_id)
            assignments = sorted(
                EmployeeAssignment.query.filter_by(
                    employee_id=first_id,
                    status="active",
                ).all(),
                key=lambda item: item.effective_from,
            )
            salaries = sorted(
                EmployeeSalary.query.filter_by(
                    employee_id=first_id,
                    status="active",
                ).all(),
                key=lambda item: item.effective_from,
            )
            self.assertEqual(len(assignments), 3)
            self.assertEqual(
                assignments[0].effective_to,
                later - timedelta(days=1),
            )
            self.assertEqual(
                assignments[1].effective_to,
                future - timedelta(days=1),
            )
            self.assertIsNone(assignments[2].effective_to)
            self.assertEqual(employee.current_assignment.payroll_group, "site_monthly")
            self.assertEqual(employee.payroll_group, "site_monthly")
            self.assertEqual(salaries[0].effective_to, later - timedelta(days=1))
            self.assertEqual(salaries[1].effective_to, future - timedelta(days=1))
            self.assertEqual(employee.current_salary.amount, Decimal("30000.00"))
            employee_type_id = employee.employee_type_id

        added = self.client.post(
            f"/employees/{first_id}/identities",
            data={
                "identity_type": "hkid",
                "identity_number": "A123456(7)",
                "is_primary": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(added.status_code, 200)
        conflict = self.client.post(
            f"/employees/{second_id}/identities",
            data={
                "identity_type": "hkid",
                "identity_number": "a 123456-7",
                "is_primary": "on",
            },
            follow_redirects=True,
        )
        self.assertIn("已屬於", conflict.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                EmployeeIdentity.query.filter_by(
                    identity_type="hkid",
                    status="active",
                ).count(),
                1,
            )

        blocked_delete = self.client.post(
            f"/references/values/{employee_type_id}/delete",
            follow_redirects=True,
        )
        self.assertIn("不能刪除", blocked_delete.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNotNone(
                db.session.get(ReferenceValue, employee_type_id)
            )

    def test_payroll_bank_details_are_separate_from_optional_document(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "銀行提示測試",
            "BANK WARNING TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            warnings = employee_warnings(employee)
            self.assertFalse(any("銀行" in warning for warning in warnings))
            bank_item = next(
                item
                for item in employee_data_items(employee)
                if item["code"] == "bank"
            )
            self.assertFalse(bank_item["ok"])
            payroll_row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertIn("出糧銀行資料未填寫", payroll_row["blockers"])

        page = self.client.get(
            f"/employees?month=2026-07&readiness=employee_data&status=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Payroll bank details not entered", page)
        self.assertNotIn("bank proof", page.lower())

    def test_employee_register_shows_month_effective_mpf_status_only_in_scope(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "management",
            "MPF 狀態測試",
            "MPF STATUS TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.employment_periods.append(
                EmployeeEmploymentPeriod(start_date=date(2026, 1, 1))
            )
            db.session.commit()

        missing_page = self.client.get(
            "/employees?month=2026-08&status=all"
        ).get_data(as_text=True)
        self.assertIn('data-mpf-status="missing"', missing_page)
        self.assertIn("MPF 資料未填寫", missing_page)

        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            scheme = MpfScheme.query.filter_by(code="BCOM_MONTHLY").one()
            create_mpf_enrollment(
                employee,
                date(2026, 8, 1),
                scheme=scheme,
                member_account_no="MPF-STATUS-001",
            )
            db.session.commit()

        complete_page = self.client.get(
            "/employees?month=2026-08&status=all"
        ).get_data(as_text=True)
        self.assertIn('data-mpf-status="complete"', complete_page)
        self.assertIn("MPF 資料已填寫", complete_page)
        simplified_page = self.client.get(
            "/employees?month=2026-08&status=all&lang=zh-Hans"
        ).get_data(as_text=True)
        self.assertIn("MPF 资料已填写", simplified_page)
        english_page = self.client.get(
            "/employees?month=2026-08&status=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn("MPF details entered", english_page)

        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.employment_periods[0].end_date = date(2026, 7, 31)
            db.session.commit()

        departed_page = self.client.get(
            "/employees?month=2026-08&status=all"
        ).get_data(as_text=True)
        self.assertNotIn("data-mpf-status=", departed_page)
        self.assertNotIn("MPF 資料已填寫", departed_page)
        self.assertNotIn("MPF 資料未填寫", departed_page)

    def test_search_fields_disable_browser_history_without_breaking_password_manager_tokens(self):
        base_source = (APP_ROOT / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("hkr-disabled-", base_source)
        self.assertIn('input[type="search"], [data-no-browser-history]', base_source)

        for relative_path in [
            "templates/attendance/index.html",
            "templates/employees/list.html",
            "templates/leave/index.html",
            "templates/payroll/index.html",
        ]:
            source = (APP_ROOT / relative_path).read_text(encoding="utf-8")
            search_controls = re.findall(r'<input type="search"[^>]*>', source)
            self.assertTrue(search_controls, relative_path)
            for control in search_controls:
                self.assertIn('autocomplete="off"', control, relative_path)
                self.assertIn('autocapitalize="off"', control, relative_path)
                self.assertIn('spellcheck="false"', control, relative_path)

        login_source = (APP_ROOT / "templates" / "auth" / "login.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('autocomplete="username"', login_source)
        self.assertIn('autocomplete="current-password"', login_source)

    def test_user_guide_page_and_release_alignment(self):
        self.assertEqual(CURRENT_VERSION, "V0.7.5")
        self.assertEqual(NEXT_VERSION, "V0.7.6")
        self.assertEqual(
            [(release["version"], release["date"]) for release in RELEASES],
            [
                ("V0.7.5", "2026-11-19"),
                ("V0.7.4", "2026-11-19"),
                ("V0.7.3", "2026-11-18"),
                ("V0.7.2", "2026-11-18"),
                ("V0.7.1", "2026-11-18"),
                ("V0.7.0", "2026-11-18"),
                ("V0.6.0", "2026-11-04"),
                ("V0.5.10", "2026-10-09"),
                ("V0.5.9", "2026-10-09"),
                ("V0.5.8", "2026-10-09"),
                ("V0.5.7", "2026-09-24"),
                ("V0.5.6", "2026-09-16"),
                ("V0.5.5", "2026-09-10"),
                ("V0.5.4", "2026-09-09"),
                ("V0.5.3", "2026-09-09"),
                ("V0.5.2", "2026-09-09"),
                ("V0.5.1", "2026-09-09"),
                ("V0.5.0", "2026-09-07"),
                ("V0.4.0", "2026-09-07"),
                ("V0.3.11", "2026-09-06"),
                ("V0.3.10", "2026-09-01"),
                ("V0.3.9", "2026-08-28"),
                ("V0.3.8", "2026-08-21"),
                ("V0.3.7", "2026-08-21"),
                ("V0.3.6", "2026-08-21"),
                ("V0.3.5", "2026-08-21"),
                ("V0.3.4", "2026-08-20"),
                ("V0.3.3", "2026-08-20"),
                ("V0.3.2", "2026-08-19"),
                ("V0.3.1", "2026-08-19"),
                ("V0.3.0", "2026-08-18"),
                ("V0.2.9", "2026-08-17"),
                ("V0.2.8", "2026-08-17"),
                ("V0.2.7", "2026-08-14"),
                ("V0.2.6", "2026-08-13"),
                ("V0.2.5", "2026-08-12"),
                ("V0.2.4", "2026-08-12"),
                ("V0.2.3", "2026-08-12"),
                ("V0.2.2", "2026-08-11"),
                ("V0.2.1", "2026-08-11"),
                ("V0.2.0", "2026-08-10"),
                ("V0.1.9", "2026-08-10"),
                ("V0.1.8", "2026-08-10"),
                ("V0.1.7", "2026-08-10"),
                ("V0.1.6", "2026-08-10"),
                ("V0.1.5", "2026-08-07"),
                ("V0.1.4", "2026-08-07"),
                ("V0.1.3", "2026-08-06"),
                ("V0.1.2", "2026-08-06"),
                ("V0.1.1", "2026-08-04"),
                ("V0.1.0", "2026-07-31"),
                ("V0.0.9", "2026-07-30"),
                ("V0.0.8", "2026-07-30"),
                ("V0.0.7", "2026-07-29"),
                ("V0.0.6", "2026-07-27"),
                ("V0.0.5", "2026-07-26"),
                ("V0.0.4", "2026-07-25"),
                ("V0.0.3", "2026-07-21"),
                ("V0.0.2", "2026-07-16"),
                ("V0.0.1", "2026-07-13"),
            ],
        )

        source = (APP_ROOT / "操作指南.md").read_text(encoding="utf-8")
        css_source = (APP_ROOT / "static" / "css" / "app.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".employee-readiness-wrap {", css_source)
        self.assertIn("max-height: calc(100vh - var(--header-height) - 205px);", css_source)
        self.assertIn(
            ".employee-readiness-wrap .employee-readiness-table thead th {",
            css_source,
        )
        self.assertIn(f"> 適用版本：{CURRENT_VERSION}", source)
        self.assertIn("本月無需考勤", source)
        self.assertIn("繁體或簡體搜尋", source)
        self.assertIn("離職後月份不再顯示", source)
        self.assertIn(f"> 更新日期：{RELEASES[0]['date']}", source)
        self.assertNotIn("適用對象：", source)
        self.assertIn("2026年8月1–20日（實際）", source)
        self.assertIn("2026年7月21–31日（原預估）", source)
        self.assertIn("上傳文件", source)
        self.assertIn("一般附件類型", source)
        self.assertIn("前往專項管理", source)
        self.assertIn("最小單位為 0.5 日", source)
        self.assertIn("撤回離職資料", source)
        self.assertIn("導出薪金證明書", source)
        self.assertIn("頁面會自動計算", source)
        self.assertIn("修正／撤回／替換／補件", source)
        self.assertIn("### 10.6 每月 MPF 供款表", source)
        self.assertIn("Member Account No.", source)
        self.assertIn("變更歷史", source)
        self.assertIn("離職 Payroll", source)
        self.assertIn("發薪單位", source)
        self.assertIn("手動例外補貼", source)

        response = self.client.get("/guide")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("HKR HR 操作指南", page)
        self.assertIn('href="/guide"', page)
        self.assertNotIn('href="/guide/download"', page)
        self.assertNotIn("下載 Markdown", page)
        self.assertNotIn("返回 Dashboard", page)
        self.assertIn("目前版本不使用 OCR", page)
        self.assertIn("Excel 會自動完整重算", page)

        english = self.client.get("/guide?lang=en").get_data(as_text=True)
        self.assertIn("<title>User Guide - HKR HR</title>", english)
        self.assertNotIn("Download Markdown", english)
        self.assertNotIn("Back to Dashboard", english)
        self.assertIn("HKR HR 操作指南", english)

        download = self.client.get("/guide/download")
        self.assertEqual(download.status_code, 404)

        self.client.post("/logout")
        protected = self.client.get("/guide")
        self.assertEqual(protected.status_code, 302)
        self.assertIn("/login", protected.headers["Location"])

    def test_record_editors_use_shared_dialogs(self):
        employee_template = (
            APP_ROOT / "templates" / "employees" / "detail.html"
        ).read_text(encoding="utf-8")
        leave_template = (
            APP_ROOT / "templates" / "leave" / "index.html"
        ).read_text(encoding="utf-8")
        change_history_template = (
            APP_ROOT / "templates" / "employees" / "_change_history.html"
        ).read_text(encoding="utf-8")
        combined = employee_template + change_history_template + leave_template

        self.assertNotIn("floating-editor", combined)
        self.assertNotIn("details class=\"row-editor\"", combined)
        self.assertGreaterEqual(combined.count("record-editor-form"), 20)
        self.assertIn("data-record-editor-trigger", combined)

    def test_employee_change_history_is_unified_without_duplicate_timeline(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "變更歷史測試",
            "CHANGE HISTORY TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "20000",
            "A1234567",
            "61234567",
        )

        page = self.client.get(
            f"/employees/{employee_id}?tab=employment"
        ).get_data(as_text=True)

        employment_panel = page.split(
            'data-panel="employment"', 1
        )[1].split('data-panel="credentials"', 1)[0]
        self.assertIn('class="dense-table change-history-table"', employment_panel)
        self.assertEqual(employment_panel.count('class="flag change-kind '), 3)
        self.assertEqual(employment_panel.count('class="record-audit-summary"'), 2)
        self.assertIn("2026-01-01", employment_panel)
        self.assertIn("HKD 20,000.00", employment_panel)
        self.assertIn("管理人員及總部人員", employment_panel)
        self.assertNotIn('class="panel profile-timeline"', employment_panel)
        self.assertNotIn('class="panel domain-timeline"', employment_panel)

    def test_profile_tabs_use_current_cards_scoped_editing_and_histories(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "統一介面測試",
            "UNIFIED PROFILE TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.education_level = "Bachelor"
            employee.major = "Engineering"
            employee.graduation_school = "Original School"
            employee.visa_required = True
            db.session.commit()

        response = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "profile"),
                "form_scope": "profile",
                "gender": "male",
                "mobile_region_code": "+852",
                "mobile_number": "61230000",
                "email": "profile@example.com",
                "residential_address": "Updated address",
                "emergency_contact_name": "Emergency Person",
                "emergency_contact_region_code": "+852",
                "emergency_contact_phone": "61239999",
                "emergency_contact_relation": "Family",
                "remarks": "Current profile",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(employee.education_level, "Bachelor")
            self.assertEqual(employee.graduation_school, "Original School")
            self.assertTrue(employee.visa_required)
            self.assertEqual(employee.mobile_number, "61230000")

        response = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "education"),
                "form_scope": "education",
                "education_level": "Master",
                "major": "Construction",
                "graduation_school": "Updated School",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(employee.mobile_number, "61230000")
            self.assertEqual(employee.education_level, "Master")
            self.assertTrue(
                AuditLog.query.filter_by(
                    employee_id=employee_id,
                    action="education_background_updated",
                ).first()
            )

        page = self.client.get(
            f"/employees/{employee_id}?tab=personal"
        ).get_data(as_text=True)
        self.assertIn("個人資料", page)
        self.assertIn('data-dialog-open="edit-personal-dialog"', page)
        self.assertIn("個人資料變更歷史", page)
        self.assertIn('class="dense-table profile-history-table"', page)

        credentials = self.client.get(
            f"/employees/{employee_id}?tab=credentials"
        ).get_data(as_text=True)
        self.assertIn("證件與資歷變更歷史", credentials)
        self.assertIn("Updated School", credentials)
        self.assertIn('data-dialog-open="education-editor-dialog"', credentials)

        status = self.client.get(
            f"/employees/{employee_id}?tab=employment_status"
        ).get_data(as_text=True)
        self.assertIn("任職狀態變更歷史", status)
        self.assertIn('data-dialog-open="termination-editor-dialog"', status)
        self.assertNotIn('details class="action-panel"', status)

        documents = self.client.get(
            f"/employees/{employee_id}?tab=documents"
        ).get_data(as_text=True)
        self.assertIn('class="dense-table document-library-table"', documents)

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

    def test_acceptance_fixes_for_admin_and_employee_defaults(self):
        users_page = self.client.get("/admin/users?lang=en")
        self.assertEqual(users_page.status_code, 200)
        users_html = users_page.get_data(as_text=True)
        self.assertIn("Existing users", users_html)
        self.assertIn("Add user", users_html)
        self.assertIn("Current account", users_html)
        self.assertIn('data-dialog-open="manage-user-', users_html)
        self.assertIn("Delete account", users_html)
        self.assertNotIn("/admin/import", users_html)
        self.assertEqual(self.client.get("/admin/import").status_code, 404)
        self.assertEqual(
            self.client.get("/admin/import/template").status_code,
            404,
        )

        with self.app.app_context():
            admin_id = User.query.filter_by(username="admin").one().id
        demotion = self.client.post(
            "/admin/users",
            data={
                "action": "update",
                "user_id": admin_id,
                "role": "hr",
                "active": "on",
            },
            follow_redirects=True,
        )
        self.assertIn(
            "不能移除目前登入帳戶的 Admin 權限",
            demotion.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(db.session.get(User, admin_id).role, "admin")

        self_delete = self.client.post(
            "/admin/users",
            data={"action": "delete", "user_id": admin_id},
            follow_redirects=True,
        )
        self.assertIn(
            "The signed-in account cannot be deleted.",
            self_delete.get_data(as_text=True),
        )

        with self.app.app_context():
            disposable = User(
                username="delete_me",
                role="hr",
                active=True,
            )
            disposable.set_password("temporary-password")
            db.session.add(disposable)
            db.session.flush()
            disposable_id = disposable.id
            historical_log = AuditLog(
                user_id=disposable_id,
                action="auth_login_success",
                entity_type="User",
                entity_id=disposable_id,
                detail="delete_me",
            )
            db.session.add(historical_log)
            db.session.commit()
            historical_log_id = historical_log.id
        deleted = self.client.post(
            "/admin/users",
            data={"action": "delete", "user_id": disposable_id},
            follow_redirects=True,
        )
        self.assertIn("User deleted.", deleted.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, disposable_id))
            self.assertIsNotNone(db.session.get(AuditLog, historical_log_id))
            self.assertIsNone(
                db.session.get(AuditLog, historical_log_id).user_id
            )
            deletion_log = AuditLog.query.filter_by(
                action="user_deleted",
                entity_id=disposable_id,
            ).one()
            self.assertEqual(deletion_log.detail, "delete_me")

        employee_id, _ = self.create_employee(
            "HKRD",
            "site_daily",
            "預設值驗收",
            "DEFAULT TEST",
        )
        profile = self.client.get(
            f"/employees/{employee_id}?tab=employment&lang=zh-Hant"
        )
        profile_html = profile.get_data(as_text=True)
        self.assertIn('value="+852" selected', profile_html)
        self.assertIn('value="daily" selected', profile_html)
        self.assertIn('value="HKD" selected', profile_html)
        self.assertIn("緊急聯絡電話", profile_html)

        saved = self.client.post(
            f"/employees/{employee_id}/personal",
            data={
                "profile_revision": current_profile_revision(self.app, employee_id, "all"),
                "mobile_region_code": "+852",
                "mobile_number": "61234567",
                "bank_name": "BANK OF CHINA (HONG KONG) LIMITED",
                "bank_account_no": "TEST-001",
                "mpf_mode": "regular",
            },
            follow_redirects=False,
        )
        self.assertEqual(saved.status_code, 302)
        self.assertIn("tab=personal", saved.headers["Location"])
        with self.app.app_context():
            saved_employee = db.session.get(Employee, employee_id)
            self.assertEqual(
                saved_employee.bank_name,
                "BANK OF CHINA (HONG KONG) LIMITED",
            )
            self.assertEqual(saved_employee.bank_account_no, "TEST-001")

        exports_page = self.client.get(
            "/exports?section=employees&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Employee records workbook", exports_page)
        self.assertIn("Employment and Salary History", exports_page)
        self.assertNotIn('name="warning"', exports_page)
        self.assertNotIn('name="expiry"', exports_page)
        self.assertNotIn("Management Overview", exports_page)

    def test_security_boundaries_and_friendly_errors(self):
        self.assertEqual(
            safe_next_url("https://example.com/steal", "/dashboard"),
            "/dashboard",
        )
        self.assertEqual(
            safe_next_url("/employees?status=active", "/dashboard"),
            "/employees?status=active",
        )
        limiter = LoginRateLimiter(limit=2, window_seconds=60)
        limiter.record_failure("admin", "127.0.0.1")
        self.assertEqual(limiter.retry_after("admin", "127.0.0.1"), 0)
        limiter.record_failure("admin", "127.0.0.1")
        self.assertGreater(limiter.retry_after("admin", "127.0.0.1"), 0)
        limiter.clear("admin", "127.0.0.1")
        self.assertEqual(limiter.retry_after("admin", "127.0.0.1"), 0)

        valid_pdf = FileStorage(
            stream=io.BytesIO(pdf_bytes("VALID")),
            filename="attendance.pdf",
            content_type="text/plain",
        )
        metadata = validate_uploaded_file(valid_pdf, {".pdf"})
        self.assertEqual(metadata["mime_type"], "application/pdf")
        disguised_pdf = FileStorage(
            stream=io.BytesIO(b"not a pdf"),
            filename="attendance.pdf",
            content_type="application/pdf",
        )
        with self.assertRaises(UploadValidationError):
            validate_uploaded_file(disguised_pdf, {".pdf"})

        with self.assertRaises(RuntimeError):
            create_app(
                {
                    "HKR_HR_ENV": "production",
                    "SECRET_KEY": "dev-change-me",
                }
            )

        missing = self.client.get("/this-page-does-not-exist?lang=en")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("Record not found", missing.get_data(as_text=True))

        self.app.config["CSRF_ENABLED"] = True
        login_page = self.client.get("/dashboard?lang=en")
        token_match = re.search(
            r'<meta name="csrf-token" content="([^"]+)"',
            login_page.get_data(as_text=True),
        )
        self.assertIsNotNone(token_match)
        self.client.post("/logout", data={"_csrf_token": token_match.group(1)})
        rejected = self.client.post(
            "/login?lang=en",
            data={"username": "admin", "password": "test-admin-password"},
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn(
            "Page verification has expired",
            rejected.get_data(as_text=True),
        )
        self.app.config["CSRF_ENABLED"] = False
        self.login("admin", "test-admin-password")

        audit_page = self.client.get("/admin/audit?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Login succeeded", audit_page)

    def test_dashboard_readiness_and_user_activity(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "待辦彙整測試",
            "GROUPED TASK TEST",
        )
        dashboard = self.client.get(
            "/dashboard?month=2026-08&lang=en"
        ).get_data(as_text=True)
        self.assertNotIn('class="readiness-employee"', dashboard)
        self.assertIn("Needs attention", dashboard)
        self.assertIn("Employee files", dashboard)
        self.assertIn("Attendance and payroll", dashboard)
        self.assertIn("Payroll status", dashboard)
        self.assertIn(employee_no, dashboard)

        register = self.client.get(
            "/employees?month=2026-08&readiness=needs_action&status=all&lang=en"
        ).get_data(as_text=True)
        self.assertIn(employee_no, register)
        self.assertIn("Employee file", register)
        self.assertIn(
            "Monthly attendance and payroll status (2026-08)",
            register,
        )
        self.assertEqual(register.count("Attendance not received"), 1)
        self.assertIn("Salary not set", register)
        self.assertIn("Staff Record not filed", register)
        self.assertIn("Employment Contract not filed", register)
        self.assertIn("Attendance not received", register)

        self.client.post("/logout", follow_redirects=True)
        with self.app.app_context():
            signed_out_admin = User.query.filter_by(username="admin").one()
            self.assertIsNotNone(signed_out_admin.last_logout_at)
            self.assertGreaterEqual(
                signed_out_admin.last_logout_at,
                signed_out_admin.last_login_at,
            )
        failed = self.login("admin", "wrong-password")
        self.assertIn("登入資料不正確", failed.get_data(as_text=True))
        self.login("admin", "test-admin-password")

        with self.app.app_context():
            failed_login = AuditLog.query.filter_by(
                action="auth_login_failed"
            ).one()
            failed_login.created_at = datetime(2026, 8, 11, 1, 2, 3)
            active_admin = User.query.filter_by(username="admin").one()
            active_admin.last_login_at = datetime.utcnow() - timedelta(hours=1)
            active_admin.last_logout_at = datetime.utcnow() - timedelta(minutes=30)
            active_admin.last_seen_at = datetime.utcnow()
            db.session.commit()

        users_page = self.client.get("/admin/users?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Account status", users_page)
        self.assertIn("Recent activity", users_page)
        self.assertIn("Online", users_page)

        login_activity = self.client.get(
            "/admin/audit?view=logins&lang=en"
        ).get_data(as_text=True)

        self.assertIn("Login succeeded", login_activity)
        self.assertIn("Login failed", login_activity)
        self.assertIn("Logged out", login_activity)
        self.assertIn("2026-08-11 09:02:03", login_activity)
        self.assertNotIn("HKT", login_activity)
        with self.app.app_context():
            actions = {
                row.action
                for row in AuditLog.query.filter(
                    AuditLog.action.in_(
                        {
                            "auth_login_success",
                            "auth_login_failed",
                            "auth_logout",
                        }
                    )
                )
            }
            self.assertEqual(
                actions,
                {"auth_login_success", "auth_login_failed", "auth_logout"},
            )

        payroll_template = load_workbook(
            APP_ROOT
            / "payroll_templates"
            / "Payroll_PC_AD014_V1_Template.xlsx",
            data_only=False,
        )
        self.assertEqual(payroll_template["月工"]["C6"].value, "Monthly Site Worker\n地盤月工")
        self.assertEqual(
            payroll_template["OFFICE"]["C6"].value,
            "Management / Office Staff\n管理及總部人員",
        )
        self.assertEqual(payroll_template["日工"]["C6"].value, "Daily Site Worker\n地盤日工")
        self.assertEqual(payroll_template["日工"]["J6"].value, "Daily salary standard\n日薪標準")
        self.assertTrue(str(payroll_template["日工"]["AP7"].value).startswith("="))
        payroll_template.close()

    def test_dashboard_confirmation_reminders_link_to_confirmation_editor(self):
        due_id, due_no = self.create_employee(
            "HKR",
            "management",
            "即將轉正",
            "CONFIRMATION DUE",
        )
        overdue_id, overdue_no = self.create_employee(
            "HKR",
            "management",
            "逾期轉正",
            "CONFIRMATION OVERDUE",
        )
        future_id, future_no = self.create_employee(
            "HKR",
            "management",
            "未到提醒期",
            "CONFIRMATION FUTURE",
        )
        confirmed_id, confirmed_no = self.create_employee(
            "HKR",
            "management",
            "已經轉正",
            "ALREADY CONFIRMED",
        )
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "月工試用期",
            "MONTHLY PROBATION",
        )
        today = date.today()
        with self.app.app_context():
            periods = {
                employee_id: EmployeeEmploymentPeriod(
                    employee_id=employee_id,
                    start_date=today - timedelta(days=100),
                )
                for employee_id in (
                    due_id,
                    overdue_id,
                    future_id,
                    confirmed_id,
                    monthly_id,
                )
            }
            periods[due_id].probation_end_date = today + timedelta(days=10)
            periods[overdue_id].probation_end_date = today - timedelta(days=2)
            periods[future_id].probation_end_date = today + timedelta(days=31)
            periods[confirmed_id].probation_end_date = today
            periods[confirmed_id].confirmation_date = today
            periods[monthly_id].probation_end_date = today
            db.session.add_all(periods.values())
            db.session.commit()

        dashboard = self.client.get(
            "/dashboard?month=2026-08&panel=confirmation&lang=en"
        ).get_data(as_text=True)
        dashboard = dashboard.split('id="confirmation-alerts"', 1)[1].split('</details>', 1)[0]
        self.assertIn("open", dashboard.split(">", 1)[0])
        self.assertIn("Employee confirmation reminders (2)", dashboard)
        self.assertIn(due_no, dashboard)
        self.assertIn(overdue_no, dashboard)
        self.assertNotIn(future_no, dashboard)
        self.assertNotIn(confirmed_no, dashboard)
        self.assertNotIn(monthly_no, dashboard)
        self.assertIn("Due in 10 day(s)", dashboard)
        self.assertIn("Overdue by 2 day(s)", dashboard)
        self.assertIn(
            f'/employees/{due_id}?tab=employment_status&amp;focus=probation',
            dashboard,
        )

        profile = self.client.get(
            f"/employees/{due_id}?tab=employment_status&focus=probation&lang=en"
        ).get_data(as_text=True)
        self.assertIn('id="probation-editor-dialog"', profile)
        self.assertIn('employeeDetailParams.get("focus") === "probation"', profile)
        self.assertIn("probation-editor-dialog", profile)

    def test_schema_compatibility_detects_legacy_columns(self):
        legacy_dir = tempfile.TemporaryDirectory()
        self.addCleanup(legacy_dir.cleanup)
        legacy_path = Path(legacy_dir.name) / "legacy.db"
        legacy_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "legacy-test",
                "SQLALCHEMY_DATABASE_URI": (
                    f"sqlite:///{legacy_path.as_posix()}"
                ),
            }
        )
        with legacy_app.app_context():
            db.session.execute(
                text(
                    "create table reference_lists ("
                    "id integer primary key, code varchar(64) not null)"
                )
            )
            db.session.execute(
                text(
                    "create table reference_values ("
                    "id integer primary key, list_id integer not null, "
                    "code varchar(64), display_name varchar(255) not null)"
                )
            )
            for table_name in (
                "employee_documents",
                "attendance_batch_items",
                "attendance_segments",
                "attendance_special_days",
                "payroll_employee_results",
                "payroll_project_lines",
            ):
                db.session.execute(
                    text(
                        f"create table {table_name} "
                        "(id integer primary key)"
                    )
                )
            db.session.commit()
            changed = apply_additive_migrations()
            self.assertIn(
                "attendance_segments.large_ecall_count",
                changed,
            )
            self.assertIn(
                "employee_documents.content_sha256",
                changed,
            )
            self.assertIn(
                "employee_documents.general_document_type_id",
                changed,
            )
            self.assertIn(
                "attendance_batch_items.content_sha256",
                changed,
            )
            self.assertIn(
                "attendance_batch_items.year_month",
                changed,
            )
            self.assertIn(
                "attendance_special_days.session",
                changed,
            )
            document_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "employee_documents"
                )
            }
            batch_item_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "attendance_batch_items"
                )
            }
            self.assertIn("content_sha256", document_columns)
            self.assertIn("general_document_type_id", document_columns)
            self.assertIn("content_sha256", batch_item_columns)
            self.assertIn("year_month", batch_item_columns)
            attendance_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "attendance_segments"
                )
            }
            self.assertTrue(
                {"large_ecall_count", "ecall_count"}.issubset(
                    attendance_columns
                )
            )
            result_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "payroll_employee_results"
                )
            }
            line_columns = {
                column["name"]
                for column in inspect(db.engine).get_columns(
                    "payroll_project_lines"
                )
            }
            self.assertTrue(
                {"large_ecall_amount", "ecall_amount"}.issubset(
                    result_columns
                )
            )
            self.assertTrue(
                {
                    "large_ecall_count",
                    "ecall_count",
                    "large_ecall_amount",
                    "ecall_amount",
                }.issubset(line_columns)
            )
            issues = schema_compatibility_issues()
            self.assertIn("reference_values", issues)
            self.assertIn("normalized_name", issues["reference_values"])
            db.session.remove()
            db.engine.dispose()

    def test_retired_workflow_tables_are_dropped_without_employee_loss(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "management",
            "保留員工測試",
            "KEEP EMPLOYEE TEST",
        )
        with self.app.app_context():
            db.session.execute(
                text(
                    "create table import_batches ("
                    "id integer primary key, batch_no varchar(80))"
                )
            )
            db.session.execute(
                text(
                    "insert into import_batches (id, batch_no) "
                    "values (1, 'LEGACY')"
                )
            )
            db.session.execute(
                text(
                    "create table employee_task_notes ("
                    "id integer primary key, employee_id integer, "
                    "task_code varchar(80), note text)"
                )
            )
            db.session.execute(
                text(
                    "insert into employee_task_notes "
                    "(id, employee_id, task_code, note) "
                    "values (1, :employee_id, 'legacy', 'retired')"
                ),
                {"employee_id": employee_id},
            )
            db.session.commit()
            retired_audit = AuditLog(
                user_id=User.query.filter_by(username="admin").one().id,
                employee_id=employee_id,
                action="bank_confirmed_for_payroll",
                entity_type="Employee",
                entity_id=employee_id,
                detail="retired bank confirmation",
            )
            db.session.add(retired_audit)
            db.session.commit()
            retired_audit_id = retired_audit.id
            self.assertIn("import_batches", inspect(db.engine).get_table_names())
            self.assertIn(
                "employee_task_notes",
                inspect(db.engine).get_table_names(),
            )

            removed = retire_legacy_tables()

            self.assertEqual(
                removed,
                ["import_batches", "employee_task_notes"],
            )
            self.assertNotIn(
                "import_batches",
                inspect(db.engine).get_table_names(),
            )
            self.assertNotIn(
                "employee_task_notes",
                inspect(db.engine).get_table_names(),
            )
            employee = db.session.get(Employee, employee_id)
            self.assertIsNotNone(employee)
            self.assertEqual(employee.employee_no, employee_no)
            self.assertEqual(retire_obsolete_audit_events(), 1)
            self.assertIsNone(db.session.get(AuditLog, retired_audit_id))
            self.assertIsNotNone(db.session.get(Employee, employee_id))

    def test_live_four_part_payroll_and_daily_mpf(self):
        employee_id, employee_no = self.create_employee(
            "HKRD",
            "site_daily",
            "四段計算測試",
            "FOUR PART TEST",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "FP100001",
            "62220001",
            mpf_mode="casual",
        )
        with self.app.app_context():
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-07",
                status="received",
            )
            db.session.add(summary)
            db.session.flush()
            for kind, days in (
                ("current_1_20", "10"),
                ("current_21_end_forecast", "5"),
                ("previous_21_end", "4"),
                ("previous_21_end_forecast", "6"),
            ):
                db.session.add(
                    AttendanceSegment(
                        summary_id=summary.id,
                        period_kind=kind,
                        project_id=project_id,
                        working_days=Decimal(days),
                    )
                )
            db.session.commit()
            row = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(row["employee"].employee_no, employee_no)
            self.assertEqual(row["current_actual_total"], Decimal("5500.00"))
            self.assertEqual(row["forecast_tail_total"], Decimal("2500.00"))
            self.assertEqual(row["actual_previous_tail"], Decimal("2000.00"))
            self.assertEqual(row["expected_previous_tail"], Decimal("3000.00"))
            self.assertEqual(row["gross_amount"], Decimal("7000.00"))
            self.assertEqual(row["overpay_amount"], Decimal("1000.00"))
            self.assertEqual(row["underpay_amount"], Decimal("0.00"))
            self.assertEqual(row["employee_mpf"], Decimal("350.00"))
            self.assertEqual(row["employer_mpf"], Decimal("350.00"))

        dashboard = self.client.get(
            "/dashboard?month=2026-07"
        ).get_data(as_text=True)
        self.assertIn("HKD 6,650.00", dashboard)

        page = self.client.get(
            "/attendance-payroll"
            "?year_month=2026-07&payroll_group=site_daily"
        ).get_data(as_text=True)
        self.assertIn("data-payroll-filter", page)
        self.assertIn("2026年7月1–20日（實際）", page)
        self.assertIn("2026年6月21–30日（原預估）", page)
        self.assertIn(
            'href="/attendance?month=2026-07"',
            page,
        )
        self.assertIn(
            'href="/mpf-contributions?year_month=2026-07"',
            page,
        )
        self.assertIn("請先選擇發薪單位", page)
        self.assertIn("/payroll/export-current", page)
        self.assertNotIn("確認並保存本次計算", page)
        self.assertNotIn("計算預覽", page)

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_daily",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        with self.app.app_context():
            run = PayrollRun.query.one()
            result = PayrollEmployeeResult.query.one()
            self.assertEqual(run.year_month, "2026-07")
            self.assertEqual(result.employee_id, employee_id)
            self.assertEqual(result.gross_amount, Decimal("7000.00"))

    def test_mpf_effective_records_preview_and_exports(self):
        with self.app.app_context():
            schemes = {
                item.code: item for item in MpfScheme.query.order_by(MpfScheme.code)
            }
            self.assertEqual(
                set(schemes),
                {
                    "BCT_SERIES_800",
                    "BCOM_MONTHLY",
                    "BCT_MONTHLY",
                    "BCT_DAILY",
                },
            )
            self.assertIsNone(schemes["BCT_SERIES_800"].payroll_group_no)
            self.assertEqual(schemes["BCT_DAILY"].calculation_mode, "casual")

        monthly_id, monthly_no = self.create_employee(
            "ASMTP",
            "management",
            "MPF 月工驗收",
            "MPF MONTHLY QA",
        )
        monthly_project = self.complete_employee(
            monthly_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "M1234567",
            "63330001",
        )
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "MPF 日工驗收",
            "MPF DAILY QA",
        )
        daily_project = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "D7654321",
            "63330002",
            mpf_mode="casual",
        )
        with self.app.app_context():
            new_scheme = MpfScheme.query.filter_by(code="BCT_MONTHLY").one()
            new_scheme_id = new_scheme.id
        response = self.client.post(
            f"/employees/{monthly_id}/mpf",
            data={
                "effective_from": "2026-05-01",
                "mpf_selection": str(new_scheme_id),
                "member_account_no": "MONTHLY-NEW-001",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("MPF 記錄已保存", response.get_data(as_text=True))

        with self.app.app_context():
            monthly = db.session.get(Employee, monthly_id)
            active_records = [
                item for item in monthly.mpf_enrollments if item.status == "active"
            ]
            self.assertEqual(len(active_records), 2)
            old_record = next(
                item for item in active_records if item.scheme.code == "BCOM_MONTHLY"
            )
            new_record = next(
                item for item in active_records if item.scheme.code == "BCT_MONTHLY"
            )
            self.assertEqual(old_record.effective_to, date(2026, 4, 30))
            self.assertIsNone(new_record.effective_to)
            new_record_id = new_record.id
            for employee_id, project_id in (
                (monthly_id, monthly_project),
                (daily_id, daily_project),
            ):
                summary = AttendanceMonthlySummary(
                    employee_id=employee_id,
                    year_month="2026-08",
                    status="received",
                )
                db.session.add(summary)
                db.session.flush()
                db.session.add_all(
                    [
                        AttendanceSegment(
                            summary_id=summary.id,
                            period_kind="current_1_20",
                            project_id=project_id,
                            working_days=Decimal("18"),
                        ),
                        AttendanceSegment(
                            summary_id=summary.id,
                            period_kind="current_21_end_forecast",
                            project_id=project_id,
                            working_days=Decimal("8"),
                        ),
                    ]
                )
            db.session.commit()

        profile = self.client.get(
            f"/employees/{monthly_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("當前薪酬及 MPF", profile)
        self.assertIn("變更歷史", profile)
        self.assertIn("銀聯（BCT）月工", profile)
        self.assertIn("MONTHLY-NEW-001", profile)

        page = self.client.get(
            "/mpf-contributions?year_month=2026-08"
        ).get_data(as_text=True)
        self.assertIn("MPF 供款表", page)
        self.assertIn(monthly_no, page)
        self.assertIn(daily_no, page)
        self.assertIn("下載全部 MPF ZIP", page)

        single = self.client.post(
            "/mpf-contributions/export",
            data={"year_month": "2026-08", "scheme_code": "BCT_MONTHLY"},
        )
        self.assertEqual(single.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument",
            single.content_type,
        )
        workbook = load_workbook(io.BytesIO(single.data), data_only=False)
        sheet = workbook["BILL_Submitted Employee(s)"]
        self.assertEqual(
            sheet["B2"].value,
            "HONG KONG RIVER ENGINEERING COMPANY LIMITED",
        )
        self.assertEqual(str(sheet["H2"].value), "53419540")
        self.assertEqual(sheet["J2"].value, "MONTHLY (CALENDAR MONTH)")
        self.assertEqual(sheet["A8"].value, "MPF MONTHLY QA")
        self.assertEqual(sheet["C8"].value, "MONTHLY-NEW-001")
        self.assertEqual(sheet["E8"].value, "APPROVED")
        self.assertIsNone(sheet["I8"].value)
        self.assertGreater(Decimal(str(sheet["H8"].value)), Decimal("0"))
        self.assertEqual(
            Decimal(str(sheet["J8"].value)),
            Decimal(str(sheet["K8"].value))
            + Decimal(str(sheet["L8"].value)),
        )

        archive_response = self.client.post(
            "/mpf-contributions/export",
            data={"year_month": "2026-08", "scheme_code": "all"},
        )
        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(archive_response.content_type, "application/zip")
        with zipfile.ZipFile(io.BytesIO(archive_response.data)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    "HKR_MPF_2026-08_BCT_DAILY.xlsx",
                    "HKR_MPF_2026-08_BCT_MONTHLY.xlsx",
                },
            )

        response = self.client.post(
            f"/mpf-enrollments/{new_record_id}/withdraw",
            data={"reason": "驗收撤回"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            monthly = db.session.get(Employee, monthly_id)
            active = [
                item for item in monthly.mpf_enrollments if item.status == "active"
            ]
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].scheme.code, "BCOM_MONTHLY")
            self.assertIsNone(active[0].effective_to)
            self.assertEqual(monthly.mpf_mode, "regular")

    def test_payroll_exports_ready_and_selected_employees_only(self):
        daily_id, daily_no = self.create_employee(
            "HKRD",
            "site_daily",
            "可出糧日工",
            "READY DAILY",
        )
        monthly_id, monthly_no = self.create_employee(
            "HKR",
            "site_monthly",
            "可出糧月工",
            "READY MONTHLY",
        )
        blocked_id, blocked_no = self.create_employee(
            "ASMTP",
            "management",
            "待補資料員工",
            "BLOCKED EMPLOYEE",
        )
        daily_project_id = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "READY-D-01",
            "61110001",
            mpf_mode="casual",
        )
        monthly_project_id = self.complete_employee(
            monthly_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "READY-M-01",
            "61110002",
        )
        with self.app.app_context():
            for employee_id, project_id in (
                (daily_id, daily_project_id),
                (monthly_id, monthly_project_id),
            ):
                summary = AttendanceMonthlySummary(
                    employee_id=employee_id,
                    year_month="2026-07",
                    status="received",
                )
                db.session.add(summary)
                db.session.flush()
                for kind, days in (
                    ("current_1_20", "15"),
                    ("current_21_end_forecast", "8"),
                    ("previous_21_end", "8"),
                    ("previous_21_end_forecast", "8"),
                ):
                    db.session.add(
                        AttendanceSegment(
                            summary_id=summary.id,
                            period_kind=kind,
                            project_id=project_id,
                            working_days=Decimal(days),
                        )
                    )
            db.session.commit()

        page = self.client.get(
            "/attendance-payroll?year_month=2026-07&payroll_group=all&status=all"
        ).get_data(as_text=True)
        self.assertIn("導出全部可出糧員工（2 人）", page)
        self.assertIn("導出此員工 Payroll", page)
        self.assertEqual(
            len(
                re.findall(
                    r"<input[^>]+data-payroll-employee-checkbox",
                    page,
                )
            ),
            2,
        )
        self.assertNotIn("payroll-person-preview", page)

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "ready",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        with self.app.app_context():
            run = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertEqual(
                {result.employee_id for result in run.employee_results},
                {daily_id, monthly_id},
            )

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "selected",
                "employee_ids": [daily_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        with self.app.app_context():
            run = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertEqual(
                [result.employee_id for result in run.employee_results],
                [daily_id],
            )

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "selected",
                "employee_ids": [daily_id, monthly_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "all",
                "scope": "selected",
                "employee_ids": [blocked_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(blocked_no, response.get_data(as_text=True))
        with self.app.app_context():
            latest = PayrollRun.query.order_by(PayrollRun.id.desc()).first()
            self.assertEqual(
                {result.employee_id for result in latest.employee_results},
                {daily_id, monthly_id},
            )
            self.assertNotIn(
                blocked_id,
                {result.employee_id for result in latest.employee_results},
            )
            self.assertEqual({daily_no, monthly_no}, {
                result.employee.employee_no
                for result in latest.employee_results
            })

    def test_record_corrections_and_withdrawals(self):
        employee_id, employee_no = self.create_employee(
            "HKR",
            "site_monthly",
            "修正流程測試",
            "CORRECTION TEST",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "WRONG-HKID",
            "63330001",
        )
        with self.app.app_context():
            identity = EmployeeIdentity.query.filter_by(
                employee_id=employee_id,
                status="active",
            ).one()
            identity_id = identity.id
            certificate_type_id = reference_by_code(
                "certificate_type",
                "SAFETY_CARD",
            ).id
            visa_category_id = reference_by_code(
                "visa_category",
                "ASMTP",
            ).id

        response = self.client.post(
            f"/identities/{identity_id}/update",
            data={
                "identity_type": "hkid",
                "identity_number": "A1234567",
                "is_primary": "on",
                "is_long_term": "on",
                "remarks": "更正測試",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("身份證件資料已更正", response.get_data(as_text=True))

        response = self.client.post(
            f"/employees/{employee_id}/certificates",
            data={
                "certificate_type_id": certificate_type_id,
                "certificate_no": "GREEN-WRONG",
                "valid_from": "2026-01-01",
                "expiry_date": "2027-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            certificate_id = EmployeeCertificate.query.filter_by(
                employee_id=employee_id
            ).one().id
        response = self.client.post(
            f"/certificates/{certificate_id}/update",
            data={
                "certificate_type_id": certificate_type_id,
                "certificate_no": "GREEN-CORRECT",
                "valid_from": "2026-02-01",
                "expiry_date": "2027-02-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/certificates/{certificate_id}/void",
            data={"reason": "整筆測試資料錯誤"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            f"/employees/{employee_id}/visas",
            data={
                "visa_category_id": visa_category_id,
                "visa_no": "VISA-QA",
                "issue_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/qualifications",
            data={
                "category": "skill",
                "qualification_name": "測試技能證書",
                "certificate_no": "SKILL-QA",
                "issue_date": "2026-01-01",
                "expiry_date": "2028-01-01",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2026",
                "entitled_days": "8.5",
                "legacy_days": "1.5",
                "remarks": "HR 確認",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            balance = EmployeeAnnualLeaveBalance.query.filter_by(
                employee_id=employee_id,
                year=2026,
            ).one()
            self.assertEqual(balance.entitled_days_override, Decimal("8.5"))
            legacy = EmployeeAnnualLeaveBalance.query.filter_by(
                employee_id=employee_id,
                year=2023,
            ).one()
            self.assertEqual(legacy.entitled_days_override, Decimal("1.5"))

        with self.app.app_context():
            audit = AuditLog.query.filter_by(
                action="identity_corrected"
            ).one()
            self.assertEqual(
                audit.before_json["identity_number"],
                "WRONG-HKID",
            )
            self.assertEqual(
                audit.after_json["identity_number"],
                "A1234567",
            )
            self.assertEqual(
                db.session.get(EmployeeCertificate, certificate_id).status,
                "voided",
            )

        page = self.client.get(
            f"/employees/{employee_id}?tab=credentials"
        ).get_data(as_text=True)
        self.assertIn("A1234567", page)
        self.assertIn("WRONG-HKID", page)
        self.assertIn("GREEN-CORRECT", page)
        self.assertIn("修正", page)
        self.assertIn("作廢", page)
        leave_page = self.client.get(
            f"/annual-leave?year=2026&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertIn(employee_no, leave_page)
        self.assertIn('value="8.5"', leave_page)

    def test_effective_records_can_be_corrected_or_withdrawn(
        self,
    ):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "任職薪酬修正測試",
            "EMPLOYMENT CORRECTION",
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "30000",
            "CORRECT1001",
            "63330002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            assignment = employee.current_assignment
            salary = employee.current_salary
            assignment_id = assignment.id
            salary_id = salary.id
            alternate_project_id = WorkProject.query.filter_by(
                code="PC_AD014"
            ).one().id
            original_project_id = assignment.project_id
            assignment_form = {
                "effective_from": "2026-02-15",
                "region_id": assignment.region_id,
                "project_id": alternate_project_id,
                "department_id": assignment.department_id,
                "position_ids": [
                    str(item.position_id) for item in assignment.positions
                ],
                "employer_id": assignment.employer_id,
                "payroll_entity_id": assignment.payroll_entity_id,
                "social_insurance_entity_id": (
                    assignment.social_insurance_entity_id
                ),
                "labour_dispatch_entity_id": (
                    assignment.labour_dispatch_entity_id
                ),
                "payroll_group": assignment.payroll_group,
                "remarks": "修正錯誤項目及生效日期",
            }

        response = self.client.post(
            f"/assignments/{assignment_id}/correct",
            data=assignment_form,
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("任職記錄已更正", response.get_data(as_text=True))
        response = self.client.post(
            f"/salaries/{salary_id}/correct",
            data={
                "effective_from": "2026-02-15",
                "salary_basis": "monthly",
                "currency": "HKD",
                "amount": "32,000.00",
                "remarks": "修正錯誤薪酬及生效日期",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("薪酬記錄已更正", response.get_data(as_text=True))

        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            assignment = db.session.get(
                type(employee.assignments[0]),
                assignment_id,
            )
            salary = db.session.get(type(employee.salaries[0]), salary_id)
            self.assertEqual(assignment.effective_from, date(2026, 2, 15))
            self.assertEqual(assignment.project_id, alternate_project_id)
            self.assertEqual(salary.effective_from, date(2026, 2, 15))
            self.assertEqual(salary.amount, Decimal("32000.00"))
            assignment_audit = AuditLog.query.filter_by(
                action="assignment_corrected"
            ).one()
            salary_audit = AuditLog.query.filter_by(
                action="salary_corrected"
            ).one()
            self.assertEqual(
                assignment_audit.before_json["project_id"],
                original_project_id,
            )
            self.assertEqual(
                assignment_audit.after_json["project_id"],
                alternate_project_id,
            )
            self.assertEqual(
                salary_audit.before_json["amount"],
                "30000.00",
            )
            self.assertEqual(
                salary_audit.after_json["amount"],
                "32000.00",
            )
        employment_page = self.client.get(
            f"/employees/{employee_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("更正任職記錄", employment_page)
        self.assertIn("TMC046 醫管局項目", employment_page)
        self.assertIn("PC AD014", employment_page)
        self.assertIn("更正薪酬記錄", employment_page)
        self.assertIn("30000.00", employment_page)
        self.assertIn("32000.00", employment_page)

        response = self.client.post(
            f"/salaries/{salary_id}/withdraw",
            data={"reason": "整筆薪酬記錄不應存在"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/assignments/{assignment_id}/withdraw",
            data={"reason": "整筆任職記錄不應存在"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            self.assertIsNone(employee.current_assignment)
            self.assertIsNone(employee.current_salary)
            self.assertEqual(
                AuditLog.query.filter_by(
                    action="assignment_withdrawn"
                ).count(),
                1,
            )
            self.assertEqual(
                AuditLog.query.filter_by(action="salary_withdrawn").count(),
                1,
            )

    def test_hard_delete_removes_attendance_and_payroll_orphans(self):
        employee_id, employee_no = self.create_employee(
            "HKRD",
            "site_daily",
            "刪除關聯測試",
            "DELETE RELATIONS",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "800",
            "DEL10001",
            "64440001",
            mpf_mode="casual",
        )
        self.add_attendance([(employee_id, project_id)])
        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_daily",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            batch_id = AttendanceBatch.query.one().id
            summary_id = AttendanceMonthlySummary.query.one().id
            run_id = PayrollRun.query.one().id
            upload_folder = (
                Path(self.app.config["HKR_HR_UPLOAD_ROOT"])
                / employee_no
            )
            self.assertTrue(upload_folder.exists())

        self.client.post("/logout")
        self.login("hr_test", "test-hr-password")
        denied = self.client.post(
            f"/employees/{employee_id}/delete",
            data={"confirm_employee_no": employee_no},
        )
        self.assertEqual(denied.status_code, 403)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Employee, employee_id))
        self.client.post("/logout")
        self.login("admin", "test-admin-password")

        response = self.client.post(
            f"/employees/{employee_id}/delete",
            data={"confirm_employee_no": employee_no},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("考勤及 Payroll 資料已全部刪除", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(Employee, employee_id))
            self.assertIsNone(
                db.session.get(AttendanceMonthlySummary, summary_id)
            )
            self.assertIsNone(db.session.get(AttendanceBatch, batch_id))
            self.assertIsNone(db.session.get(PayrollRun, run_id))
            self.assertEqual(
                AttendanceBatchItem.query.filter_by(
                    employee_id=employee_id
                ).count(),
                0,
            )
            self.assertEqual(
                PayrollEmployeeResult.query.filter_by(
                    employee_id=employee_id
                ).count(),
                0,
            )
            self.assertFalse(upload_folder.exists())
        attendance_page = self.client.get(
            "/attendance?month=2026-07"
        ).get_data(as_text=True)
        payroll_page = self.client.get(
            "/attendance-payroll"
            "?year_month=2026-07&payroll_group=site_daily"
        ).get_data(as_text=True)
        self.assertNotIn(employee_no, attendance_page)
        self.assertNotIn(employee_no, payroll_page)

    def test_annual_leave_legacy_bucket_and_special_extension(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "年假桶測試",
            "LEAVE BUCKET TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "LEAVE1001",
            "65550001",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.start_date = date(2020, 1, 1)
            employee.current_period.contract_annual_leave_days = Decimal("10")
            db.session.add(
                EmployeeCompLeaveCredit(
                    employee_id=employee_id,
                    source_date=date(2026, 7, 5),
                    source_kind="rest_day",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.commit()

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2025",
                "entitled_days": "8",
                "legacy_days": "8",
                "extended_until": "2026-12-31",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/annual-leave",
            data={
                "start_date": "2026-08-10",
                "start_session": "am",
                "end_date": "2026-08-14",
                "end_session": "pm",
                "entitlement_year": "2026",
                "days": "5",
                "legacy_days": "3",
                "regular_days": "2",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("請假記錄已新增", response.get_data(as_text=True))
        with self.app.app_context():
            record = EmployeeAnnualLeaveRecord.query.one()
            self.assertEqual(record.days, Decimal("5.0"))
            self.assertEqual(len(record.comp_leave_allocations), 1)
            self.assertEqual(
                record.comp_leave_allocations[0].days, Decimal("1.0")
            )
            self.assertEqual(
                EmployeeAnnualLeaveAllocation.query.filter_by(
                    record_id=record.id
                ).count(),
                1,
            )
            allocations = {
                item.balance.year: item.days for item in record.allocations
            }
            self.assertEqual(allocations[2023], Decimal("4.0"))
            employee = db.session.get(Employee, employee_id)
            buckets = annual_leave_buckets(
                employee,
                as_of=date(2026, 8, 14),
            )
            by_year = {item["year"]: item for item in buckets}
            self.assertEqual(by_year[2023]["remaining"], Decimal("4.0"))
            self.assertEqual(by_year[2025]["remaining"], Decimal("8.0"))
            self.assertEqual(by_year[2025]["expiry_date"], date(2026, 12, 31))

    def test_annual_leave_record_is_not_counted_against_two_buckets(self):
        employee_id, _ = self.create_employee(
            "ASMTP",
            "management",
            "年假跨帳戶測試",
            "LEAVE CROSS BUCKET TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "LEAVE1002",
            "65550002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.start_date = date(2020, 1, 1)
            employee.current_period.contract_annual_leave_days = Decimal("14")
            legacy_balance = EmployeeAnnualLeaveBalance(
                employee_id=employee_id,
                year=2023,
                entitled_days_override=Decimal("50.5"),
            )
            current_balance = EmployeeAnnualLeaveBalance(
                employee_id=employee_id,
                year=2026,
                entitled_days_override=Decimal("14"),
                expiry_date=date(2027, 3, 31),
            )
            db.session.add_all([legacy_balance, current_balance])
            db.session.flush()

            fallback_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 7, 1),
                end_date=date(2026, 7, 7),
                entitlement_year=2026,
                days=Decimal("7"),
                leave_type="annual",
                status="active",
            )
            legacy_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 8, 31),
                end_date=date(2026, 8, 31),
                start_session="am",
                end_session="am",
                entitlement_year=2026,
                days=Decimal("0.5"),
                leave_type="annual",
                status="active",
            )
            comp_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 9, 1),
                end_date=date(2026, 9, 1),
                entitlement_year=2026,
                days=Decimal("1"),
                leave_type="annual",
                status="active",
            )
            sick_record = EmployeeAnnualLeaveRecord(
                employee_id=employee_id,
                leave_date=date(2026, 9, 2),
                end_date=date(2026, 9, 3),
                entitlement_year=2026,
                days=Decimal("2"),
                leave_type="sick",
                status="active",
            )
            credit = EmployeeCompLeaveCredit(
                employee_id=employee_id,
                source_date=date(2026, 6, 1),
                source_kind="rest_day",
                days=Decimal("1"),
                status="active",
            )
            db.session.add_all(
                [
                    fallback_record,
                    legacy_record,
                    comp_record,
                    sick_record,
                    credit,
                ]
            )
            db.session.flush()
            fixed_utc = datetime(2026, 9, 1, 6, 30)
            legacy_record.created_at = fixed_utc
            legacy_record.updated_at = fixed_utc
            db.session.add_all(
                [
                    EmployeeAnnualLeaveAllocation(
                        record_id=legacy_record.id,
                        balance_id=legacy_balance.id,
                        days=Decimal("0.5"),
                    ),
                    EmployeeCompLeaveAllocation(
                        leave_record_id=comp_record.id,
                        credit_id=credit.id,
                        days=Decimal("1"),
                    ),
                ]
            )
            db.session.commit()

            buckets = annual_leave_buckets(
                employee,
                as_of=date(2026, 9, 1),
            )
            by_year = {item["year"]: item for item in buckets}
            self.assertEqual(by_year[2023]["used"], Decimal("0.5"))
            self.assertEqual(by_year[2023]["remaining"], Decimal("50.0"))
            self.assertEqual(by_year[2026]["used"], Decimal("7.0"))
            self.assertEqual(by_year[2026]["remaining"], Decimal("7.0"))

            summary = annual_leave_summary(employee, 2026)
            self.assertEqual(summary["used"], Decimal("8.5"))
            self.assertEqual(summary["bucket_used"], Decimal("7.0"))
            self.assertEqual(summary["remaining"], Decimal("7.0"))

        page = self.client.get(
            f"/annual-leave?year=2026&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertIn("本年實際已放", page)
        self.assertIn("所有帳戶合計", page)
        self.assertIn("本年度帳戶剩餘", page)
        self.assertIn("已確認總額", page)
        self.assertIn("目前剩餘＝已確認總額－已扣除", page)
        self.assertIn("假期變更歷史", page)
        self.assertIn("變更時間（香港）", page)
        self.assertIn("2026-09-01 14:30", page)
        self.assertIn("假期日期：2026-08-31", page)
        self.assertNotIn("2026-08-31 至 2026-08-31", page)
        self.assertIn("假期日期：2026-09-02 上午 – 2026-09-03 下午", page)
        self.assertIn("補休只可由考勤錄入產生", page)
        self.assertIn("扣自：2023及以前 0.5 日", page)
        self.assertIn("扣自：補休 1.0 日", page)

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2026",
                "scope": "current",
                "entitled_days": "15",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2026,
                ).one().entitled_days_override,
                Decimal("15.0"),
            )
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2023,
                ).one().entitled_days_override,
                Decimal("50.5"),
            )

        response = self.client.post(
            f"/annual-leave/{employee_id}/balance",
            data={
                "year": "2026",
                "scope": "legacy",
                "legacy_days": "51",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("年假額度調整", page)
        with self.app.app_context():
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2026,
                ).one().entitled_days_override,
                Decimal("15.0"),
            )
            self.assertEqual(
                EmployeeAnnualLeaveBalance.query.filter_by(
                    employee_id=employee_id,
                    year=2023,
                ).one().entitled_days_override,
                Decimal("51.0"),
            )

    def test_leave_work_injury_allowance_and_special_day_payroll_rules(self):
        sick_employee_id, _ = self.create_employee(
            "ASMTP",
            "site_monthly",
            "病假薪酬測試",
            "SICK PAY TEST",
        )
        project_id = self.complete_employee(
            sick_employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "SP100001",
            "62223100",
        )
        injury_employee_id, _ = self.create_employee(
            "ASMTP",
            "site_monthly",
            "工傷薪酬測試",
            "INJURY PAY TEST",
        )
        self.complete_employee(
            injury_employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "WI100001",
            "62224800",
        )

        with self.app.app_context():
            sick_employee = db.session.get(Employee, sick_employee_id)
            sick_employee.current_period.confirmation_date = date(2026, 6, 30)
            summary = AttendanceMonthlySummary(
                employee_id=sick_employee_id,
                year_month="2026-07",
                status="received",
                special_day_handling="pay",
            )
            db.session.add(summary)
            db.session.flush()
            segment = AttendanceSegment(
                summary=summary,
                period_kind="current_1_20",
                project_id=project_id,
                # Monthly ordinary-day input is intentionally ignored.
                working_days=Decimal("16"),
                other_allowance_amount=Decimal("250"),
            )
            db.session.add(segment)
            db.session.flush()
            special_day = AttendanceSpecialDay(
                summary=summary,
                segment=segment,
                period_kind="current_1_20",
                project_id=project_id,
                work_date=date(2026, 7, 5),
                day_kind="rest_day",
                handling="pay",
                days=Decimal("1"),
                status="active",
            )
            db.session.add_all(
                [
                    special_day,
                    EmployeeAnnualLeaveRecord(
                        employee_id=sick_employee_id,
                        leave_date=date(2026, 7, 10),
                        end_date=date(2026, 7, 12),
                        start_session="am",
                        end_session="pm",
                        entitlement_year=2026,
                        days=Decimal("3"),
                        leave_type="sick",
                        status="active",
                    ),
                    EmployeeAllowance(
                        employee_id=sick_employee_id,
                        label="餐補",
                        allowance_type="meal",
                        currency="HKD",
                        amount=Decimal("310"),
                        effective_from=date(2026, 7, 1),
                        status="active",
                    ),
                    EmployeeAllowance(
                        employee_id=sick_employee_id,
                        label="特殊津貼",
                        allowance_type="special",
                        currency="HKD",
                        amount=Decimal("620"),
                        effective_from=date(2026, 7, 1),
                        status="active",
                    ),
                    EmployeeWorkInjuryPeriod(
                        employee_id=injury_employee_id,
                        accident_date=date(2026, 7, 1),
                        payroll_start_date=date(2026, 7, 1),
                        payroll_end_date=date(2026, 7, 31),
                        confirmed_monthly_earnings=Decimal("31000"),
                        incapacity_monthly_earnings=Decimal("0"),
                        currency="HKD",
                        status="active",
                    ),
                ]
            )
            db.session.commit()

            rows = calculate_payroll("2026-07", "site_monthly")
            sick_row = next(
                row for row in rows if row["employee"].id == sick_employee_id
            )
            self.assertEqual(sick_row["sick_leave_days"], Decimal("3.0"))
            self.assertEqual(sick_row["sick_leave_amount"], Decimal("2600.00"))
            self.assertEqual(
                sick_row["traffic_meal_allowance_amount"], Decimal("8680.00")
            )
            self.assertEqual(
                sick_row["special_allowance_amount"], Decimal("620.00")
            )
            self.assertEqual(sick_row["gross_amount"], Decimal("41150.00"))
            self.assertEqual(
                sick_row["attendance_other_allowance_amount"], Decimal("250.00")
            )
            line = sick_row["lines"][0]
            self.assertEqual(line["working_days"], Decimal("28.00"))
            self.assertEqual(line["holiday_days"], Decimal("1.00"))
            self.assertIn("病假憑證待補", sick_row["warnings"])

            special_day.handling = "comp_leave"
            summary.special_day_handling = "comp_leave"
            db.session.commit()
            sick_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == sick_employee_id
            )
            self.assertEqual(sick_row["gross_amount"], Decimal("40150.00"))
            self.assertEqual(sick_row["lines"][0]["holiday_days"], Decimal("0.00"))

            db.session.add(
                AttendanceSegment(
                    summary=summary,
                    period_kind="current_21_end_forecast",
                    project_id=project_id,
                    working_days=Decimal("0"),
                    sunday_holiday_days=Decimal("1"),
                )
            )
            db.session.commit()
            sick_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == sick_employee_id
            )
            self.assertEqual(sick_row["gross_amount"], Decimal("41150.00"))
            self.assertEqual(
                sick_row["lines"][0]["forecast_holiday_days"],
                Decimal("1.00"),
            )

            injury_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == injury_employee_id
            )
            self.assertFalse(injury_row["blockers"])
            self.assertEqual(injury_row["work_injury_days"], Decimal("31.0"))
            self.assertEqual(
                injury_row["work_injury_amount"], Decimal("24800.00")
            )
            self.assertEqual(injury_row["gross_amount"], Decimal("24800.00"))

            injury_period = EmployeeWorkInjuryPeriod.query.filter_by(
                employee_id=injury_employee_id
            ).one()
            injury_period.pay_mode = "full_pay"
            db.session.add(
                EmployeeWorkInjuryMonthlyExpense(
                    employee_id=injury_employee_id,
                    work_injury_period_id=injury_period.id,
                    year_month="2026-07",
                    amount=Decimal("800"),
                    currency="HKD",
                    status="active",
                )
            )
            db.session.commit()
            injury_row = next(
                row
                for row in calculate_payroll("2026-07", "site_monthly")
                if row["employee"].id == injury_employee_id
            )
            self.assertEqual(injury_row["work_injury_amount"], Decimal("31000.00"))
            self.assertEqual(injury_row["gross_amount"], Decimal("31000.00"))
            self.assertEqual(
                injury_row["work_injury_medical_reimbursement_amount"],
                Decimal("800.00"),
            )
            self.assertEqual(injury_row["net_amount"], Decimal("30300.00"))

        employment_page = self.client.get(
            f"/employees/{sick_employee_id}?tab=employment"
        ).get_data(as_text=True)
        self.assertIn("變更歷史", employment_page)
        self.assertIn("補貼", employment_page)
        self.assertIn('id="allowance-editor-', employment_page)
        self.assertIn("可不填；留空表示持續生效", employment_page)
        self.assertNotIn("補貼時間線", employment_page)

        injury_search_page = self.client.get(
            "/annual-leave",
            query_string={"view": "injury", "q": "工伤薪酬测试"},
        ).get_data(as_text=True)
        self.assertIn("假期與工傷", injury_search_page)
        self.assertIn("工傷管理", injury_search_page)
        self.assertIn("工傷薪酬測試", injury_search_page)
        injury_detail_page = self.client.get(
            "/annual-leave",
            query_string={
                "view": "injury",
                "employee_id": injury_employee_id,
            },
        ).get_data(as_text=True)
        self.assertIn("按〔核實每月收入－期間每月收入〕× 4/5", injury_detail_page)
        self.assertIn("日工 AM；月工／OFFICE AN", injury_detail_page)

        payroll_page = self.client.get(
            "/attendance-payroll",
            query_string={
                "year_month": "2026-07",
                "status": "all",
                "employee_id": sick_employee_id,
            },
        ).get_data(as_text=True)
        self.assertNotIn("工資更正與一次性調整", payroll_page)
        self.assertNotIn('action="/payroll/adjustments"', payroll_page)
        self.assertIn("離職當月的工資只由離職 Payroll", payroll_page)

    def test_attendance_special_dates_generate_and_void_comp_leave(self):
        employee_id, _ = self.create_employee(
            "HKRD", "site_daily", "補休聯動測試", "COMP LEAVE TEST"
        )
        project_id = self.complete_employee(
            employee_id,
            "site_daily",
            "TMC046",
            "daily",
            "500",
            "CL100001",
            "62225000",
            mpf_mode="casual",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            db.session.add_all(
                [
                    WorkCalendarHoliday(
                        region_id=employee.current_assignment.region_id,
                        holiday_date=holiday_date,
                        name=f"補休測試法定假日 {holiday_date:%m-%d}",
                        active=True,
                    )
                    for holiday_date in (date(2026, 7, 5), date(2026, 7, 12))
                ]
            )
            db.session.commit()
        response = self.client.post(
            "/attendance/batches",
            data={
                "year_month": "2026-07",
                "files": [
                    (
                        io.BytesIO(pdf_bytes("comp-leave-attendance")),
                        "comp-leave-attendance.pdf",
                    )
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            item_id = AttendanceBatchItem.query.one().id

        entry_page = self.client.get(
            f"/attendance?month=2026-07&view=collection&item_id={item_id}&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertIn("Payroll 類別", entry_page)
        self.assertIn("填寫方式：非法定假日按真正實際出勤日數填寫", entry_page)
        self.assertIn("請選擇員工", entry_page)
        self.assertNotIn("文件名不作身份依據", entry_page)
        context_start = entry_page.index(
            '<section class="period-context-bar attendance-period-context'
        )
        context_end = entry_page.index("</section>", context_start)
        self.assertIn(
            'class="attendance-calendar-check"',
            entry_page[context_start:context_end],
        )
        self.assertNotIn(
            '<section class="attendance-calendar-check"',
            entry_page,
        )
        self.assertIn("非法定假日實際出勤日數（含星期日）", entry_page)
        self.assertIn("法定假日實際工作日數", entry_page)
        self.assertIn("法定假日預估工作日數", entry_page)
        self.assertIn('data-special-work-picker', entry_page)
        self.assertNotIn('data-special-work-session', entry_page)
        self.assertNotIn('class="icon-btn remove-segment"', entry_page)
        self.assertNotIn("休息日實際工作日期", entry_page)
        self.assertIn("指定法定假日實際工作日期", entry_page)
        self.assertNotIn("特殊日統一處理方式", entry_page)
        self.assertIn('class="attendance-period-table-head"', entry_page)
        self.assertIn('class="review-section attendance-period-row actual-period-row"', entry_page)
        self.assertIn("待按 PDF 核對的系統基準", entry_page)
        self.assertIn("目前未錄入額外考勤項目", entry_page)
        self.assertIn("ⓘ 計算規則", entry_page)
        self.assertNotIn("本次 Payroll 核對", entry_page)
        self.assertRegex(
            entry_page,
            r'name="previous_21_end_forecast_working_days" value="8(?:\.0+)?"',
        )
        self.assertRegex(
            entry_page,
            r'name="previous_21_end_forecast_holiday_days" value="0"',
        )
        self.assertIn('disabled aria-disabled="true"', entry_page)
        self.assertIn("未找到 2026年6月考勤", entry_page)

        form = {
            "employee_id": str(employee_id),
            "special_day_handling": "comp_leave",
            "current_1_20_project_id": [str(project_id)],
            "current_1_20_working_days": ["16"],
            "current_1_20_ot_hours": ["0"],
            "current_1_20_holiday_days": ["2"],
            "current_1_20_special_work_entries": [json.dumps([
                {"date": "2026-07-05", "session": "full_day"},
                {"date": "2026-07-12", "session": "pm"},
            ])],
            "current_1_20_large_ecall_count": ["0"],
            "current_1_20_ecall_count": ["0"],
            "current_21_end_forecast_project_id": [str(project_id)],
            "current_21_end_forecast_working_days": ["6"],
            "current_21_end_forecast_holiday_days": ["1"],
            "current_21_end_forecast_special_work_entries": ["[]"],
        }
        invalid_form = dict(form)
        invalid_form["current_1_20_special_work_entries"] = [json.dumps([
            {"date": "2026-07-05", "session": "full_day"},
        ])]
        invalid_response = self.client.post(
            f"/attendance/items/{item_id}/save",
            data=invalid_form,
            follow_redirects=True,
        )
        self.assertIn(
            "日期數必須與出勤日數一致",
            invalid_response.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertEqual(AttendanceMonthlySummary.query.count(), 0)

        response = self.client.post(
            f"/attendance/items/{item_id}/save", data=form
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            credits = EmployeeCompLeaveCredit.query.order_by(
                EmployeeCompLeaveCredit.source_date
            ).all()
            self.assertEqual(len(credits), 2)
            self.assertTrue(all(item.status == "active" for item in credits))
            self.assertEqual(
                [item.source_date for item in credits],
                [date(2026, 7, 5), date(2026, 7, 12)],
            )
            self.assertEqual(
                [item.days for item in credits],
                [Decimal("1.0"), Decimal("1.0")],
            )
            special_days = AttendanceSpecialDay.query.order_by(
                AttendanceSpecialDay.work_date
            ).all()
            self.assertEqual(
                [item.session for item in special_days],
                ["full_day", "full_day"],
            )

        response = self.client.post(
            "/attendance/batches",
            data={
                "year_month": "2026-08",
                "files": [
                    (
                        io.BytesIO(pdf_bytes("august-attendance")),
                        "august-attendance.pdf",
                    )
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            august_item_id = AttendanceBatchItem.query.filter_by(
                original_filename="august-attendance.pdf"
            ).one().id
        august_page = self.client.get(
            f"/attendance?month=2026-08&view=collection&item_id={august_item_id}&employee_id={employee_id}"
        ).get_data(as_text=True)
        self.assertRegex(
            august_page,
            r'name="previous_21_end_forecast_working_days" value="6(?:\.00)?"',
        )
        self.assertRegex(
            august_page,
            r'name="previous_21_end_forecast_holiday_days" value="1(?:\.00)?"',
        )
        self.assertIn('target="_blank" rel="noopener"', august_page)
        self.assertIn("打開 2026年7月考勤表", august_page)
        self.assertNotIn("未找到 2026年7月考勤", august_page)

        form["special_day_handling"] = "pay"
        form["confirm_duplicate"] = "1"
        response = self.client.post(
            f"/attendance/items/{item_id}/save", data=form
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            credits = EmployeeCompLeaveCredit.query.all()
            self.assertEqual(len(credits), 2)
            self.assertTrue(all(item.status == "voided" for item in credits))
            special_days = AttendanceSpecialDay.query.all()
            self.assertEqual(len(special_days), 2)
            self.assertTrue(all(item.handling == "pay" for item in special_days))

    def test_final_payment_review_calculation_and_formula_export(self):
        employee_id, employee_no = self.create_employee(
            "ASMTP",
            "management",
            "離職結算測試",
            "FINAL PAYMENT TEST",
        )
        self.complete_employee(
            employee_id,
            "management",
            "TMC046",
            "monthly",
            "30000",
            "FINAL1001",
            "65550002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_period.start_date = date(2020, 1, 1)
            employee.current_period.contract_annual_leave_days = Decimal("10")
            assignment = employee.current_assignment
            payroll_entity_id = assignment.payroll_entity_id
            payroll_entity_code = assignment.payroll_entity.code
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-08",
                status="received",
                special_day_handling="pay",
            )
            db.session.add(summary)
            db.session.flush()
            db.session.add(
                AttendanceSegment(
                    summary=summary,
                    period_kind="current_1_20",
                    working_days=Decimal("14"),
                    ot_hours=Decimal("2"),
                    other_allowance_amount=Decimal("250"),
                )
            )
            injury = EmployeeWorkInjuryPeriod(
                employee_id=employee_id,
                accident_date=date(2026, 7, 1),
                payroll_start_date=date(2026, 7, 1),
                payroll_end_date=date(2026, 7, 31),
                confirmed_monthly_earnings=Decimal("30000"),
                incapacity_monthly_earnings=Decimal("0"),
                currency="HKD",
                status="active",
            )
            db.session.add(injury)
            db.session.flush()
            db.session.add_all(
                [
                    EmployeeAllowance(
                        employee_id=employee_id,
                        label="交通補貼",
                        allowance_type="transport",
                        currency="HKD",
                        amount=Decimal("60"),
                        effective_from=date(2026, 8, 1),
                        status="active",
                    ),
                    EmployeeAllowance(
                        employee_id=employee_id,
                        label="特殊津貼",
                        allowance_type="special",
                        currency="HKD",
                        amount=Decimal("310"),
                        effective_from=date(2026, 8, 1),
                        status="active",
                    ),
                    PayrollAdjustment(
                        employee_id=employee_id,
                        year_month="2026-08",
                        label="離職月補發",
                        amount=Decimal("300"),
                        status="active",
                    ),
                    EmployeeWorkInjuryMonthlyExpense(
                        employee_id=employee_id,
                        work_injury_period_id=injury.id,
                        year_month="2026-08",
                        amount=Decimal("400"),
                        currency="HKD",
                        status="active",
                    ),
                ]
            )
            db.session.commit()
        response = self.client.post(
            f"/employees/{employee_id}/terminate",
            data={
                "end_date": "2026-08-20",
                "reason": "company_termination",
                "average_wage": "30000",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            period = EmployeeEmploymentPeriod.query.filter_by(
                employee_id=employee_id
            ).one()
            period_id = period.id

        response = self.client.post(
            f"/final-payment/{period_id}/save",
            data={
                "year_month": "2026-08",
                "payroll_group": "management",
                "payroll_entity_id": str(payroll_entity_id),
                "actual_working_days": "14",
                "actual_ot_hours": "2",
                "actual_holiday_days": "0",
                "large_ecall_count": "0",
                "ecall_count": "0",
                "allowance_amount": "1000",
                "other_payment": "500",
                "overpay_amount": "0",
                "underpay_amount": "0",
                "legacy_leave_days": "3",
                "post_2024_leave_days": "2",
                "statutory_holiday_days": "1",
                "leave_average_wage": "30000",
                "leave_wage_total": "360000",
                "benefit_type": "long_service",
                "pre_basis_last": "18000",
                "pre_basis_average": "20000",
                "pre_basis_choice": "average",
                "post_basis_last": "30000",
                "post_basis_average": "28000",
                "post_basis_choice": "last",
                "mpf_offset_amount": "500",
                "special_compensation": "1000",
                "payment_in_lieu": "30000",
                "remarks": "HR 已核對測試資料",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("離職 Payroll 資料已保存", page)
        self.assertIn("當前離職 Payroll 月份", page)
        self.assertIn("交通／餐補（自動）", page)
        self.assertIn("工傷醫療實銷（不計 MPF）", page)
        self.assertIn(employee_no, page)
        self.assertIn("2025-05-01", page)
        self.assertIn("勞工處規則摘要", page)
        self.assertIn("最後 30 個正常工作日", page)
        self.assertIn("不少於 24 個月", page)
        self.assertIn("前 12 個月工資合計 ÷ 365", page)
        self.assertIn("離職當月以 Final Payment 作唯一工資來源", page)
        with self.app.app_context():
            db.session.expire_all()
            period = db.session.get(EmployeeEmploymentPeriod, period_id)
            result = calculate_final_payment(period)
            expected_base_amount = result["base_amount"]
            expected_ot_amount = result["ot_amount"]
            expected_holiday_amount = result["holiday_amount"]
            expected_net_amount = result["net_amount"]
            self.assertFalse(result["blockers"])
            self.assertEqual(
                result["traffic_meal_allowance_amount"], Decimal("1200.00")
            )
            self.assertEqual(
                result["special_allowance_amount"], Decimal("200.00")
            )
            self.assertEqual(
                result["manual_allowance_amount"], Decimal("1000.00")
            )
            self.assertEqual(
                result["attendance_other_allowance_amount"], Decimal("250.00")
            )
            self.assertEqual(
                result["month_adjustment_amount"], Decimal("300.00")
            )
            self.assertEqual(
                result["manual_other_payment"], Decimal("500.00")
            )
            self.assertEqual(
                result["work_injury_medical_reimbursement_amount"],
                Decimal("400.00"),
            )
            self.assertEqual(result["leave_wage_total"], Decimal("360000.00"))
            self.assertEqual(result["leave_rate"], Decimal("986.3014"))
            leave_summary = annual_leave_summary(result["employee"], 2026)
            expected_prorated = (
                leave_summary["calculated_entitled"]
                * Decimal("232")
                / Decimal("365")
            )
            self.assertTrue(leave_summary["termination_prorated"])
            self.assertEqual(leave_summary["termination_date"], date(2026, 8, 20))
            self.assertEqual(leave_summary["entitled"], expected_prorated)
            self.assertEqual(result["benefit"]["type"], "long_service")
            self.assertEqual(result["benefit"]["mpf_offset"], Decimal("500.00"))
            self.assertGreater(result["benefit"]["pre_amount"], Decimal("0"))
            self.assertGreater(result["benefit"]["post_amount"], Decimal("0"))
            daily_benefit = calculate_benefit(
                period,
                result["case"],
                {},
                "site_daily",
            )
            pre_days, post_days = service_portion_days(period)
            self.assertEqual(
                daily_benefit["pre_amount"],
                (Decimal("15000") * Decimal(pre_days) / Decimal("365")).quantize(
                    Decimal("0.01")
                ),
            )
            self.assertEqual(
                daily_benefit["post_amount"],
                (Decimal("15000") * Decimal(post_days) / Decimal("365")).quantize(
                    Decimal("0.01")
                ),
            )
            self.assertEqual(
                EmployeeFinalPaymentCase.query.filter_by(
                    employment_period_id=period_id
                ).count(),
                1,
            )
            ordinary_rows = [
                row
                for row in calculate_payroll("2026-08", "all")
                if row["employee"].id == employee_id
            ]
            self.assertEqual(ordinary_rows, [])
            final_mpf_rows = [
                row
                for row in mpf_preview_rows("2026-08")
                if row["employee"].id == employee_id
            ]
            self.assertEqual(len(final_mpf_rows), 1)
            self.assertTrue(final_mpf_rows[0]["is_final_payment"])

        mpf_page = self.client.get(
            "/mpf-contributions",
            query_string={"year_month": "2026-08"},
        ).get_data(as_text=True)
        self.assertIn("離職員工 MPF 規則", mpf_page)
        self.assertIn("只採用已確認的 Final Payment 結果", mpf_page)

        response = self.client.post(
            "/final-payment/export",
            data={
                "year_month": "2026-08",
                "payroll_group": "management",
                "payroll_entity_id": str(payroll_entity_id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument",
            response.content_type,
        )
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        self.assertEqual(workbook.sheetnames, ["OFFICE", "計算說明"])
        sheet = workbook["OFFICE"]
        self.assertEqual(sheet["A1"].value, "Hong Kong River Engineering Co. Ltd.")
        self.assertEqual(sheet["A2"].value, "Final Payment")
        self.assertEqual(sheet["A3"].value, "Payroll of Local Staff")
        merged_ranges = {str(item) for item in sheet.merged_cells.ranges}
        self.assertTrue({"A1:Z1", "A2:Z2", "A3:Z3"}.issubset(merged_ranges))
        self.assertEqual(sheet["D8"].value, employee_no)
        self.assertIsNone(sheet["D9"].value)
        self.assertLess(Decimal(str(sheet["W8"].value)), Decimal("0"))
        self.assertEqual(sheet["J8"].value, "=ROUND(H8*I8,2)")
        self.assertEqual(sheet["M8"].value, "=ROUND(K8*L8,2)")
        self.assertTrue(str(sheet["V8"].value).startswith("=ROUND("))
        self.assertEqual(sheet["X8"].value, "=ROUND(V8+W8,2)")
        self.assertEqual(sheet["Y8"].value, "=X8")
        exported_base = (
            Decimal(str(sheet["H8"].value))
            * Decimal(str(sheet["I8"].value))
        ).quantize(Decimal("0.01"))
        exported_ot = (
            Decimal(str(sheet["K8"].value))
            * Decimal(str(sheet["L8"].value))
        ).quantize(Decimal("0.01"))
        exported_holiday = (
            Decimal(str(sheet["N8"].value))
            * Decimal(str(sheet["O8"].value))
        ).quantize(Decimal("0.01"))
        exported_gross = sum(
            (
                exported_base,
                exported_ot,
                exported_holiday,
                *(Decimal(str(sheet.cell(8, column).value or 0)) for column in range(17, 22)),
            ),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        exported_net = (
            exported_gross + Decimal(str(sheet["W8"].value))
        ).quantize(Decimal("0.01"))
        self.assertEqual(exported_base, expected_base_amount)
        self.assertEqual(exported_ot, expected_ot_amount)
        self.assertEqual(exported_holiday, expected_holiday_amount)
        self.assertEqual(exported_net, expected_net_amount)
        notes = workbook["計算說明"]
        self.assertIn("勞工處規則摘要", notes["A1"].value)
        self.assertTrue(
            any(
                "最後 30 個正常工作日" in str(cell.value or "")
                for cell in notes["B"]
            )
        )
        self.assertEqual(
            notes["C5"].hyperlink.target,
            "https://www.labour.gov.hk/tc/faq/cap57l_whole.htm",
        )

        response = self.client.post(
            "/final-payment/export",
            data={
                "year_month": "2026-08",
                "payroll_group": "all",
                "payroll_entity_id": str(payroll_entity_id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    f"HKR_Final_Payment_2026-08_{payroll_entity_code}_site_daily.xlsx",
                    f"HKR_Final_Payment_2026-08_{payroll_entity_code}_site_monthly.xlsx",
                    f"HKR_Final_Payment_2026-08_{payroll_entity_code}_management.xlsx",
                },
            )
            daily_workbook = load_workbook(
                io.BytesIO(
                    archive.read(
                        f"HKR_Final_Payment_2026-08_{payroll_entity_code}_site_daily.xlsx"
                    )
                ),
                data_only=False,
            )
        self.assertIn("計算說明", daily_workbook.sheetnames)

    def test_work_injury_allowance_and_effective_bank_routes(self):
        employee_id, _ = self.create_employee(
            "ASMTP", "site_monthly", "記錄路由測試", "RECORD ROUTES"
        )
        self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "ROUTES-01",
            "61119991",
        )
        general_upload = self.client.get(
            f"/employees/{employee_id}/documents/new"
        ).get_data(as_text=True)
        self.assertIn('value="staff_record"', general_upload)
        self.assertIn('value="three_treasures"', general_upload)
        self.assertIn('value="cv"', general_upload)
        self.assertIn('value="other"', general_upload)
        self.assertIn('value="signed_contract"', general_upload)
        self.assertIn('value="bank_record"', general_upload)
        specialist = self.client.get(
            f"/employees/{employee_id}/documents/new?upload_type=bank_record",
            follow_redirects=False,
        )
        self.assertEqual(specialist.status_code, 302)
        self.assertIn("tab=personal", specialist.headers["Location"])
        other_upload = self.client.get(
            f"/employees/{employee_id}/documents/new?upload_type=other"
        ).get_data(as_text=True)
        self.assertIn('name="general_document_type_id"', other_upload)
        with self.app.app_context():
            general_type = ReferenceValue.query.join(ReferenceList).filter(
                ReferenceList.code == "general_document_type",
                ReferenceValue.code == "GENERAL_OTHER",
            ).one()
            general_type_id = general_type.id
        response = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": "other",
                "general_document_type_id": str(general_type_id),
                "title": "一般測試附件",
                "file": (
                    io.BytesIO(pdf_bytes("general attachment")),
                    "general-attachment.pdf",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            general_document = EmployeeDocument.query.filter_by(
                employee_id=employee_id,
                category="other",
            ).one()
            self.assertEqual(
                general_document.general_document_type_id,
                general_type_id,
            )
        response = self.client.post(
            f"/employees/{employee_id}/documents/new",
            data={
                "category": "change_evidence",
                "file": (
                    io.BytesIO(pdf_bytes("orphan evidence")),
                    "orphan-evidence.pdf",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            f"/employees/{employee_id}/work-injuries",
            data={
                "accident_date": "2026-07-01",
                "payroll_start_date": "2026-07-01",
                "payroll_end_date": "2026-07-31",
                "confirmed_monthly_earnings": "31000",
                "incapacity_monthly_earnings": "0",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/allowances",
            data={
                "allowance_type": "meal",
                "effective_from": "2026-07-01",
                "amount": "500",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/bank-accounts",
            data={
                "effective_from": "2026-08-01",
                "bank_name": "NEW BANK",
                "account_no": "99887766",
                "currency": "HKD",
                "evidence": (
                    io.BytesIO(pdf_bytes("bank evidence")),
                    "bank-evidence.pdf",
                ),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("NEW BANK", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(
                EmployeeWorkInjuryPeriod.query.filter_by(employee_id=employee_id).count(),
                1,
            )
            self.assertEqual(
                EmployeeAllowance.query.filter_by(employee_id=employee_id).count(),
                1,
            )
            bank = EmployeeBankAccount.query.filter_by(
                employee_id=employee_id,
                bank_name="NEW BANK",
            ).one()
            bank_id = bank.id
            bank_document_id = bank.evidence_document_id
        profile = self.client.get(
            f"/employees/{employee_id}?tab=documents&lang=en"
        ).get_data(as_text=True)
        self.assertIn("bank-evidence.pdf", profile)
        self.assertIn("Manage in module", profile)
        self.assertIn(
            f'/employees/{employee_id}?tab=personal',
            profile,
        )
        self.assertNotIn(
            f'data-dialog-open="document-replace-{bank_document_id}"',
            profile,
        )
        response = self.client.post(
            f"/bank-accounts/{bank_id}/correct",
            data={
                "effective_from": "2026-08-01",
                "bank_name": "CORRECT BANK",
                "account_no": "88776655",
                "currency": "HKD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("CORRECT BANK", response.get_data(as_text=True))
        response = self.client.post(
            f"/bank-accounts/{bank_id}/withdraw",
            data={"reason": "wrong account"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            bank = db.session.get(EmployeeBankAccount, bank_id)
            employee = db.session.get(Employee, employee_id)
            self.assertEqual(bank.status, "voided")
            self.assertEqual(
                employee.bank_name,
                "BANK OF CHINA (HONG KONG) LIMITED",
            )
            self.assertTrue(
                AuditLog.query.filter_by(
                    entity_type="EmployeeBankAccount",
                    entity_id=bank_id,
                ).count() >= 3
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

    def test_payroll_regression_matrix_for_leave_ot_ecall_and_export(self):
        post_id, _ = self.create_employee(
            "ASMTP", "site_monthly", "綜合薪酬測試", "PAYROLL MATRIX"
        )
        project_id = self.complete_employee(
            post_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "MATRIX-01",
            "61118881",
        )
        pre_id, _ = self.create_employee(
            "ASMTP", "site_monthly", "試用期病假測試", "PROBATION SICK"
        )
        self.complete_employee(
            pre_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "MATRIX-02",
            "61118882",
        )
        with self.app.app_context():
            post = db.session.get(Employee, post_id)
            post.current_period.confirmation_date = date(2026, 6, 30)
            summary = AttendanceMonthlySummary(
                employee_id=post_id,
                year_month="2026-07",
                status="received",
                special_day_handling="pay",
            )
            pre_summary = AttendanceMonthlySummary(
                employee_id=pre_id,
                year_month="2026-07",
                status="received",
            )
            db.session.add_all([summary, pre_summary])
            db.session.flush()
            current = AttendanceSegment(
                summary=summary,
                period_kind="current_1_20",
                project_id=project_id,
                working_days=Decimal("16"),
                ot_hours=Decimal("9"),
                large_ecall_count=1,
                ecall_count=1,
            )
            previous = AttendanceSegment(
                summary=summary,
                period_kind="previous_21_end",
                project_id=project_id,
                ot_hours=Decimal("9"),
                ecall_count=1,
            )
            previous_forecast = AttendanceSegment(
                summary=summary,
                period_kind="previous_21_end_forecast",
                project_id=project_id,
            )
            db.session.add_all([current, previous, previous_forecast])
            db.session.flush()
            db.session.add_all(
                [
                    AttendanceSpecialDay(
                        summary=summary,
                        segment=current,
                        period_kind="current_1_20",
                        project_id=project_id,
                        work_date=date(2026, 7, 5),
                        day_kind="rest_day",
                        handling="pay",
                        days=Decimal("1"),
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=post_id,
                        leave_date=date(2026, 7, 6),
                        end_date=date(2026, 7, 7),
                        entitlement_year=2026,
                        days=Decimal("2"),
                        leave_type="annual",
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=post_id,
                        leave_date=date(2026, 7, 8),
                        end_date=date(2026, 7, 10),
                        entitlement_year=2026,
                        days=Decimal("3"),
                        leave_type="sick",
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=post_id,
                        leave_date=date(2026, 7, 11),
                        end_date=date(2026, 7, 12),
                        entitlement_year=2026,
                        days=Decimal("2"),
                        leave_type="unpaid",
                        status="active",
                    ),
                    EmployeeAnnualLeaveRecord(
                        employee_id=pre_id,
                        leave_date=date(2026, 7, 8),
                        end_date=date(2026, 7, 8),
                        entitlement_year=2026,
                        days=Decimal("1"),
                        leave_type="sick",
                        status="active",
                    ),
                ]
            )
            db.session.commit()
            rows = calculate_payroll("2026-07", "site_monthly")
            matrix = next(row for row in rows if row["employee"].id == post_id)
            probation = next(row for row in rows if row["employee"].id == pre_id)
            self.assertEqual(matrix["annual_leave_days"], Decimal("2.00"))
            self.assertEqual(matrix["sick_leave_days"], Decimal("3.00"))
            self.assertEqual(matrix["sick_leave_amount"], Decimal("2600.00"))
            self.assertEqual(matrix["unpaid_leave_days"], Decimal("2.00"))
            self.assertEqual(matrix["unpaid_leave_deduction"], Decimal("2000.00"))
            self.assertEqual(matrix["ot_amount"], Decimal("1500.00"))
            self.assertEqual(matrix["large_ecall_amount"], Decimal("1000.00"))
            self.assertEqual(matrix["ecall_amount"], Decimal("400.00"))
            self.assertEqual(matrix["underpay_amount"], Decimal("0.00"))
            self.assertEqual(matrix["overpay_amount"], Decimal("0.00"))
            self.assertEqual(probation["sick_leave_amount"], Decimal("800.00"))
            payroll_entity_id = post.current_assignment.payroll_entity_id

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_monthly",
                "payroll_entity_id": payroll_entity_id,
                "scope": "selected",
                "employee_ids": [post_id],
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        sheet = workbook["月工"]
        self.assertEqual(sheet["K7"].value, "=J7/$G$5")
        self.assertEqual(Decimal(str(sheet["L7"].value)), Decimal("26"))
        self.assertEqual(Decimal(str(sheet["AF7"].value)), Decimal("0"))
        self.assertEqual(Decimal(str(sheet["AG7"].value)), Decimal("0"))
        self.assertTrue(str(sheet["M7"].value).startswith("=ROUND"))

    def test_attendance_prorated_monthly_salary_and_work_calendar_forecast(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "例外月薪測試",
            "ATTENDANCE PRORATED",
        )
        project_id = self.complete_employee(
            employee_id,
            "site_monthly",
            "TMC046",
            "monthly",
            "31000",
            "QA-PRORATED-001",
            "62220001",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            employee.current_salary.monthly_pay_method = "attendance_days"
            employee.allowances.append(
                EmployeeAllowance(
                    label="Daily meal",
                    allowance_type="meal",
                    currency="HKD",
                    amount=Decimal("50"),
                    effective_from=date(2026, 1, 1),
                    status="active",
                )
            )
            summary = AttendanceMonthlySummary(
                employee_id=employee_id,
                year_month="2026-07",
                status="received",
            )
            for kind, days in (
                ("current_1_20", Decimal("10")),
                ("current_21_end_forecast", Decimal("0")),
                ("previous_21_end", Decimal("0")),
                ("previous_21_end_forecast", Decimal("0")),
            ):
                summary.segments.append(
                    AttendanceSegment(
                        period_kind=kind,
                        project_id=project_id,
                        working_days=days,
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    )
                )
            db.session.add(summary)
            db.session.commit()

            row = calculate_payroll("2026-07", "site_monthly")[0]
            self.assertEqual(row["base_amount"], Decimal("10000.00"))
            self.assertEqual(
                row["traffic_meal_allowance_amount"],
                Decimal("500.00"),
            )
            self.assertEqual(row["holiday_amount"], Decimal("0.00"))

            region_id = employee.current_assignment.region_id
            db.session.add(
                WorkCalendarHoliday(
                    region_id=region_id,
                    holiday_date=date(2026, 7, 24),
                    name="Test statutory holiday",
                    applies_to_statutory=True,
                    applies_to_public=True,
                    active=True,
                )
            )
            employee.current_salary.monthly_pay_method = "full_month"
            db.session.commit()
            monthly_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in monthly_rows),
                Decimal("9"),
            )
            employee.current_assignment.payroll_group = "management"
            employee.current_assignment.workweek_days = Decimal("5")
            employee.payroll_group = "management"
            db.session.commit()
            management_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in management_rows),
                Decimal("8"),
            )
            holiday = WorkCalendarHoliday.query.filter_by(
                region_id=region_id,
                holiday_date=date(2026, 7, 24),
            ).one()
            holiday.applies_to_public = False
            db.session.commit()
            statutory_only_management_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(
                    Decimal(str(item["working_days"]))
                    for item in statutory_only_management_rows
                ),
                Decimal("9"),
            )
            holiday.applies_to_public = True
            employee.current_salary.monthly_pay_method = "attendance_days"
            db.session.commit()
            self.assertEqual(
                automatic_attendance_rows(
                    employee,
                    date(2026, 7, 21),
                    date(2026, 7, 31),
                ),
                [],
            )

    def test_daily_statutory_holiday_pay_and_workweek_units(self):
        daily_id, _ = self.create_employee(
            "HKR",
            "site_daily",
            "日工法定假日測試",
            "DAILY STATUTORY HOLIDAY",
        )
        project_id = self.complete_employee(
            daily_id,
            "site_daily",
            "TMC046",
            "daily",
            "1000",
            "Y1234567",
            "61110001",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, daily_id)
            region_id = employee.current_assignment.region_id
            sunday_rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 5),
                date(2026, 7, 5),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in sunday_rows),
                Decimal("0"),
            )
            self.assertIsNone(
                special_work_day_units(employee, date(2026, 7, 5))
            )
            self.assertEqual(
                special_work_day_units(employee, date(2026, 7, 1)),
                Decimal("1"),
            )
            employee.annual_leave_records.append(
                EmployeeAnnualLeaveRecord(
                    leave_date=date(2026, 8, 15),
                    end_date=date(2026, 8, 15),
                    entitlement_year=2026,
                    days=Decimal("1"),
                    leave_type="annual",
                    status="active",
                )
            )
            august_summary = AttendanceMonthlySummary(
                employee_id=daily_id,
                year_month="2026-08",
                status="received",
            )
            for kind in (
                "current_1_20",
                "current_21_end_forecast",
                "previous_21_end",
                "previous_21_end_forecast",
            ):
                august_summary.segments.append(
                    AttendanceSegment(
                        period_kind=kind,
                        project_id=project_id,
                        working_days=Decimal("0"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    )
                )
            db.session.add(august_summary)
            db.session.commit()
            august_prefill = automatic_attendance_rows(
                employee,
                date(2026, 8, 15),
                date(2026, 8, 15),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in august_prefill),
                Decimal("0"),
            )
            august_payroll = calculate_payroll("2026-08", "site_daily")[0]
            self.assertEqual(august_payroll["annual_leave_days"], Decimal("1.00"))
            self.assertEqual(august_payroll["base_amount"], Decimal("1000.00"))
            with self.app.test_request_context(
                method="POST",
                data={
                    "employee_id": str(daily_id),
                    "current_1_20_project_id": [str(project_id)],
                    "current_1_20_working_days": ["1"],
                    "current_1_20_holiday_days": ["1"],
                    "current_1_20_special_work_entries": [json.dumps([
                        {"date": "2026-07-05"},
                    ])],
                },
            ):
                self.assertIn(
                    "日工的星期日工作應計入一般實際出勤日數",
                    validate_sunday_holiday_entries("2026-07"),
                )
            summary = AttendanceMonthlySummary(
                employee_id=daily_id,
                year_month="2026-07",
                status="received",
                special_day_handling="pay",
            )
            actual = AttendanceSegment(
                summary=summary,
                period_kind="current_1_20",
                project_id=project_id,
                working_days=Decimal("10"),
                sunday_holiday_days=Decimal("0"),
                ot_hours=Decimal("0"),
            )
            summary.segments.extend(
                [
                    actual,
                    AttendanceSegment(
                        period_kind="current_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("8"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end",
                        project_id=project_id,
                        working_days=Decimal("8"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("8"),
                        sunday_holiday_days=Decimal("0"),
                        ot_hours=Decimal("0"),
                    ),
                ]
            )
            db.session.add(summary)
            db.session.commit()

            fallback_lines = {}
            fallback_amount = forecast_tail(
                employee,
                date(2026, 7, 1),
                date(2026, 7, 2),
                fallback_lines,
            )
            self.assertEqual(fallback_amount, Decimal("1000"))
            self.assertEqual(
                sum(
                    Decimal(str(line["forecast_working_days"]))
                    for line in fallback_lines.values()
                ),
                Decimal("1"),
            )

            holiday_only = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(holiday_only["holiday_amount"], Decimal("1000.00"))
            self.assertEqual(
                holiday_only["statutory_holiday_paid_days"],
                Decimal("1.00"),
            )

            actual.sunday_holiday_days = Decimal("1")
            actual.summary.special_days.append(
                AttendanceSpecialDay(
                    segment=actual,
                    period_kind="current_1_20",
                    project_id=project_id,
                    work_date=date(2026, 7, 1),
                    day_kind="sunday_statutory_holiday",
                    session="full_day",
                    handling="pay",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.commit()
            worked_and_paid = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(
                worked_and_paid["holiday_amount"],
                Decimal("2000.00"),
            )

            actual.summary.special_days[0].handling = "comp_leave"
            db.session.commit()
            worked_for_comp = calculate_payroll("2026-07", "site_daily")[0]
            self.assertEqual(
                worked_for_comp["holiday_amount"],
                Decimal("1000.00"),
            )

            db.session.add_all(
                [
                    WorkCalendarHoliday(
                        region_id=region_id,
                        holiday_date=holiday_date,
                        name=f"五月法定假日 {holiday_date:%m-%d}",
                        active=True,
                    )
                    for holiday_date in (date(2026, 5, 1), date(2026, 5, 25))
                ]
            )
            may_summary = AttendanceMonthlySummary(
                employee_id=daily_id,
                year_month="2026-05",
                status="received",
                special_day_handling="pay",
            )
            may_actual = AttendanceSegment(
                summary=may_summary,
                period_kind="current_1_20",
                project_id=project_id,
                working_days=Decimal("16"),
                sunday_holiday_days=Decimal("1"),
            )
            may_summary.segments.extend(
                [
                    may_actual,
                    AttendanceSegment(
                        period_kind="current_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("10"),
                        sunday_holiday_days=Decimal("1"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end",
                        project_id=project_id,
                        working_days=Decimal("0"),
                        sunday_holiday_days=Decimal("0"),
                    ),
                    AttendanceSegment(
                        period_kind="previous_21_end_forecast",
                        project_id=project_id,
                        working_days=Decimal("0"),
                        sunday_holiday_days=Decimal("0"),
                    ),
                ]
            )
            may_summary.special_days.append(
                AttendanceSpecialDay(
                    segment=may_actual,
                    period_kind="current_1_20",
                    project_id=project_id,
                    work_date=date(2026, 5, 1),
                    day_kind="statutory_holiday",
                    session="full_day",
                    handling="pay",
                    days=Decimal("1"),
                    status="active",
                )
            )
            db.session.add(may_summary)
            db.session.commit()
            may_payroll = calculate_payroll("2026-05", "site_daily")[0]
            self.assertEqual(
                sum(line["working_days"] for line in may_payroll["lines"]),
                Decimal("26.00"),
            )
            self.assertEqual(
                sum(line["holiday_days"] for line in may_payroll["lines"]),
                Decimal("4.00"),
            )
            self.assertEqual(
                may_payroll["statutory_holiday_paid_days"], Decimal("2.00")
            )
            self.assertEqual(may_payroll["base_amount"], Decimal("26000.00"))
            self.assertEqual(may_payroll["holiday_amount"], Decimal("4000.00"))
            self.assertEqual(may_payroll["gross_amount"], Decimal("30000.00"))

        management_id, _ = self.create_employee(
            "HKR",
            "management",
            "五點五天測試",
            "FIVE HALF WORKWEEK",
        )
        management_project_id = self.complete_employee(
            management_id,
            "management",
            "TMC046",
            "monthly",
            "31000",
            "Y7654321",
            "61110002",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, management_id)
            employee.current_assignment.workweek_days = Decimal("5.5")
            db.session.add(
                WorkCalendarHoliday(
                    region_id=employee.current_assignment.region_id,
                    holiday_date=date(2026, 7, 24),
                    name="工作日曆測試假日",
                    applies_to_statutory=False,
                    applies_to_public=True,
                    active=True,
                )
            )
            db.session.commit()
            rows = automatic_attendance_rows(
                employee,
                date(2026, 7, 21),
                date(2026, 7, 31),
            )
            self.assertEqual(
                sum(Decimal(str(item["working_days"])) for item in rows),
                Decimal("8.5"),
            )
            self.assertEqual(
                special_work_day_units(employee, date(2026, 7, 25)),
                Decimal("0.5"),
            )
            self.assertEqual(
                special_work_day_units(employee, date(2026, 7, 26)),
                Decimal("1"),
            )
            self.assertIsNone(
                special_work_day_units(employee, date(2026, 7, 27))
            )
            with self.app.test_request_context(
                method="POST",
                data={
                    "employee_id": str(management_id),
                    "current_1_20_project_id": [str(management_project_id)],
                    "current_1_20_working_days": ["0"],
                    "current_1_20_holiday_days": ["0.5"],
                    "current_1_20_special_work_entries": [json.dumps([
                        {"date": "2026-07-18"},
                    ])],
                },
            ):
                self.assertIsNone(
                    validate_attendance_segment_totals("2026-07")
                )
                self.assertIsNone(
                    validate_sunday_holiday_entries("2026-07")
                )


if __name__ == "__main__":
    unittest.main()
