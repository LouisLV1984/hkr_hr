"""Local UI-test server. Temporary synthetic database/files; never production."""
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_profile_integrity import ProfileIntegrityTests
from models import db, EmployeeCertificate, EmployeeAnnualLeaveRecord, EmployeeSalary, EmployeeAssignment
from tools.hr_core import reference_by_code


def main():
    fixture = ProfileIntegrityTests()
    fixture.setUp()
    try:
        eid = fixture.employee("介面驗證")
        did = fixture.document(eid, "staff_record")
        with fixture.app.app_context():
            db.session.add(EmployeeAssignment(employee_id=eid, effective_from=date(2026, 1, 1),
                payroll_group="management", workweek_days=5,
                region_id=reference_by_code("work_region", "HK").id))
            db.session.add_all([
                EmployeeSalary(employee_id=eid, effective_from=date(2022, 9, 19),
                    effective_to=date(2025, 12, 31), salary_basis="monthly", currency="HKD",
                    amount=15000, evidence_document_id=did),
                EmployeeSalary(employee_id=eid, effective_from=date(2026, 1, 1),
                    salary_basis="monthly", currency="HKD", amount=20000,
                    evidence_document_id=did, remarks="Synthetic long salary history note. " * 10),
            ])
            db.session.add(EmployeeCertificate(employee_id=eid,
                certificate_type_id=reference_by_code("certificate_type", "WORKER_REGISTRATION").id,
                certificate_no="SYNTHETIC", expiry_date=date.today() - timedelta(days=3)))
            db.session.add(EmployeeAnnualLeaveRecord(employee_id=eid, leave_date=date(2026, 8, 4),
                days=1, entitlement_year=2026, leave_type="sick"))
            db.session.commit()
        fixture.app.run(host="127.0.0.1", port=8766, use_reloader=False)
    finally:
        fixture.tearDown()


if __name__ == "__main__":
    main()
