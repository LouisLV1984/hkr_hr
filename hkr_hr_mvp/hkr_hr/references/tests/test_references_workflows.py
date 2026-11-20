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


class ReferencesWorkflowTests(HrAppTestCase):
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


if __name__ == "__main__":
    unittest.main()
