from sqlalchemy import inspect, text

from models import SystemSetting, db


SCHEMA_VERSION = "2.8"
REQUIRED_V1_TABLES = {
    "employee_salary_records",
    "employees",
    "employee_assignments",
    "employee_salaries",
    "employee_mpf_enrollments",
    "mpf_schemes",
    "employee_documents",
    "employee_bank_accounts",
    "attendance_batches",
    "attendance_monthly_summaries",
    "employee_attendance_policies",
    "attendance_segments",
    "attendance_special_days",
    "employee_comp_leave_credits",
    "employee_comp_leave_allocations",
    "employee_work_injury_periods",
    "employee_work_injury_monthly_expenses",
    "payroll_runs",
    "payroll_employee_results",
    "payroll_project_lines",
}

ADDITIVE_V1_MIGRATIONS = {
    "users": {
        "last_login_at": "TIMESTAMP",
        "last_seen_at": "TIMESTAMP",
        "last_logout_at": "TIMESTAMP",
    },
    "employee_documents": {
        "content_sha256": "VARCHAR(64)",
        "general_document_type_id": "INTEGER",
    },
    "attendance_batch_items": {
        "content_sha256": "VARCHAR(64)",
        "year_month": "VARCHAR(7)",
    },
    "attendance_segments": {
        "large_ecall_count": "INTEGER NOT NULL DEFAULT 0",
        "ecall_count": "INTEGER NOT NULL DEFAULT 0",
        "other_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
    },
    "attendance_monthly_summaries": {
        "monthly_project_allocation": "JSON",
        "special_day_handling": "VARCHAR(20) NOT NULL DEFAULT 'pay'",
    },
    "attendance_special_days": {
        "session": "VARCHAR(20) NOT NULL DEFAULT 'full_day'",
    },
    "employee_allowances": {
        "allowance_type": "VARCHAR(30) NOT NULL DEFAULT 'special'",
        "exchange_rate": "NUMERIC(14, 6)",
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
    },
    "employee_assignments": {
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
        "workweek_days": "NUMERIC(3, 1) NOT NULL DEFAULT 6",
    },
    "employee_salaries": {
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
        "monthly_pay_method": "VARCHAR(30) NOT NULL DEFAULT 'full_month'",
    },
    "payroll_adjustments": {
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
    },
    "employee_qualifications": {
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
    },
    "employee_certificates": {
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
    },
    "employee_visas": {
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
    },
    "employee_annual_leave_balances": {
        "entitled_days_override": "NUMERIC(5, 1)",
        "expiry_date": "DATE",
        "extended_until": "DATE",
    },
    "employee_annual_leave_records": {
        "leave_units_json": "JSON",
        "end_date": "DATE",
        "start_session": "VARCHAR(20) NOT NULL DEFAULT 'am'",
        "end_session": "VARCHAR(20) NOT NULL DEFAULT 'pm'",
        "status": "VARCHAR(30) NOT NULL DEFAULT 'active'",
        "leave_type": "VARCHAR(30) NOT NULL DEFAULT 'annual'",
        "evidence_document_id": "INTEGER",
    },
    "payroll_employee_results": {
        "large_ecall_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "ecall_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "mpf_relevant_income": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "mpf_scheme_name": "VARCHAR(200)",
        "mpf_scheme_code": "VARCHAR(80)",
        "mpf_employer_account_no": "VARCHAR(80)",
        "mpf_payroll_group_no": "VARCHAR(120)",
        "mpf_member_account_no": "VARCHAR(120)",
        "mpf_member_name": "VARCHAR(200)",
        "mpf_calculation_mode": "VARCHAR(20)",
        "traffic_meal_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "special_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "sick_leave_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "work_injury_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "unpaid_leave_deduction": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "annual_leave_days": "NUMERIC(8, 2) NOT NULL DEFAULT 0",
        "sick_leave_days": "NUMERIC(8, 2) NOT NULL DEFAULT 0",
        "unpaid_leave_days": "NUMERIC(8, 2) NOT NULL DEFAULT 0",
        "work_injury_days": "NUMERIC(8, 2) NOT NULL DEFAULT 0",
        "work_injury_medical_reimbursement_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "attendance_other_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
    },
    "payroll_project_lines": {
        "large_ecall_count": "INTEGER NOT NULL DEFAULT 0",
        "ecall_count": "INTEGER NOT NULL DEFAULT 0",
        "large_ecall_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "ecall_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "traffic_meal_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "special_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
        "attendance_other_allowance_amount": "NUMERIC(14, 2) NOT NULL DEFAULT 0",
    },
    "employee_work_injury_periods": {
        "pay_mode": "VARCHAR(30) NOT NULL DEFAULT 'four_fifths'",
    },
    "employee_final_payment_cases": {
        "leave_wage_total": "NUMERIC(14, 2)",
    },
    "work_calendar_holidays": {
        "applies_to_statutory": "BOOLEAN NOT NULL DEFAULT TRUE",
        "applies_to_public": "BOOLEAN NOT NULL DEFAULT FALSE",
    },
}


def existing_tables():
    return set(inspect(db.engine).get_table_names())


def schema_is_v1():
    return (
        REQUIRED_V1_TABLES.issubset(existing_tables())
        and not schema_compatibility_issues()
    )


def schema_compatibility_issues():
    """Return missing columns on tables that already exist.

    SQLAlchemy's create_all() creates missing tables but does not add columns
    to an existing table. V0.1 test databases therefore need an explicit
    one-time rebuild before the V1 models can be queried safely.
    """
    inspector = inspect(db.engine)
    present_tables = set(inspector.get_table_names())
    issues = {}
    for table_name, table in db.metadata.tables.items():
        if table_name not in present_tables:
            continue
        present_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        missing_columns = sorted(set(table.columns.keys()) - present_columns)
        if missing_columns:
            issues[table_name] = missing_columns
    return issues


def format_schema_issues(issues):
    return "; ".join(
        f"{table}: {', '.join(columns)}"
        for table, columns in sorted(issues.items())
    )


def apply_additive_migrations():
    """Add backward-compatible V1 columns without resetting employee data."""
    inspector = inspect(db.engine)
    present_tables = set(inspector.get_table_names())
    changed = []
    for table_name, columns in ADDITIVE_V1_MIGRATIONS.items():
        if table_name not in present_tables:
            continue
        present_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column_name, column_ddl in columns.items():
            if column_name in present_columns:
                continue
            db.session.execute(
                text(
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{column_name}" {column_ddl}'
                )
            )
            changed.append(f"{table_name}.{column_name}")
    if changed:
        db.session.commit()
    return changed


def retire_legacy_tables():
    """Remove tables belonging only to retired, one-time setup workflows."""
    retired = []
    for table_name in ("import_batches", "employee_task_notes"):
        if table_name not in existing_tables():
            continue
        db.session.execute(text(f'DROP TABLE "{table_name}"'))
        retired.append(table_name)
    if retired:
        db.session.commit()
    return retired


def cleanup_orphaned_workflow_rows():
    """Remove workflow shells left by the previous hard-delete behavior."""
    present_tables = existing_tables()
    required = {
        "attendance_batch_items",
        "attendance_batches",
        "payroll_runs",
        "payroll_employee_results",
    }
    if not required.issubset(present_tables):
        return {}
    statements = {
        "attendance_batch_items": """
            DELETE FROM attendance_batch_items
            WHERE status = 'saved'
              AND employee_id IS NULL
              AND summary_id IS NULL
        """,
        "attendance_batches": """
            DELETE FROM attendance_batches AS batch
            WHERE NOT EXISTS (
                SELECT 1
                FROM attendance_batch_items AS item
                WHERE item.batch_id = batch.id
            )
        """,
        "payroll_runs": """
            DELETE FROM payroll_runs AS run
            WHERE NOT EXISTS (
                SELECT 1
                FROM payroll_employee_results AS result
                WHERE result.run_id = run.id
            )
        """,
    }
    removed = {}
    for name, statement in statements.items():
        result = db.session.execute(text(statement))
        removed[name] = max(result.rowcount or 0, 0)
    db.session.commit()
    return removed


def retire_obsolete_audit_events():
    """Remove audit events belonging to retired application workflows."""
    if "audit_logs" not in existing_tables():
        return 0
    result = db.session.execute(
        text(
            "DELETE FROM audit_logs "
            "WHERE action = 'bank_confirmed_for_payroll'"
        )
    )
    db.session.commit()
    return max(result.rowcount or 0, 0)


def repair_legacy_inferred_special_day_attendance():
    """Clear the retired Sunday-as-work split without touching real work.

    Genuine special-day work has dated AttendanceSpecialDay evidence. The
    retired generator instead split all four exempt Monthly/OFFICE periods
    into ordinary weekdays and Sundays. Only that exact pattern is repaired.
    """
    from models import AttendanceMonthlySummary, AuditLog, Employee
    from tools.attendance_policy import (
        is_legacy_inferred_special_day_summary,
    )

    required = {
        "attendance_monthly_summaries",
        "attendance_segments",
        "attendance_special_days",
        "employees",
        "audit_logs",
    }
    if not required.issubset(existing_tables()):
        return 0

    summaries = (
        AttendanceMonthlySummary.query
        .join(Employee)
        .filter(
            AttendanceMonthlySummary.status == "not_required",
            Employee.payroll_group.in_(("site_monthly", "management")),
        )
        .all()
    )
    repaired = 0
    for summary in summaries:
        if not is_legacy_inferred_special_day_summary(summary):
            continue
        before_segments = [
            {
                "id": segment.id,
                "period_kind": segment.period_kind,
                "working_days": str(segment.working_days),
                "sunday_holiday_days": str(segment.sunday_holiday_days),
            }
            for segment in summary.segments
        ]
        for segment in summary.segments:
            segment.sunday_holiday_days = 0
        after_segments = [
            {
                "id": segment.id,
                "period_kind": segment.period_kind,
                "working_days": str(segment.working_days),
                "sunday_holiday_days": "0",
            }
            for segment in summary.segments
        ]
        db.session.add(
            AuditLog(
                employee_id=summary.employee_id,
                action="attendance_legacy_special_days_repaired",
                entity_type="AttendanceMonthlySummary",
                entity_id=summary.id,
                before_json={"segments": before_segments},
                after_json={"segments": after_segments},
                detail=(
                    f"{summary.year_month} 免交考勤舊版日曆星期日數已清除；"
                    "真正額外工作只認逐日記錄"
                ),
            )
        )
        repaired += 1
    if repaired:
        db.session.commit()
    return repaired


def ensure_schema():
    db.create_all()
    changed_columns = apply_additive_migrations()
    if "employee_assignments.workweek_days" in changed_columns:
        db.session.execute(
            text(
                "UPDATE employee_assignments "
                "SET workweek_days = CASE "
                "WHEN payroll_group = 'management' THEN 5 ELSE 6 END"
            )
        )
        db.session.commit()
    db.session.execute(
        text(
            """
            INSERT INTO employee_bank_accounts
                (employee_id, effective_from, bank_name, account_no, currency,
                 status, created_at, updated_at)
            SELECT e.id, COALESCE(
                       (SELECT MIN(p.start_date)
                        FROM employee_employment_periods AS p
                        WHERE p.employee_id = e.id),
                       CURRENT_DATE
                   ),
                   e.bank_name, e.bank_account_no, 'HKD', 'active',
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM employees AS e
            WHERE e.bank_name IS NOT NULL
              AND e.bank_account_no IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM employee_bank_accounts AS b
                  WHERE b.employee_id = e.id
              )
            """
        )
    )
    db.session.commit()
    retire_legacy_tables()
    cleanup_orphaned_workflow_rows()
    retire_obsolete_audit_events()
    repaired_special_day_summaries = (
        repair_legacy_inferred_special_day_attendance()
    )
    issues = schema_compatibility_issues()
    if issues:
        raise RuntimeError(
            "Existing HKR HR tables are not compatible with V1. "
            f"Missing columns: {format_schema_issues(issues)}"
        )
    setting = SystemSetting.query.filter_by(key="schema_version").first()
    if not setting:
        setting = SystemSetting(key="schema_version")
        db.session.add(setting)
    setting.value_json = {"version": SCHEMA_VERSION}
    db.session.commit()
    return {
        "legacy_special_day_summaries": repaired_special_day_summaries,
    }


def reset_postgres_schema(expected_database):
    current = db.session.execute(text("select current_database()")).scalar_one()
    if current != expected_database or expected_database != "hkr_hr_db":
        raise RuntimeError(
            f"Refusing destructive reset for {current!r}; expected hkr_hr_db."
        )
    db.session.execute(text("drop schema public cascade"))
    db.session.execute(text("create schema public"))
    db.session.commit()
