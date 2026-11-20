"""Employee workspace routes: directory."""
from hkr_hr.workbench.web.employees.common import *  # noqa: F401, F403
from hkr_hr.workbench.web.employees.employment import requested_mpf_values


@employees_bp.route("/api/employees/next-no")
@login_required
def api_next_employee_no():
    employee_type = db.session.get(ReferenceValue, request.args.get("employee_type_id", type=int))
    if not employee_type:
        return {"employee_no": ""}
    return {"employee_no": next_employee_no(employee_type)}


@employees_bp.route("/employees")
@login_required
def list_employees():
    year_month = request.args.get("month") or session.get("operating_month") or current_month()
    try:
        month_start, month_end = parse_year_month(year_month)
    except (TypeError, ValueError):
        year_month = current_month()
        month_start, month_end = parse_year_month(year_month)
    session["operating_month"] = year_month
    session["employee_list_url"] = request.full_path.rstrip("?")
    employees = employee_query().options(*workbench_options()).all()
    status = request.args.get("status", "active")
    if status in {"active", "departed"}:
        employees = [
            employee
            for employee in employees
            if employee.derived_status == status
        ]
    readiness_filter = request.args.get("readiness", "")
    impact_filter = request.args.get("impact", "")
    monthly_view = readiness_filter in {"needs_action", "attendance", "payroll"} or bool(impact_filter)
    impact_counts = {}
    if monthly_view:
        summaries = {
            row.employee_id: row
            for row in AttendanceMonthlySummary.query.filter_by(
                year_month=year_month,
            ).all()
        }
        payroll_rows = {
            row["employee"].id: row
            for row in calculate_payroll(year_month, "all")
        }
        readiness_rows = [
            employee_readiness(
                employee,
                year_month,
                payroll_row=payroll_rows.get(employee.id),
                summary=summaries.get(employee.id),
                in_scope=employee.employed_during(month_start, month_end),
            )
            for employee in employees
        ]
        for row in readiness_rows:
            for item in row["payroll"]:
                target = {"薪酬未設定": ("employment", "salary"), "出糧銀行資料未填寫": ("personal", "bank"), "日工暫不支持固定補貼，請先撤回補貼記錄": ("employment", "allowance")}.get(item.get("label"))
                if target:
                    item["action_url"] = url_for("employees.view_employee", employee_id=row["employee"].id, tab=target[0], focus=target[1])
            summary = summaries.get(row["employee"].id)
            row["attendance_url"] = url_for("attendance.attendance_home", month=year_month, view="collection", employee_id=row["employee"].id, **({"summary_id": summary.id} if summary else {}))
        readiness_rows.sort(key=lambda row: (not any(not i["ok"] for i in row["payroll"]), row["attendance"]["ok"], row["employee"].employee_no))
        document_codes = {
            "staff_record",
            "signed_contract",
            "three_treasures",
            "visa",
            "sick_evidence",
        }
        impact_counts = {
            "payroll": 0,
            "leave": 0,
            "mpf": 0,
            "documents": 0,
        }
        for row in readiness_rows:
            missing_codes = {
                item["code"] for item in row["employee_data"] if not item["ok"]
            }
            row["impact"] = {
                "payroll": (
                    not row["attendance"]["ok"]
                    or any(not item["ok"] for item in row["payroll"])
                ),
                "leave": "employment" in missing_codes,
                "mpf": "mpf" in missing_codes,
                "documents": bool(missing_codes & document_codes),
            }
            for code, affected in row["impact"].items():
                if affected:
                    impact_counts[code] += 1
        if readiness_filter == "needs_action":
            readiness_rows = [row for row in readiness_rows if row["has_issue"]]
        elif readiness_filter == "attendance":
            readiness_rows = [
                row for row in readiness_rows if not row["attendance"]["ok"]
            ]
        elif readiness_filter == "payroll":
            readiness_rows = [
                row
                for row in readiness_rows
                if any(not item["ok"] for item in row["payroll"])
            ]
        if impact_filter in impact_counts:
            readiness_rows = [
                row for row in readiness_rows if row["impact"][impact_filter]
            ]
    else:
        readiness_rows = []
        for employee in sorted(employees, key=lambda person: person.employee_no):
            data = employee_data_items(employee)
            if employee.employed_during(month_start, month_end):
                data.append(mpf_data_item(employee, month_end))
            readiness_rows.append({"employee": employee, "employee_data": data})
    if readiness_filter == "employee_data":
        readiness_rows = [row for row in readiness_rows if any(not item["ok"] for item in row["employee_data"])]
    group_by = "position" if request.args.get("group_by") == "position" else "department"
    directory_groups = {}
    group_objects = {}
    for row in readiness_rows:
        assignment = row["employee"].current_assignment
        group = (assignment.primary_position if group_by == "position" else assignment.department) if assignment else None
        group_name = group.display_name if group else ""
        directory_groups.setdefault(group_name, []).append(row)
        group_objects.setdefault(group_name, group)
    return render_template(
        "employees/list.html",
        readiness_rows=readiness_rows, group_by=group_by,
        directory_groups=sorted(
            directory_groups.items(),
            key=lambda pair: reference_sort_key(group_by, group_objects.get(pair[0])) if pair[0] else (1, 9999, ""),
        ),
        year_month=year_month,
        readiness_filter=readiness_filter,
        impact_filter=impact_filter,
        impact_counts=impact_counts,
        employee_types=reference_options("employee_type"),
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
    )


@employees_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
def new_employee():
    employee_types = reference_options("employee_type")
    if request.method == "POST":
        chinese_name = request.form.get("chinese_name", "").strip() or None
        english_name = request.form.get("english_name", "").strip() or None
        employee_type = db.session.get(
            ReferenceValue,
            form_int("employee_type_id"),
        )
        payroll_group = request.form.get("payroll_group", "").strip()
        if not (chinese_name or english_name):
            flash("中文名或英文名至少填寫一項。", "error")
        elif not employee_type:
            flash("請選擇員工編號類別。", "error")
        elif payroll_group not in {item[0] for item in PAYROLL_GROUPS}:
            flash("請選擇薪酬組別。", "error")
        else:
            employee = Employee(
                employee_no=next_employee_no(employee_type),
                employee_type=employee_type,
                payroll_group=payroll_group,
                chinese_name=chinese_name,
                english_name=english_name,
                status="active",
            )
            db.session.add(employee)
            db.session.flush()
            if request.form.get("requires_attendance", "1") == "0":
                db.session.add(
                    set_long_term_attendance_policy(
                        employee,
                        current_month(),
                        False,
                        created_by=current_user.id,
                        remarks="建立員工檔案時設定長期免交考勤",
                    )
                )
            write_audit(
                "employee_created",
                "Employee",
                employee.id,
                employee_id=employee.id,
                detail=f"建立員工檔案 {employee.employee_no}",
                after=employee_audit_snapshot(employee),
            )
            db.session.commit()
            flash("員工檔案已建立。", "success")
            return redirect(url_for("employees.view_employee", employee_id=employee.id))
    return render_template(
        "employees/new.html",
        employee_types=employee_types,
        payroll_groups=PAYROLL_GROUPS,
    )


@employees_bp.post("/employees/<int:employee_id>/initial-setup")
@login_required
def initial_setup(employee_id):
    """Fill missing initial records in one transaction using the existing owners."""
    employee = db.get_or_404(Employee, employee_id)
    effective = parse_date(request.form.get("effective_from"))
    amount = parse_decimal(request.form.get("amount"))
    basis = request.form.get("salary_basis", "daily" if employee.payroll_group == "site_daily" else "monthly")
    method = request.form.get("monthly_pay_method") or "full_month"
    bank_name = request.form.get("bank_name", "").strip()
    bank_no = request.form.get("account_no", "").strip()
    currency = request.form.get("currency") or "HKD"
    try:
        if not effective:
            raise ValueError("請填寫入職／初始生效日期。")
        if not employee.salaries and (not valid_salary_amount(amount) or basis not in {"monthly", "daily"} or method not in {"full_month", "attendance_days"}):
            raise ValueError("請完整填寫薪酬類型及金額。")
        if not employee.bank_accounts and bool(bank_name) != bool(bank_no):
            raise ValueError("銀行名稱及戶口號碼請一起填寫，或稍後補齊。")
        mpf_values = requested_mpf_values() if not employee.mpf_enrollments and (request.form.get("mpf_selection") or request.form.get("mpf_exempt")) else None
    except ValueError as exc:
        flash(str(exc), "error")
        return employee_redirect(employee.id, "overview")
    initial_leave = parse_decimal(request.form.get("initial_leave_days") or "7")
    if not employee.employment_periods:
        from hkr_hr.leave.api import validate_leave_setup as validate
        try:
            validate(effective, initial_leave)
        except ValueError:
            flash("leave.setup_invalid", "error")
            return employee_redirect(employee.id, "overview")
    created = []
    if not employee.employment_periods:
        period = EmployeeEmploymentPeriod(employee=employee, start_date=effective, contract_annual_leave_days=initial_leave, annual_leave_policy_year=date.today().year, annual_leave_contract_verified=False)
        db.session.add(period)
        created.append(("EmployeeEmploymentPeriod", period, {"start_date": effective.isoformat()}))
    if not employee.assignments:
        assignment = create_assignment(employee, effective, employee.payroll_group,
            workweek_days=request.form.get("workweek_days"),
            region_id=form_int("region_id"), project_id=form_int("project_id"),
            department_id=form_int("department_id"), employer_id=form_int("employer_id"),
            payroll_entity_id=form_int("payroll_entity_id"),
            position_ids=[int(i) for i in request.form.getlist("position_ids") if str(i).isdigit()])
        created.append(("EmployeeAssignment", assignment, assignment_snapshot(assignment)))
    if not employee.salaries:
        salary = create_salary(employee, effective, basis, currency, amount, monthly_pay_method=method)
        created.append(("EmployeeSalary", salary, salary_snapshot(salary)))
    if not employee.bank_accounts and bank_name and bank_no:
        account = EmployeeBankAccount(employee=employee, effective_from=effective, bank_name=bank_name, account_no=bank_no, currency=currency, status="active")
        db.session.add(account)
        db.session.flush()
        sync_legacy_bank_fields(employee)
        created.append(("EmployeeBankAccount", account, bank_account_snapshot(account)))
    if mpf_values:
        _, scheme, member, mode = mpf_values
        mpf = create_mpf_enrollment(employee, effective, scheme=scheme, member_account_no=member, contribution_mode=mode)
        created.append(("EmployeeMpfEnrollment", mpf, mpf_snapshot(mpf)))
    db.session.flush()
    if any(name == "EmployeeEmploymentPeriod" for name, _, _ in created):
        from hkr_hr.leave.api import save_current_balance
        balance = save_current_balance(employee)
        write_audit("annual_leave_balance_updated", "EmployeeAnnualLeaveBalance", balance.id,
                    employee_id=employee.id, detail="初始任職建立本年度年假",
                    after={"initial_days": str(initial_leave), "applied": str(balance.calculated_entitled_days)})
    for model_name, record, after in created:
        write_audit("initial_setup", model_name, record.id, employee_id=employee.id, before=None, after=after)
    db.session.commit()
    flash("入職資料已保存。", "success")
    return employee_redirect(employee.id, "overview")


@employees_bp.route("/employees/<int:employee_id>")
@login_required
def view_employee(employee_id):
    from hkr_hr.payroll.api import review_rows
    employee = db.get_or_404(Employee, employee_id)
    refs = reference_map()
    attendance_rows = AttendanceMonthlySummary.query.filter_by(
        employee_id=employee.id
    ).order_by(AttendanceMonthlySummary.year_month.desc()).all()
    payroll_by_month = {}
    payroll_results = (
        PayrollEmployeeResult.query.join(PayrollRun)
        .filter(PayrollEmployeeResult.employee_id == employee.id)
        .order_by(
            PayrollRun.year_month.desc(),
            PayrollRun.created_at.desc(),
            PayrollRun.id.desc(),
            PayrollEmployeeResult.id.desc(),
        )
        .all()
    )
    for result in payroll_results:
        payroll_by_month.setdefault(result.run.year_month, result)
    corrections_by_month = {}
    for record in AttendanceCorrection.query.filter_by(employee_id=employee.id).order_by(AttendanceCorrection.source_month):
        corrections_by_month.setdefault(record.pay_month, []).append(record)
    extra_months = sorted((payroll_by_month.keys() | corrections_by_month.keys()) -
                          {item.year_month for item in attendance_rows}, reverse=True)
    current_bank = current_bank_account_on(employee, date.today())
    document_management_tabs = {
        document.id: document_management_tab(document)
        for document in employee.documents
    }
    hash_counts = {}
    for document in employee.documents:
        if document.status == "active" and document.content_sha256:
            hash_counts[document.content_sha256] = hash_counts.get(document.content_sha256, 0) + 1
    shared_document_hashes = {digest for digest, count in hash_counts.items() if count > 1}
    pay_month = request.args.get("pay_month", "")
    payroll_return = originating_payroll(request.args, pay_month)
    pay_assignment = None
    salary_dates = []
    if payroll_return:
        _, pay_end = parse_year_month(pay_month)
        pay_assignment = current_assignment_on(employee, pay_end)
        if request.args.get("focus") == "salary":
            pay_summary = calculate_employee(employee, pay_month).get("attendance")
            salary_dates = salary_gaps(employee, pay_summary)
    return render_template(
        "employees/detail.html",
        payroll_return=payroll_return, pay_assignment=pay_assignment, salary_dates=salary_dates,
        active_successor=active_successor, credential_state=credential_state,
        leave_review_count=len(review_rows(employee.id)[0]),
        employee=employee,
        today=date.today(),
        refs=refs,
        projects=WorkProject.query.filter_by(active=True).order_by(
            WorkProject.name
        ).all(),
        payroll_groups=PAYROLL_GROUPS,
        mpf_schemes=MpfScheme.query.filter_by(active=True).order_by(
            MpfScheme.name
        ).all(),
        identity_types=IDENTITY_TYPE_OPTIONS,
        termination_reasons=TERMINATION_REASONS,
        change_history=build_change_history(employee),
        personal_history=build_personal_history(employee),
        credential_history=build_credential_history(employee),
        employment_status_history=build_employment_status_history(employee),
        missing=missing_employee_data_labels(employee),
        missing_items=[
            item for item in employee_data_items(employee) if not item["ok"]
        ],
        leave=annual_leave_summary(employee),
        comp_leave=comp_leave_summary(employee),
        leave_records=EmployeeAnnualLeaveRecord.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeAnnualLeaveRecord.leave_date.desc(),
            EmployeeAnnualLeaveRecord.id.desc(),
        ).all(),
        work_injury_periods=EmployeeWorkInjuryPeriod.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeWorkInjuryPeriod.payroll_start_date.desc(),
            EmployeeWorkInjuryPeriod.id.desc(),
        ).all(),
        allowances=EmployeeAllowance.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeAllowance.effective_from.desc(),
            EmployeeAllowance.id.desc(),
        ).all(),
        average_wage=average_wage_prefill(employee),
        current_bank=current_bank,
        bank_accounts=EmployeeBankAccount.query.filter_by(
            employee_id=employee.id
        ).order_by(
            EmployeeBankAccount.effective_from.desc(),
            EmployeeBankAccount.id.desc(),
        ).all(),
        masked_bank=masked_bank_account(
            current_bank.account_no if current_bank else employee.bank_account_no
        ),
        contracts=GeneratedContract.query.filter_by(employee_id=employee.id)
        .order_by(GeneratedContract.created_at.desc())
        .all(),
        attendance=attendance_rows,
        payroll_by_month=payroll_by_month, corrections_by_month=corrections_by_month, extra_months=extra_months,
        payroll_adjustments=PayrollAdjustment.query.filter_by(
            employee_id=employee.id
        ).order_by(
            PayrollAdjustment.year_month.desc(),
            PayrollAdjustment.id.desc(),
        ).all(),
        default_payroll_month=current_month(),
        attendance_required_now=attendance_required(
            employee,
            current_month(),
        ),
        attendance_policy=policy_on(employee.id, current_month()),
        document_categories={**DOCUMENT_CATEGORIES, "credential": "證件"},
        certificate_files={c.document_id: c.certificate_type.display_name for c in employee.certificates
                           if c.document_id and c.document and c.document.category == "qualification"
                           and c.certificate_type.code not in {"DEGREE", "SKILL"}},
        replacement_reasons=REPLACEMENT_REASONS,
        document_management_tabs=document_management_tabs,
        shared_document_hashes=shared_document_hashes,
    )

