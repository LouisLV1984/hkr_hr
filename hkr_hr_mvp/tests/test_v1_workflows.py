import io
import re
import tempfile
import unittest
import zipfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook
from sqlalchemy import inspect, text

from app import create_app
from models import (
    AuditLog,
    AttendanceBatch,
    AttendanceBatchItem,
    AttendanceMonthlySummary,
    AttendanceSegment,
    Employee,
    EmployeeAnnualLeaveBalance,
    EmployeeAnnualLeaveAllocation,
    EmployeeAnnualLeaveRecord,
    EmployeeCertificate,
    EmployeeDocument,
    EmployeeEmploymentPeriod,
    EmployeeFinalPaymentCase,
    EmployeeIdentity,
    EmployeeAssignment,
    EmployeeQualification,
    EmployeeSalary,
    EmployeeTaskNote,
    EmployeeVisa,
    GeneratedContract,
    ImportBatch,
    PayrollAdjustment,
    PayrollEmployeeResult,
    PayrollRun,
    ReferenceList,
    ReferenceValue,
    User,
    WorkProject,
    db,
)
from tools.hr_core import (
    annual_leave_buckets,
    annual_leave_days_between,
    employee_type_by_code,
    ensure_reference_seed,
    reference_by_code,
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
)
from tools.releases import CURRENT_VERSION, NEXT_VERSION, RELEASES
from tools.schema_migrations import (
    apply_additive_migrations,
    schema_compatibility_issues,
)


APP_ROOT = Path(__file__).resolve().parents[1]


def pdf_bytes(label):
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
        + f"% {label}\n".encode("ascii")
        + b"%%EOF\n"
    )


class V1WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": (
                    f"sqlite:///{(temp_root / 'test.db').as_posix()}"
                ),
                "HKR_HR_UPLOAD_ROOT": temp_root / "uploads",
                "GENERATED_CONTRACT_ROOT": temp_root / "contracts",
                "CONTRACT_TEMPLATE_ROOT": APP_ROOT / "contract_templates",
                "PAYROLL_TEMPLATE_ROOT": APP_ROOT / "payroll_templates",
                "ATTENDANCE_BATCH_ROOT": temp_root / "attendance",
                "IMPORT_ROOT": temp_root / "imports",
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
                "gender": "male",
                "date_of_birth": birth_date,
                "mobile_region_code": "+852",
                "mobile_number": mobile,
                "email": f"{mobile}@example.test",
                "residential_address": "Acceptance test address",
                "bank_name": "BANK OF CHINA (HONG KONG) LIMITED",
                "bank_account_no": f"QA-{identity_number}",
                "mpf_mode": mpf_mode,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/employees/{employee_id}/bank-confirm",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return ids["project"]

    def upload_document(self, employee_id, category, filename):
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
        self.assertIn('class="context-nav"', batch_page)
        self.assertIn('class="attendance-rail"', batch_page)
        self.assertIn("current-batch-panel", batch_page)
        self.assertIn("recent-batches-panel", batch_page)
        self.assertIn('class="attendance-workbench"', batch_page)
        self.assertNotIn('class="workbench-left"', batch_page)
        with self.app.app_context():
            batch = AttendanceBatch.query.one()
            items = list(batch.items)
            self.assertEqual(len(items), len(employees_and_projects))
            item_ids = [item.id for item in items]
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
                },
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)

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
                }
                for result in run.employee_results
            }
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
                self.assertEqual(
                    sheet["F4"].value.date(),
                    date(2026, 7, 1),
                )
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
                                f"+AA{row}+AD{row}-AE{row}+AF{row}"
                                f"+AG{row},2)"
                            ),
                        )
                    else:
                        self.assertEqual(
                            total_formula,
                            (
                                f"=ROUND(M{row}+P{row}+S{row}+T{row}"
                                f"+AB{row}+AE{row}-AF{row}+AG{row}"
                                f"+AH{row},2)"
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
            self.assertEqual(float(employee.current_period.notice_period_value), 7.0)
            self.assertEqual(employee.current_period.notice_period_unit, "day")
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
        self.assertEqual(report_payroll.mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(report_payroll.data)) as archive:
            self.assertEqual(len(archive.namelist()), 3)

        delete_id, _ = self.create_employee(
            "TE",
            "site_daily",
            "只供刪除測試",
            "DELETE ME",
        )
        response = self.client.post(
            f"/employees/{delete_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Employee, delete_id))
            self.assertEqual(Employee.query.count(), 3)

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
            "/attendance?month=2099-08"
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
            self.assertEqual(leave.days, Decimal("1.0"))
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
        self.assertIn('form="project-update-', html)

        self.client.get("/logout")
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
            "/admin/import",
            "/admin/import/template",
        ):
            self.assertEqual(self.client.get(admin_path).status_code, 403)
            self.assertNotIn(f'href="{admin_path}"', references_page)

    def test_employee_quick_reference_creation_and_return_context(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "快速選項驗收",
            "QUICK REFERENCE QA",
        )
        self.client.get("/logout")
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
        self.assertIn("建立初始任職", empty_page)

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
        self.assertIn("<summary>調整任職</summary>", html)
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
            },
            follow_redirects=True,
        )
        future_html = future.get_data(as_text=True)
        self.assertIn("將於 2099-01-01 生效；目前任職暫不變", future_html)
        self.assertIn("當前任職</span><h2>項目經理</h2>", future_html)

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
            "/admin/import",
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
        self.assertIn("考勤管理", dashboard)
        self.assertIn("薪酬與匯出", dashboard)
        self.assertIn('aria-current="page"', dashboard)
        attendance = self.client.get("/attendance").get_data(as_text=True)
        self.assertIn('class="app-layout"', attendance)
        self.assertIn('class="app-shell"', attendance)
        self.assertIn('class="context-nav"', attendance)
        self.assertIn('data-attendance-upload-form', attendance)
        self.assertIn("拖放 PDF 到此或點擊選擇", attendance)
        self.assertIn("可隨時返回過往批次繼續處理", attendance)
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
        self.assertIn("Payroll &amp; Exports", english)
        self.assertNotIn("建立員工檔案", english)
        english_references = self.client.get(
            "/references?list=education_level&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Education level", english_references)
        self.assertIn("Available for new records", english_references)
        self.assertNotIn("學歷", english_references)
        self.assertIn("Renaming updates existing displays", english_references)
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
        self.assertNotIn("出糧週期", english_payroll)
        english_attendance = self.client.get(
            "/attendance?lang=en"
        ).get_data(as_text=True)
        self.assertIn("Drop PDFs here or click to choose", english_attendance)
        self.assertIn("Return to any previous batch to continue", english_attendance)
        simplified = self.client.get(
            "/employees?lang=zh-Hans"
        ).get_data(as_text=True)
        self.assertIn("员工总表", simplified)
        self.assertIn("考勤管理", simplified)
        self.assertIn("薪酬与导出", simplified)
        self.assertNotIn("員工總表", simplified)
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

    def test_bank_setup_uses_one_operator_warning(self):
        employee_id, _ = self.create_employee(
            "HKR",
            "site_monthly",
            "銀行提示測試",
            "BANK WARNING TEST",
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            warnings = employee_warnings(employee)
            self.assertEqual(warnings.count("銀行資料未完成"), 1)
            self.assertNotIn("缺銀行資料", warnings)
            self.assertNotIn("缺銀行證明", warnings)

        page = self.client.get(
            f"/employees/{employee_id}"
        ).get_data(as_text=True)
        self.assertEqual(page.count("銀行資料未完成"), 1)
        self.assertNotIn("缺銀行資料", page)
        self.assertNotIn("缺銀行證明", page)

    def test_user_guide_page_and_release_alignment(self):
        self.assertEqual(CURRENT_VERSION, "V0.1.4")
        self.assertEqual(NEXT_VERSION, "V0.1.5")
        self.assertEqual(
            [(release["version"], release["date"]) for release in RELEASES],
            [
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
        self.assertIn(f"> 適用版本：{CURRENT_VERSION}", source)
        self.assertIn(f"> 更新日期：{RELEASES[0]['date']}", source)
        self.assertNotIn("適用對象：", source)
        self.assertIn("本月 1–20 日實際", source)
        self.assertIn("上月 21 日至月底原預估", source)
        self.assertIn("最小單位為 0.5 日", source)
        self.assertIn("撤回離職資料", source)
        self.assertIn("導出薪金證明書", source)
        self.assertIn("頁面會自動計算", source)
        self.assertIn("修正／撤回／替換／補件", source)

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

        self.client.get("/logout")
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
        combined = employee_template + leave_template

        self.assertNotIn("floating-editor", combined)
        self.assertNotIn("details class=\"row-editor\"", combined)
        self.assertEqual(combined.count("record-editor-form"), 14)
        self.assertIn("data-record-editor-trigger", combined)

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

    def test_acceptance_fixes_for_admin_employee_import_and_template(self):
        users_page = self.client.get("/admin/users?lang=en")
        self.assertEqual(users_page.status_code, 200)
        users_html = users_page.get_data(as_text=True)
        self.assertIn("Existing users", users_html)
        self.assertIn("Add user", users_html)
        self.assertIn("Current account", users_html)
        self.assertIn('data-dialog-open="manage-user-', users_html)

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
        bank_confirmed = self.client.post(
            f"/employees/{employee_id}/bank-confirm",
            follow_redirects=True,
        )
        self.assertIn(
            "新銀行戶口已核對",
            bank_confirmed.get_data(as_text=True),
        )

        template = self.client.get("/admin/import/template")
        self.assertEqual(template.status_code, 200)
        workbook = load_workbook(io.BytesIO(template.data), data_only=False)
        self.assertEqual(
            [cell.value for cell in workbook["員工匯入"][1]],
            [
                "員工編號",
                "中文姓名",
                "英文姓名",
            ],
        )
        self.assertIn("填寫說明", workbook.sheetnames)
        workbook.close()

        invalid = Workbook()
        invalid_sheet = invalid.active
        invalid_sheet.append(
            [
                "員工編號",
                "中文姓名",
                "英文姓名",
            ]
        )
        invalid_sheet.append(
            [
                "DUP001",
                "重複一",
                "",
            ]
        )
        invalid_sheet.append(
            [
                "DUP001",
                "重複二",
                "",
            ]
        )
        invalid_sheet.append(
            [
                "NONAME001",
                "",
                "",
            ]
        )
        invalid_bytes = io.BytesIO()
        invalid.save(invalid_bytes)
        invalid_bytes.seek(0)
        response = self.client.post(
            "/admin/import",
            data={"file": (invalid_bytes, "duplicate.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        invalid_preview = self.client.get(response.headers["Location"])
        invalid_html = invalid_preview.get_data(as_text=True)
        self.assertIn("檔案內員工編號重複", invalid_html)
        self.assertIn("中文姓名或英文姓名至少填寫一項", invalid_html)
        self.assertIn("不能確認匯入", invalid_html)
        self.assertNotIn(">確認導入</button>", invalid_html)

        valid = Workbook()
        valid_sheet = valid.active
        valid_sheet.append(
            [
                "員工編號",
                "中文姓名",
                "英文姓名",
            ]
        )
        valid_sheet.append(
            [
                "IMPORT001",
                "",
                "IMPORT TEST",
            ]
        )
        valid_bytes = io.BytesIO()
        valid.save(valid_bytes)
        valid_bytes.seek(0)
        response = self.client.post(
            "/admin/import",
            data={"file": (valid_bytes, "valid.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            batch = ImportBatch.query.order_by(ImportBatch.id.desc()).first()
            batch_id = batch.id
            self.assertFalse(batch.result_json["has_errors"])
            self.assertEqual(batch.result_json["validation_version"], 3)
            self.assertEqual(batch.result_json["rows"][0]["english_name"], "IMPORT TEST")
        confirmed = self.client.post(
            f"/admin/import/{batch_id}/confirm",
            follow_redirects=True,
        )
        self.assertIn("已匯入 1 名員工", confirmed.get_data(as_text=True))
        with self.app.app_context():
            imported = Employee.query.filter_by(employee_no="IMPORT001").one()
            self.assertEqual(imported.payroll_group, "unassigned")
            self.assertEqual(imported.employee_type.code, "OTHER")
            self.assertEqual(imported.english_name, "IMPORT TEST")
            self.assertIsNone(imported.current_assignment)
            self.assertIsNone(imported.current_salary)

        exports_page = self.client.get(
            "/exports?section=employees&lang=en"
        ).get_data(as_text=True)
        self.assertIn("Employee records workbook", exports_page)
        self.assertIn("Employment and Salary History", exports_page)
        self.assertNotIn('name="warning"', exports_page)
        self.assertNotIn('name="expiry"', exports_page)
        self.assertNotIn("Management Overview", exports_page)

        audit_page = self.client.get("/admin/audit?lang=en").get_data(
            as_text=True
        )
        self.assertIn("Created employee from XLSX", audit_page)
        self.assertIn("Employee import batch", audit_page)
        self.assertNotIn(">employee_imported<", audit_page)

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
                "attendance_batch_items.content_sha256",
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
            self.assertIn("content_sha256", batch_item_columns)
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
            self.assertEqual(row["current_actual_total"], Decimal("5000.00"))
            self.assertEqual(row["forecast_tail_total"], Decimal("2500.00"))
            self.assertEqual(row["actual_previous_tail"], Decimal("2000.00"))
            self.assertEqual(row["expected_previous_tail"], Decimal("3000.00"))
            self.assertEqual(row["gross_amount"], Decimal("6500.00"))
            self.assertEqual(row["overpay_amount"], Decimal("1000.00"))
            self.assertEqual(row["underpay_amount"], Decimal("0.00"))
            self.assertEqual(row["employee_mpf"], Decimal("325.00"))
            self.assertEqual(row["employer_mpf"], Decimal("325.00"))

        dashboard = self.client.get(
            "/dashboard?month=2026-07"
        ).get_data(as_text=True)
        self.assertIn("HKD 6,175.00", dashboard)

        page = self.client.get(
            "/attendance-payroll"
            "?year_month=2026-07&payroll_group=site_daily"
        ).get_data(as_text=True)
        self.assertIn("data-payroll-filter", page)
        self.assertIn("本月 1–20 日實際", page)
        self.assertIn("上月 21 日至月底原預估", page)
        self.assertIn("/payroll/export-current", page)
        self.assertNotIn("確認並保存本次計算", page)
        self.assertNotIn("計算預覽", page)

        response = self.client.post(
            "/payroll/export-current",
            data={
                "year_month": "2026-07",
                "payroll_group": "site_daily",
            },
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
            self.assertEqual(result.gross_amount, Decimal("6500.00"))

    def test_record_corrections_withdrawals_and_task_notes(self):
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

        response = self.client.post(
            f"/dashboard/tasks/{employee_id}/missing_signed_contract/notes",
            data={
                "month": "2026-07",
                "progress": "in_progress",
                "note": "已向地盤追收，明日再跟進",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = self.client.get(
            "/dashboard?task_type=missing_signed_contract"
            "&task_progress=in_progress"
        ).get_data(as_text=True)
        self.assertIn(employee_no, page)
        self.assertIn("已向地盤追收，明日再跟進", page)
        self.assertIn("admin", page)
        with self.app.app_context():
            self.assertEqual(EmployeeTaskNote.query.count(), 1)
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

    def test_effective_records_and_adjustments_can_be_corrected_or_withdrawn(
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

        response = self.client.post(
            f"/employees/{employee_id}/payroll-adjustments",
            data={
                "year_month": "2026-07",
                "label": "項目津貼",
                "amount": "1,000.00",
                "project_id": alternate_project_id,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            adjustment_id = PayrollAdjustment.query.filter_by(
                employee_id=employee_id
            ).one().id
        response = self.client.post(
            f"/payroll-adjustments/{adjustment_id}/correct",
            data={
                "year_month": "2026-08",
                "label": "更正後項目津貼",
                "amount": "1,200.00",
                "project_id": original_project_id,
                "remarks": "更正月份、項目及金額",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Payroll 調整項目已更正",
            response.get_data(as_text=True),
        )
        with self.app.app_context():
            employee = db.session.get(Employee, employee_id)
            assignment = db.session.get(
                type(employee.assignments[0]),
                assignment_id,
            )
            salary = db.session.get(type(employee.salaries[0]), salary_id)
            adjustment = db.session.get(PayrollAdjustment, adjustment_id)
            self.assertEqual(assignment.effective_from, date(2026, 2, 15))
            self.assertEqual(assignment.project_id, alternate_project_id)
            self.assertEqual(salary.effective_from, date(2026, 2, 15))
            self.assertEqual(salary.amount, Decimal("32000.00"))
            self.assertEqual(adjustment.year_month, "2026-08")
            self.assertEqual(adjustment.project_id, original_project_id)
            self.assertEqual(adjustment.amount, Decimal("1200.00"))
            assignment_audit = AuditLog.query.filter_by(
                action="assignment_corrected"
            ).one()
            salary_audit = AuditLog.query.filter_by(
                action="salary_corrected"
            ).one()
            adjustment_audit = AuditLog.query.filter_by(
                action="payroll_adjustment_corrected"
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
            self.assertEqual(
                adjustment_audit.before_json["year_month"],
                "2026-07",
            )
            self.assertEqual(
                adjustment_audit.after_json["year_month"],
                "2026-08",
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
            f"/payroll-adjustments/{adjustment_id}/withdraw",
            data={"reason": "整筆調整不應存在"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
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
                db.session.get(PayrollAdjustment, adjustment_id).status,
                "voided",
            )
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
            self.assertEqual(
                AuditLog.query.filter_by(
                    action="payroll_adjustment_withdrawn"
                ).count(),
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

        response = self.client.post(
            f"/employees/{employee_id}/delete",
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
        self.assertIn("年假記錄已新增", response.get_data(as_text=True))
        with self.app.app_context():
            record = EmployeeAnnualLeaveRecord.query.one()
            self.assertEqual(record.days, Decimal("5.0"))
            self.assertEqual(
                EmployeeAnnualLeaveAllocation.query.filter_by(
                    record_id=record.id
                ).count(),
                2,
            )
            allocations = {
                item.balance.year: item.days for item in record.allocations
            }
            self.assertEqual(allocations[2023], Decimal("3.0"))
            self.assertEqual(allocations[2025], Decimal("2.0"))
            employee = db.session.get(Employee, employee_id)
            buckets = annual_leave_buckets(
                employee,
                as_of=date(2026, 8, 14),
            )
            by_year = {item["year"]: item for item in buckets}
            self.assertEqual(by_year[2023]["remaining"], Decimal("5.0"))
            self.assertEqual(by_year[2025]["remaining"], Decimal("6.0"))
            self.assertEqual(by_year[2025]["expiry_date"], date(2026, 12, 31))

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
        self.assertIn("離職結算資料已保存", page)
        self.assertIn(employee_no, page)
        self.assertIn("2025-05-01", page)
        with self.app.app_context():
            period = db.session.get(EmployeeEmploymentPeriod, period_id)
            result = calculate_final_payment(period)
            self.assertFalse(result["blockers"])
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

        response = self.client.post(
            "/final-payment/export",
            data={
                "year_month": "2026-08",
                "payroll_group": "management",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument",
            response.content_type,
        )
        workbook = load_workbook(io.BytesIO(response.data), data_only=False)
        self.assertEqual(workbook.sheetnames, ["OFFICE"])
        sheet = workbook["OFFICE"]
        self.assertEqual(sheet["D8"].value, employee_no)
        self.assertEqual(sheet["J8"].value, "=ROUND(H8*I8,2)")
        self.assertEqual(sheet["M8"].value, "=ROUND(K8*L8,2)")
        self.assertTrue(str(sheet["V8"].value).startswith("=ROUND("))
        self.assertEqual(sheet["X8"].value, "=ROUND(V8+W8,2)")
        self.assertEqual(sheet["Y8"].value, "=X8")

        response = self.client.post(
            "/final-payment/export",
            data={
                "year_month": "2026-08",
                "payroll_group": "all",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    "HKR_Final_Payment_2026-08_site_daily.xlsx",
                    "HKR_Final_Payment_2026-08_site_monthly.xlsx",
                    "HKR_Final_Payment_2026-08_management.xlsx",
                },
            )


if __name__ == "__main__":
    unittest.main()
