"""Independent salary register: saved facts only, no write-back to Payroll."""
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from models import Employee, SalaryRecord
from tools.hr_core import parse_year_month, current_salary_on, reference_options

START_MONTH = "2026-04"
MONEY_FIELDS = ("gross_amount", "employee_mpf", "net_amount")


def checked_month(value):
    if not re.fullmatch(r"\d{4}-\d{2}", value or ""):
        raise ValueError("salary_record.invalid_month")
    try:
        parse_year_month(value)
    except ValueError:
        raise ValueError("salary_record.invalid_month") from None
    if value < START_MONTH or value > date.today().strftime("%Y-%m"):
        raise ValueError("salary_record.invalid_month")
    return value


def money(value):
    try:
        amount = Decimal(value.strip().replace(",", ""))
        if not amount.is_finite() or abs(amount) >= Decimal("1000000000000") or amount != amount.quantize(Decimal(".01")):
            raise ValueError
        return amount.quantize(Decimal(".01"))
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError("salary_record.invalid_money") from None


def record_values(record):
    return dict(currency=record.currency, **{f: str(getattr(record, f)) for f in MONEY_FIELDS},
                remarks=record.remarks or "")


def parse_values(form, key):
    values = {f: money(form.get(f"{key}.{f}", "")) for f in MONEY_FIELDS}
    currency = form.get(f"{key}.currency", "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("salary_record.invalid_currency")
    return dict(currency=currency, **{f: str(v) for f, v in values.items()},
                remarks=form.get(f"{key}.remarks", "").strip()[:2000])


def expected_employees(month, entity_id=None):
    start, end = parse_year_month(month)
    employees = Employee.query.order_by(Employee.employee_no).all()
    result = {}
    for employee in employees:
        employed = any(p.start_date <= end and (p.end_date is None or p.end_date >= start)
                       for p in employee.employment_periods)
        if not employed:
            continue
        assignments = [a for a in employee.assignments if a.status == "active" and a.effective_from <= end
                       and (a.effective_to is None or a.effective_to >= start)]
        entities = {a.payroll_entity_id for a in assignments if a.payroll_entity_id}
        if not entities:
            entities = {None}
        for entity in entities:
            if entity_id and entity != entity_id:
                continue
            salary = current_salary_on(employee, end)
            result[employee.id, entity] = dict(employee=employee, currency=salary.currency if salary else "HKD")
    return result


def monthly_rows(month, entity_id, extra_employee_id=None, search=""):
    records = {r.employee_id: r for r in SalaryRecord.query.filter_by(
        year_month=month, payroll_entity_id=entity_id).all()}
    expected = expected_employees(month, entity_id)
    employees = {eid: v["employee"] for (eid, _), v in expected.items()}
    employees.update({eid: r.employee for eid, r in records.items()})
    if extra_employee_id:
        employee = Employee.query.filter_by(id=extra_employee_id).first()
        if employee:
            employees[employee.id] = employee
    from tools.text_search import chinese_search_variants
    terms = chinese_search_variants(search) if search else []
    rows = []
    for employee in sorted(employees.values(), key=lambda e: e.employee_no):
        if terms and not any(term.casefold() in f'{employee.employee_no} {employee.chinese_name or ""} {employee.english_name or ""}'.casefold() for term in terms):
            continue
        record = records.get(employee.id)
        salary = current_salary_on(employee, parse_year_month(month)[1])
        values = (record_values(record) if record and record.status == "active" else
                  dict(currency=salary.currency if salary else "HKD", gross_amount="", employee_mpf="", net_amount="", remarks=""))
        rows.append(dict(employee=employee, record=record, values=values,
                         expected=(employee.id, entity_id) in expected))
    return rows


def annual_summary(year, entity_id=None):
    if year < 2026 or year > date.today().year:
        raise ValueError("salary_record.invalid_year")
    months = [f"{year}-{m:02}" for m in range(4,13)] + [f"{year+1}-{m:02}" for m in range(1,4)]
    elapsed = [m for m in months if m <= date.today().strftime("%Y-%m")]
    expected, employee_map, currency_map = {}, {}, {}
    for month in elapsed:
        for key, value in expected_employees(month, entity_id).items():
            expected.setdefault(key, set()).add(month)
            employee_map[key] = value["employee"]
            currency_map[key] = value["currency"]
    query = SalaryRecord.query.filter(SalaryRecord.status == "active", SalaryRecord.year_month.in_(months))
    if entity_id:
        query = query.filter_by(payroll_entity_id=entity_id)
    details = query.order_by(SalaryRecord.employee_id, SalaryRecord.year_month, SalaryRecord.payroll_entity_id).all()
    groups, saved = {}, {}
    for record in details:
        pair = record.employee_id, record.payroll_entity_id
        employee_map[pair] = record.employee
        saved.setdefault(pair, set()).add(record.year_month)
        groups.setdefault((*pair, record.currency), []).append(record)
    for pair in expected:
        if not any(key[:2] == pair for key in groups):
            groups[(*pair, currency_map[pair])] = []
    entities = {e.id: e.display_name for e in reference_options('payroll_entity', active_only=False)}
    rows = []
    for (eid, entity, currency), records in groups.items():
        pair = eid, entity
        rows.append(dict(employee=employee_map[pair], entity_id=entity, entity=entities.get(entity), currency=currency,
                         amounts={f: sum((getattr(r,f) for r in records), Decimal("0")) if records else None for f in MONEY_FIELDS},
                         months=sorted({r.year_month for r in records}),
                         missing=sorted(expected.get(pair,set()) - saved.get(pair,set())),
                         needs_assignment=entity is None))
    rows.sort(key=lambda r: (r["employee"].employee_no, r["entity"] or "", r["currency"]))
    return rows, details, months
