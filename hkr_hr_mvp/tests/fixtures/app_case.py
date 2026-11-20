"""Fast, isolated test base classes and synthetic helpers for HKR HR."""
from __future__ import annotations

import io
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

import app as app_module
from hkr_hr.attendance.api import AttendanceBatch
from hkr_hr.employees.api import Employee, EmployeeEmploymentPeriod
from hkr_hr.documents.api import EmployeeDocument
from hkr_hr.references.api import MpfScheme, WorkProject
from hkr_hr.platform.db import User, db
from hkr_hr.attendance.api import set_long_term_attendance_policy
from hkr_hr.employees.api import create_mpf_enrollment
from hkr_hr.references.api import employee_type_by_code, ensure_reference_seed, reference_by_code
from hkr_hr.platform.files import store_employee_file, uploaded_file_sha256
from hkr_hr.payroll.api import calculate_employee
from hkr_hr.attendance.api import profile_revision


APP_ROOT = Path(__file__).resolve().parents[2]

# Precompute password hashes once per test process instead of per test method.
_ADMIN_PASSWORD_HASH = generate_password_hash("test-admin-password")
_HR_PASSWORD_HASH = generate_password_hash("test-hr-password")


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


class HrAppTestCase(unittest.TestCase):
    """Isolated Flask + SQLite in-memory test harness with zero cross-test state."""

    use_file_db = False

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        db_uri = (
            f"sqlite:///{(temp_root / 'test.db').as_posix()}"
            if self.use_file_db
            else "sqlite:///:memory:"
        )
        self.app = app_module.create_app(
            {
                "TESTING": True,
                "CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": db_uri,
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
            now = datetime.utcnow()
            admin = User(
                username="admin",
                role="admin",
                active=True,
                password_hash=_ADMIN_PASSWORD_HASH,
                last_login_at=now,
                last_seen_at=now,
            )
            hr_user = User(
                username="hr_test",
                role="hr",
                active=True,
                password_hash=_HR_PASSWORD_HASH,
            )
            db.session.add_all([admin, hr_user])
            db.session.commit()
            admin_session_id = admin.get_id()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["_user_id"] = admin_session_id
            sess["_fresh"] = True

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
            employee = Employee.query.filter_by(chinese_name=chinese_name).one()
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
            none_social = reference_by_code("social_insurance_entity", "NONE")
            none_dispatch = reference_by_code("labour_dispatch_entity", "NONE")
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
            scheme_code = "BCT_DAILY" if mpf_mode == "casual" else "BCOM_MONTHLY"
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
            document = (
                EmployeeDocument.query.filter_by(
                    employee_id=employee_id,
                    category=category,
                )
                .order_by(EmployeeDocument.id.desc())
                .first()
            )
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
        batch_page = self.client.get(response.headers["Location"]).get_data(as_text=True)
        self.assertIn("data-attendance-upload-form", batch_page)
        self.assertIn("data-attendance-drop-zone", batch_page)
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
        details_page = self.client.get("/attendance?month=2026-07&view=details").get_data(as_text=True)
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
        policies_page = self.client.get("/attendance?month=2026-07&view=policies").get_data(as_text=True)
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
                    "current_21_end_forecast_project_id": [str(project_id)],
                    "current_21_end_forecast_working_days": ["10"],
                    "current_21_end_forecast_holiday_days": ["0"],
                    "previous_21_end_project_id": [str(project_id)],
                    "previous_21_end_working_days": ["8"],
                    "previous_21_end_ot_hours": ["1"],
                    "previous_21_end_holiday_days": ["2"],
                    "previous_21_end_large_ecall_count": ["1"],
                    "previous_21_end_ecall_count": ["1"],
                    "previous_21_end_forecast_project_id": [str(project_id)],
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
                "data-attendance-employee",
                locked_page,
            )
            self.assertNotIn(
                f'name="employee_id" value="{wrong_employee_id}" '
                "data-attendance-employee",
                locked_page,
            )

    def document(self, eid, category="staff_record", suffix="A"):
        response = self.client.post(
            f"/employees/{eid}/documents/new",
            data={
                "category": category,
                "file": (io.BytesIO(pdf_bytes(suffix)), suffix + ".pdf"),
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            return (
                EmployeeDocument.query.filter_by(employee_id=eid)
                .order_by(EmployeeDocument.id.desc())
                .first()
                .id
            )


class PayrollTestCase(HrAppTestCase):
    """Shared base for attendance/leave/payroll workflow tests."""

    def employee(self, group="site_daily", number=1):
        eid, _ = self.create_employee("HKR", group, f"驗收{number}", f"QA {number}")
        project = self.complete_employee(
            eid,
            group,
            "TMC046",
            "daily" if group == "site_daily" else "monthly",
            "1000" if group == "site_daily" else "31000",
            f"QA{number:06}",
            f"6123{number:04}",
        )
        return eid, project

    def request_leave(self, eid, start="2026-08-04", end="2026-08-04", **extra):
        form = dict(
            leave_type="sick",
            start_date=start,
            end_date=end,
            start_session="am",
            end_session="pm",
        )
        form.update(extra)
        return self.client.post(
            f"/employees/{eid}/annual-leave", data=form, follow_redirects=True
        )

    def ready(self, number=1):
        eid, _ = self.employee("management", number)
        with self.app.app_context():
            employee = db.session.get(Employee, eid)
            db.session.add(set_long_term_attendance_policy(employee, "2026-01", False))
            db.session.commit()
            row = calculate_employee(employee, "2026-08")
            self.assertFalse(row["blockers"])
            self.assertGreaterEqual(row["net_amount"], 0)
        return eid


class ProfileTestCase(HrAppTestCase):
    """Shared base for employee profile integrity and workspace tests."""

    def employee(self, suffix="A"):
        eid, _ = self.create_employee("HKR", "management", "測試" + suffix, "QA " + suffix)
        with self.app.app_context():
            db.session.add(
                EmployeeEmploymentPeriod(
                    employee_id=eid,
                    start_date=date(2026, 1, 1),
                    contract_annual_leave_days=14,
                    probation_end_date=date(2026, 3, 31),
                )
            )
            db.session.commit()
        return eid

