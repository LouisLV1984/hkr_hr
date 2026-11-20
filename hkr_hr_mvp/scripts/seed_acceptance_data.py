"""Create and retain three representative V1 acceptance employees."""

import shutil
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = APP_ROOT.parent
sys.path.insert(0, str(APP_ROOT))

from app import create_app
from hkr_hr.attendance.api import AttendanceMonthlySummary, AttendanceSegment
from hkr_hr.employees.api import Employee, EmployeeCertificate, EmployeeEmploymentPeriod, EmployeeIdentity, EmployeeVisa
from hkr_hr.documents.api import EmployeeDocument
from hkr_hr.references.api import MpfScheme, ReferenceValue, WorkProject
from hkr_hr.platform.db import User, db
from hkr_hr.employees.api import create_assignment, create_mpf_enrollment, create_salary
from hkr_hr.references.api import employee_type_by_code, ensure_reference_seed, reference_by_code
from hkr_hr.platform.files import file_sha256


YEAR_MONTH = "2026-07"


def employee(number, type_code, group, chinese_name, english_name):
    row = Employee.query.filter_by(employee_no=number).first()
    if not row:
        row = Employee(
            employee_no=number,
            employee_type=employee_type_by_code(type_code),
            payroll_group=group,
            chinese_name=chinese_name,
            english_name=english_name,
            status="active",
        )
        db.session.add(row)
        db.session.flush()
    return row


def ensure_period(row, start_date, annual_leave=7, probation_end=None):
    period = EmployeeEmploymentPeriod.query.filter_by(
        employee_id=row.id,
        end_date=None,
    ).first()
    if not period:
        period = EmployeeEmploymentPeriod(
            employee=row,
            start_date=start_date,
        )
        db.session.add(period)
    period.start_date = start_date
    period.contract_annual_leave_days = Decimal(str(annual_leave))
    period.probation_end_date = probation_end
    return period


def ensure_mpf(row, effective_from, scheme_code, member_account_no):
    existing = next(
        (
            item
            for item in row.mpf_enrollments
            if item.status == "active" and item.effective_from == effective_from
        ),
        None,
    )
    scheme = MpfScheme.query.filter_by(code=scheme_code).one()
    if existing:
        existing.scheme = scheme
        existing.member_account_no = member_account_no
        existing.contribution_mode = scheme.calculation_mode
        return existing
    return create_mpf_enrollment(
        row,
        effective_from,
        scheme=scheme,
        member_account_no=member_account_no,
    )


def ensure_identity(row, identity_type, number, primary=False, long_term=False):
    identity = EmployeeIdentity.query.filter_by(
        employee_id=row.id,
        identity_type=identity_type,
        identity_number=number,
    ).first()
    if not identity:
        identity = EmployeeIdentity(
            employee=row,
            identity_type=identity_type,
            identity_number=number,
        )
        db.session.add(identity)
    identity.status = "active"
    identity.is_primary = primary
    identity.is_long_term = long_term
    if primary:
        for item in row.identities:
            if item is not identity:
                item.is_primary = False
    return identity


def ensure_document(row, category, source, admin_id, month=None):
    existing = EmployeeDocument.query.filter_by(
        employee_id=row.id,
        category=category,
        status="active",
    ).first()
    if existing and Path(existing.stored_path).is_file():
        return existing
    target_dir = APP_ROOT / "uploads" / row.employee_no / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    document = EmployeeDocument(
        employee=row,
        category=category,
        title=category.replace("_", " ").title(),
        original_filename=source.name,
        stored_path=str(target),
        mime_type="application/pdf",
        file_ext=".pdf",
        file_size=target.stat().st_size,
        content_sha256=file_sha256(target),
        status="active",
        effective_month=month,
        uploaded_by=admin_id,
        uploaded_at=datetime.utcnow(),
        remarks="V1 acceptance fixture - retain for user review",
    )
    db.session.add(document)
    db.session.flush()
    return document


def ensure_assignment(row, start_date, group, project, department, position):
    if not row.assignments:
        create_assignment(
            row,
            start_date,
            group,
            region_id=reference_by_code("work_region", "HK").id,
            project_id=project.id,
            department_id=department.id,
            employer_id=reference_by_code("employer", "HK_RIVER").id,
            payroll_entity_id=reference_by_code(
                "payroll_entity",
                "HK_RIVER",
            ).id,
            social_insurance_entity_id=reference_by_code(
                "social_insurance_entity",
                "NONE",
            ).id,
            labour_dispatch_entity_id=reference_by_code(
                "labour_dispatch_entity",
                "NONE",
            ).id,
            position_ids=[position.id],
            remarks="V1 acceptance initial assignment",
        )


def ensure_salary(row, start_date, basis, amount):
    if not row.salaries:
        create_salary(
            row,
            start_date,
            basis,
            "HKD",
            Decimal(str(amount)),
            remarks="V1 acceptance initial salary",
        )


def ensure_attendance(row, document, current, previous):
    summary = AttendanceMonthlySummary.query.filter_by(
        employee_id=row.id,
        year_month=YEAR_MONTH,
    ).first()
    if not summary:
        summary = AttendanceMonthlySummary(
            employee=row,
            year_month=YEAR_MONTH,
        )
        db.session.add(summary)
        db.session.flush()
    summary.document = document
    summary.status = "received"
    summary.confirmed_at = datetime.utcnow()
    for item in list(summary.segments):
        db.session.delete(item)
    for kind, rows in (
        ("current_1_20", current),
        ("previous_21_end", previous),
    ):
        for row_values in rows:
            project, days, ot, holiday, *ecall_values = row_values
            large_ecall = ecall_values[0] if ecall_values else 0
            ecall = ecall_values[1] if len(ecall_values) > 1 else 0
            db.session.add(
                AttendanceSegment(
                    summary=summary,
                    period_kind=kind,
                    project=project,
                    working_days=Decimal(str(days)),
                    ot_hours=Decimal(str(ot)),
                    sunday_holiday_days=Decimal(str(holiday)),
                    large_ecall_count=int(large_ecall),
                    ecall_count=int(ecall),
                )
            )
    return summary


def seed():
    ensure_reference_seed()
    admin = User.query.filter_by(username="admin").first()
    admin_id = admin.id if admin else None
    ha = WorkProject.query.filter_by(code="TMC046").one()
    pc = WorkProject.query.filter_by(code="PC_AD014").one()
    headquarters = WorkProject.query.filter_by(code="UNASSIGNED").one()
    site = reference_by_code("department", "SITE")
    management_department = reference_by_code("department", "MANAGEMENT")
    worker = reference_by_code("position", "WORKER")
    foreman = reference_by_code("position", "FOREMAN")
    manager = reference_by_code("position", "PROJECT_MANAGER")

    monthly = employee(
        "QA-HKR-M01",
        "HKR",
        "site_monthly",
        "黃文飛",
        "HUANG WEN FEI",
    )
    monthly.gender = "male"
    monthly.date_of_birth = date(1986, 4, 12)
    monthly.mobile_region_code = "+852"
    monthly.mobile_number = "6111 1001"
    monthly.email = "qa.monthly@example.test"
    monthly.residential_address = "九龍驗收測試地址 1 號"
    monthly.bank_name = reference_by_code("bank", "BOCHK").display_name
    monthly.bank_account_no = "012-345-678901"
    ensure_period(monthly, date(2025, 10, 27), 10)
    ensure_identity(monthly, "hkid", "QA-M190283(1)", primary=True)
    ensure_assignment(
        monthly,
        date(2025, 10, 27),
        "site_monthly",
        ha,
        site,
        foreman,
    )
    ensure_salary(monthly, date(2025, 10, 27), "monthly", "30000")
    ensure_mpf(monthly, date(2025, 10, 27), "BCOM_MONTHLY", "QA-MPF-M01")

    daily = employee(
        "QA-HKRD-D01",
        "HKRD",
        "site_daily",
        "黃振雄",
        "WONG CHUN HUNG",
    )
    daily.gender = "male"
    daily.date_of_birth = date(1978, 7, 20)
    daily.mobile_region_code = "+852"
    daily.mobile_number = "6111 1002"
    daily.email = "qa.daily@example.test"
    daily.residential_address = "新界驗收測試地址 2 號"
    daily.bank_name = reference_by_code("bank", "HSBC").display_name
    daily.bank_account_no = "004-345-678902"
    ensure_period(daily, date(2025, 11, 10), 7)
    ensure_identity(daily, "hkid", "QA-D290384(2)", primary=True)
    ensure_assignment(
        daily,
        date(2025, 11, 10),
        "site_daily",
        ha,
        site,
        worker,
    )
    ensure_salary(daily, date(2025, 11, 10), "daily", "1650")
    ensure_mpf(daily, date(2025, 11, 10), "BCT_DAILY", "QA-MPF-D01")

    management = employee(
        "QA-ASMTP-V01",
        "ASMTP",
        "management",
        "余英奇",
        "YU YING QI",
    )
    management.gender = "male"
    management.date_of_birth = date(1990, 2, 18)
    management.mobile_region_code = "+852"
    management.mobile_number = "6111 1003"
    management.email = "qa.management@example.test"
    management.residential_address = "香港驗收測試地址 3 號"
    management.bank_name = reference_by_code("bank", "HASE").display_name
    management.bank_account_no = "024-345-678903"
    management.visa_required = True
    ensure_period(
        management,
        date(2026, 4, 1),
        12,
        probation_end=date(2026, 6, 30),
    )
    ensure_identity(management, "hkid", "QA-V390485(3)", primary=True)
    ensure_identity(
        management,
        "mainland_id",
        "440100199002180019",
        long_term=True,
    )
    ensure_assignment(
        management,
        date(2026, 4, 1),
        "management",
        headquarters,
        management_department,
        manager,
    )
    ensure_salary(management, date(2026, 4, 1), "monthly", "36000")
    ensure_mpf(
        management,
        date(2026, 4, 1),
        "BCT_SERIES_800",
        "QA-MPF-V01",
    )

    sources = {
        monthly.id: {
            "three_treasures": WORKSPACE_ROOT / "三寶" / "黃文飛三寶.pdf",
            "staff_record": WORKSPACE_ROOT / "Staff record" / "Huang WenFei 黃文飛 (木工) $1400 Staff Record 僱員資料登記表.pdf",
            "signed_contract": WORKSPACE_ROOT / "Contract" / "Contract Daily Site Staff Huang WenFei 黃文飛 (木工) $1400 27Oct25  Ver 20250801.pdf",
        },
        daily.id: {
            "three_treasures": WORKSPACE_ROOT / "三寶" / "黃振雄三寶.pdf",
            "staff_record": WORKSPACE_ROOT / "Staff record" / "黃振雄 (水喉) $1650 Staff Record 僱員資料登記表.pdf",
            "signed_contract": WORKSPACE_ROOT / "Contract" / "Contract Daily Site Staff 黃振雄 10Nov25 $1650 Ver 20250801.pdf",
        },
        management.id: {
            "three_treasures": WORKSPACE_ROOT / "三寶" / "余英奇三寶.pdf",
            "staff_record": WORKSPACE_ROOT / "Staff record" / "余英奇staff record.pdf",
        },
    }
    documents = {}
    for row in (monthly, daily, management):
        documents[row.id] = {}
        for category, source in sources[row.id].items():
            documents[row.id][category] = ensure_document(
                row,
                category,
                source,
                admin_id,
            )
    attendance_source = (
        WORKSPACE_ROOT
        / "考勤表"
        / "202605 醫管局 attendance-SAMSON SIGNED.pdf"
    )
    for row in (monthly, daily, management):
        documents[row.id]["attendance_pdf"] = ensure_document(
            row,
            "attendance_pdf",
            attendance_source,
            admin_id,
            YEAR_MONTH,
        )
    visa_document = ensure_document(
        management,
        "visa",
        sources[management.id]["three_treasures"],
        admin_id,
    )
    visa = EmployeeVisa.query.filter_by(
        employee_id=management.id,
        visa_no="QA-VISA-2026-001",
    ).first()
    if not visa:
        visa = EmployeeVisa(
            employee=management,
            visa_category=reference_by_code("visa_category", "ASMTP"),
            visa_no="QA-VISA-2026-001",
            issue_date=date(2026, 3, 15),
            expiry_date=date(2027, 3, 14),
            document=visa_document,
        )
        db.session.add(visa)

    safety_type = reference_by_code("certificate_type", "SAFETY_CARD")
    if not EmployeeCertificate.query.filter_by(
        employee_id=daily.id,
        certificate_no="QA-SC-001",
    ).first():
        db.session.add(
            EmployeeCertificate(
                employee=daily,
                certificate_type=safety_type,
                certificate_no="QA-SC-001",
                valid_from=date(2026, 1, 1),
                expiry_date=date(2028, 12, 31),
                document=documents[daily.id]["three_treasures"],
            )
        )

    ensure_attendance(
        monthly,
        documents[monthly.id]["attendance_pdf"],
        [(ha, 17, 8, 3, 1, 2)],
        [(ha, 8, 3, 2, 1, 1)],
    )
    ensure_attendance(
        daily,
        documents[daily.id]["attendance_pdf"],
        [(ha, 10, 4, 2, 1, 1), (pc, 7, 2, 1, 0, 1)],
        [(ha, 8, 1, 2, 1, 1)],
    )
    ensure_attendance(
        management,
        documents[management.id]["attendance_pdf"],
        [(headquarters, 17, 0, 3, 1, 1)],
        [(headquarters, 8, 0, 2, 0, 1)],
    )
    db.session.commit()
    print("Retained V1 acceptance employees:")
    for row in (monthly, daily, management):
        print(f"  {row.employee_no} | {row.display_name} | {row.payroll_group}")


if __name__ == "__main__":
    application = create_app()
    with application.app_context():
        seed()
