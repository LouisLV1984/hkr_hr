import io
import re
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.exceptions import InvalidFileException
from werkzeug.utils import secure_filename

from models import (
    AuditLog,
    Employee,
    ImportBatch,
    User,
    db,
)
from tools.hr_core import (
    employee_type_by_code,
    normalize_reference_display,
    write_audit,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ROLE_OPTIONS = [
    ("admin", "Admin / 系統管理員"),
    ("hr", "HR / 人事同事"),
]


def require_admin():
    if current_user.role != "admin":
        abort(403)


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
def users():
    require_admin()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role")
            if not username or not password or role not in {"admin", "hr"}:
                flash("請完整填寫用戶名、角色和密碼。", "error")
            elif User.query.filter_by(username=username).first():
                flash("用戶名已存在。", "error")
            else:
                user = User(username=username, role=role, active=True)
                user.set_password(password)
                db.session.add(user)
                db.session.flush()
                write_audit(
                    "user_created",
                    "User",
                    user.id,
                    detail=f"{username} / {role}",
                )
                db.session.commit()
                flash("用戶已新增。", "success")
                return redirect(url_for("admin.users"))
        elif action == "update":
            user = db.session.get(User, request.form.get("user_id", type=int))
            if not user:
                abort(404)
            active = request.form.get("active") == "on"
            role = request.form.get("role")
            if role not in {"admin", "hr"}:
                abort(400)
            if user.id == current_user.id and not active:
                flash("不能停用目前登入的帳戶。", "error")
                return redirect(url_for("admin.users"))
            if user.id == current_user.id and role != "admin":
                flash("不能移除目前登入帳戶的 Admin 權限。", "error")
                return redirect(url_for("admin.users"))
            before = {"role": user.role, "active": user.active}
            user.role = role
            user.active = active
            password = request.form.get("password", "").strip()
            if password:
                user.set_password(password)
            write_audit(
                "user_updated",
                "User",
                user.id,
                detail=user.username,
                before=before,
                after={
                    "role": user.role,
                    "active": user.active,
                    "password_changed": bool(password),
                },
            )
            db.session.commit()
            flash("用戶已更新。", "success")
            return redirect(url_for("admin.users"))
    return render_template(
        "admin/users.html",
        users=User.query.order_by(User.username.asc()).all(),
        roles=ROLE_OPTIONS,
    )


@admin_bp.route("/audit")
@login_required
def audit():
    require_admin()
    page = max(1, request.args.get("page", 1, type=int))
    logs = (
        AuditLog.query.order_by(AuditLog.created_at.desc())
        .paginate(page=page, per_page=80, error_out=False)
    )
    return render_template("admin/audit.html", logs=logs)


HEADER_ALIASES = {
    "employee_no": ("员工编码", "員工編號", "employee no", "employee_no"),
    "chinese_name": ("中文名", "中文姓名"),
    "english_name": ("英文名", "英文姓名"),
}

IMPORT_HEADERS = [
    "員工編號",
    "中文姓名",
    "英文姓名",
]


def normalized_header(value):
    return normalize_reference_display(value).casefold()


def locate_columns(header):
    available = {
        normalized_header(value): index
        for index, value in enumerate(header)
        if value not in {None, ""}
    }
    result = {}
    for key, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if normalized_header(alias) in available:
                result[key] = available[normalized_header(alias)]
                break
    return result


def cell_text(row, columns, key):
    index = columns.get(key)
    if index is None or index >= len(row):
        return ""
    value = row[index]
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value or "").strip()


def parse_import_file(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = (
            workbook["香港(瑞沃)"]
            if "香港(瑞沃)" in workbook.sheetnames
            else workbook.active
        )
        values = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()
    if not values:
        return [], ["工作表沒有資料。"]
    header_index = next(
        (
            index
            for index, row in enumerate(values[:20])
            if "employee_no" in locate_columns(row)
            and {"chinese_name", "english_name"} & set(locate_columns(row))
        ),
        None,
    )
    if header_index is None:
        return [], ["找不到員工編號及中文姓名／英文姓名欄。"]
    columns = locate_columns(values[header_index])
    rows = []
    errors = []
    seen_employee_nos = set()
    existing_employee_nos = {
        value.casefold()
        for value, in db.session.query(Employee.employee_no).all()
        if value
    }
    for source_row, row in enumerate(
        values[header_index + 1 :],
        start=header_index + 2,
    ):
        item = {
            key: cell_text(row, columns, key)
            for key in HEADER_ALIASES
        }
        if not any(item.values()):
            continue
        item["source_row"] = source_row
        row_errors = []
        if not item["chinese_name"] and not item["english_name"]:
            row_errors.append("中文姓名或英文姓名至少填寫一項")
        if not item["employee_no"]:
            row_errors.append("缺員工編號")
        else:
            employee_no_key = item["employee_no"].casefold()
            if employee_no_key in seen_employee_nos:
                row_errors.append("檔案內員工編號重複")
            elif employee_no_key in existing_employee_nos:
                row_errors.append("員工編號已存在於系統")
            seen_employee_nos.add(employee_no_key)
        item["errors"] = row_errors
        rows.append(item)
    if not rows:
        errors.append("工作表沒有可匯入的員工資料。")
    return rows, errors


EMPLOYEE_TYPE_PREFIXES = (
    "ASMTP",
    "HKRD",
    "HKR",
    "MCR",
    "PRO",
    "BV",
    "LD",
    "TE",
)


def employee_type_for_number(employee_no):
    normalized = re.sub(r"[^A-Z0-9]", "", (employee_no or "").upper())
    for code in EMPLOYEE_TYPE_PREFIXES:
        if normalized.startswith(code):
            employee_type = employee_type_by_code(code)
            if employee_type:
                return employee_type
    return employee_type_by_code("OTHER")


def import_row(item):
    if Employee.query.filter_by(employee_no=item["employee_no"]).first():
        return "skipped", "員工編號已存在"
    employee = Employee(
        employee_no=item["employee_no"],
        status="active",
        employee_type=employee_type_for_number(item["employee_no"]),
        payroll_group="unassigned",
        mpf_mode="regular",
        chinese_name=item["chinese_name"] or None,
        english_name=item["english_name"] or None,
    )
    db.session.add(employee)
    db.session.flush()
    write_audit(
        "employee_imported",
        "Employee",
        employee.id,
        employee_id=employee.id,
        detail=f"XLSX 第 {item['source_row']} 行",
    )
    return "imported", ""


@admin_bp.route("/import/template")
@login_required
def download_import_template():
    require_admin()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "員工匯入"
    sheet.append(IMPORT_HEADERS)
    header_fill = PatternFill("solid", fgColor="176B62")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:C1000"
    for column, width in {
        "A": 14,
        "B": 20,
        "C": 28,
    }.items():
        sheet.column_dimensions[column].width = width

    notes = workbook.create_sheet("填寫說明")
    notes.append(["欄位", "填寫規則"])
    notes.append(["員工編號", "必填且不可與系統或本檔案其他行重複。"])
    notes.append(["中文姓名 / 英文姓名", "至少填寫其中一項。"])
    notes.append(
        [
            "用途",
            "此範本只建立最基本的員工檔案；其他資料由 HR 進入員工檔案後補充。",
        ]
    )
    for cell in notes[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
    notes.column_dimensions["A"].width = 24
    notes.column_dimensions["B"].width = 70
    notes.freeze_panes = "A2"

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="HKR_HR_員工初始化匯入範本.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


@admin_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_employees():
    require_admin()
    if request.method == "POST":
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename.lower().endswith(".xlsx"):
            flash("請上傳 XLSX 員工檔案。", "error")
        else:
            root = Path(current_app.config["IMPORT_ROOT"])
            root.mkdir(parents=True, exist_ok=True)
            batch_no = f"IMP{datetime.utcnow():%Y%m%d%H%M%S%f}"
            path = root / f"{batch_no}_{secure_filename(uploaded.filename)}"
            uploaded.save(path)
            try:
                rows, errors = parse_import_file(path)
            except (BadZipFile, InvalidFileException, OSError, ValueError):
                path.unlink(missing_ok=True)
                flash("XLSX 無法讀取，請使用官方匯入範本重新填寫。", "error")
                return redirect(url_for("admin.import_employees"))
            row_error_count = sum(bool(item.get("errors")) for item in rows)
            batch = ImportBatch(
                batch_no=batch_no,
                original_filename=uploaded.filename,
                status="preview",
                row_count=len(rows),
                result_json={
                    "stored_path": str(path),
                    "rows": rows,
                    "errors": errors,
                    "row_error_count": row_error_count,
                    "has_errors": bool(errors or row_error_count),
                    "validation_version": 3,
                },
                created_by=current_user.id,
            )
            db.session.add(batch)
            db.session.commit()
            flash("已建立匯入預覽；確認前不會寫入員工資料。", "success")
            return redirect(
                url_for("admin.import_employees", batch_id=batch.id)
            )
    batch_id = request.args.get("batch_id", type=int)
    batch = db.session.get(ImportBatch, batch_id) if batch_id else None
    history = (
        ImportBatch.query.order_by(ImportBatch.created_at.desc())
        .limit(15)
        .all()
    )
    return render_template(
        "admin/import.html",
        batch=batch,
        history=history,
    )


@admin_bp.route("/import/<int:batch_id>/confirm", methods=["POST"])
@login_required
def confirm_import(batch_id):
    require_admin()
    batch = db.get_or_404(ImportBatch, batch_id)
    if batch.status != "preview":
        flash("此批次已處理。", "error")
        return redirect(url_for("admin.import_employees", batch_id=batch.id))
    result = batch.result_json or {}
    if (
        result.get("validation_version") != 3
        or result.get("has_errors")
        or result.get("errors")
        or any(item.get("errors") for item in result.get("rows", []))
    ):
        flash("此預覽仍有錯誤，修正 XLSX 後重新上傳才可確認匯入。", "error")
        return redirect(url_for("admin.import_employees", batch_id=batch.id))
    imported = 0
    skipped = []
    for item in result.get("rows", []):
        status, reason = import_row(item)
        if status == "imported":
            imported += 1
        else:
            skipped.append(
                {
                    "source_row": item["source_row"],
                    "reason": reason,
                }
            )
    batch.status = "imported"
    batch.imported_count = imported
    result = dict(batch.result_json or {})
    result["skipped"] = skipped
    batch.result_json = result
    write_audit(
        "xlsx_import_confirmed",
        "ImportBatch",
        batch.id,
        detail=f"imported={imported}; skipped={len(skipped)}",
    )
    db.session.commit()
    flash(f"已匯入 {imported} 名員工；略過 {len(skipped)} 行。", "success")
    return redirect(url_for("admin.import_employees", batch_id=batch.id))


@admin_bp.route("/import/<int:batch_id>/discard", methods=["POST"])
@login_required
def discard_import(batch_id):
    require_admin()
    batch = db.get_or_404(ImportBatch, batch_id)
    if batch.status == "preview":
        stored_path = Path((batch.result_json or {}).get("stored_path", ""))
        root = Path(current_app.config["IMPORT_ROOT"]).resolve()
        try:
            resolved = stored_path.resolve()
            if resolved.is_relative_to(root) and resolved.is_file():
                resolved.unlink()
        except (OSError, ValueError):
            pass
        batch.status = "discarded"
        write_audit(
            "xlsx_import_discarded",
            "ImportBatch",
            batch.id,
            detail=batch.original_filename,
        )
        db.session.commit()
        flash("匯入預覽已捨棄，沒有寫入員工資料。", "success")
    return redirect(url_for("admin.import_employees"))
