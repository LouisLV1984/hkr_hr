from datetime import datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_, text

from hkr_hr.platform.db import AuditLog, User, db
from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.dates import hong_kong_datetime
from hkr_hr.workbench.service.historical_audit import daily_injury_earnings_rows, replaced_attendance_rows, unlinked_renewal_rows
from hkr_hr.workbench.service.releases import CURRENT_VERSION


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ROLE_OPTIONS = [
    ("admin", "Admin / 系統管理員"),
    ("hr", "HR / 人事同事"),
]


def require_admin():
    if current_user.role != "admin":
        abort(403)


def clear_user_references(user_id):
    """Keep historical business rows while removing their login account."""
    for table in db.metadata.tables.values():
        if table.name == User.__tablename__:
            continue
        for column in table.columns:
            references_user = any(
                foreign_key.target_fullname == "users.id"
                for foreign_key in column.foreign_keys
            )
            if references_user:
                db.session.execute(
                    table.update()
                    .where(column == user_id)
                    .values({column.name: None})
                )


def application_root():
    app_root = Path(current_app.root_path).resolve()
    if app_root.parent.name.lower() == "_system":
        return app_root.parent.parent
    return app_root


def latest_log_status(pattern, success_marker):
    log_root = application_root() / "03.Output" / "logs"
    try:
        files = sorted(
            log_root.glob(pattern) if log_root.exists() else [],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return {"state": "unreadable", "checked_at": None, "filename": None}
    if not files:
        return {"state": "missing", "checked_at": None, "filename": None}
    latest = files[0]
    try:
        content = latest.read_text(encoding="utf-8", errors="replace")
        modified = latest.stat().st_mtime
    except OSError:
        return {"state": "unreadable", "checked_at": None, "filename": latest.name}
    state = "ok" if success_marker in content else "attention"
    if pattern == "restore_verify_*.log" and any(marker in content for marker in (
        "Restore verification passed.", "Archive listing and template extraction passed;",
        "Database restore and template extraction passed;",
    )):
        # Neither legacy success nor the current script proves attachment recovery.
        state = "partial"
    return {
        "state": state,
        "checked_at": hong_kong_datetime(
            datetime.utcfromtimestamp(modified)
        ),
        "filename": latest.name,
    }


def database_runtime_status():
    dialect = db.engine.dialect.name
    if dialect == "postgresql":
        row = db.session.execute(
            text(
                "SELECT current_database() AS database_name, "
                "current_setting('server_version') AS server_version"
            )
        ).mappings().one()
        return {
            "database_name": row["database_name"],
            "server_version": row["server_version"],
            "dialect": "PostgreSQL",
        }
    return {
        "database_name": "test / local",
        "server_version": getattr(db.engine.dialect, "server_version_info", None),
        "dialect": dialect,
    }


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
        elif action == "delete":
            user = db.session.get(User, request.form.get("user_id", type=int))
            if not user:
                abort(404)
            if user.id == current_user.id:
                flash("不能刪除目前登入的帳戶。", "error")
                return redirect(url_for("admin.users"))
            active_admin_count = User.query.filter_by(
                role="admin",
                active=True,
            ).count()
            if user.role == "admin" and user.active and active_admin_count <= 1:
                flash("不能刪除系統最後一個啟用中的 Admin 帳戶。", "error")
                return redirect(url_for("admin.users"))
            username = user.username
            user_id = user.id
            clear_user_references(user_id)
            db.session.delete(user)
            write_audit(
                "user_deleted",
                "User",
                user_id,
                detail=username,
                before={"username": username, "role": user.role},
            )
            db.session.commit()
            flash("用戶已刪除。", "success")
            return redirect(url_for("admin.users"))
    now = datetime.utcnow()
    user_rows = []
    for user in User.query.order_by(User.username.asc()).all():
        last_activity = max(
            (
                value
                for value in (
                    user.last_seen_at,
                    user.last_login_at,
                    user.last_logout_at,
                )
                if value is not None
            ),
            default=None,
        )
        has_open_session = bool(
            user.last_seen_at
            and (
                user.last_logout_at is None
                or user.last_seen_at > user.last_logout_at
            )
        )
        online = bool(
            user.active
            and has_open_session
            and last_activity
            and now - last_activity <= timedelta(minutes=15)
        )
        if online:
            activity_kind = "online"
            activity_value = None
        elif last_activity is None:
            activity_kind = "never"
            activity_value = None
        else:
            elapsed = max(now - last_activity, timedelta())
            if elapsed < timedelta(hours=1):
                activity_kind = "minutes"
                activity_value = max(1, int(elapsed.total_seconds() // 60))
            elif elapsed < timedelta(days=1):
                activity_kind = "hours"
                activity_value = max(1, int(elapsed.total_seconds() // 3600))
            elif elapsed < timedelta(days=7):
                activity_kind = "days"
                activity_value = max(1, elapsed.days)
            else:
                activity_kind = "date"
                activity_value = last_activity.strftime("%Y-%m-%d")
        user_rows.append(
            {
                "user": user,
                "online": online,
                "activity_kind": activity_kind,
                "activity_value": activity_value,
            }
        )
    return render_template(
        "admin/users.html",
        users=User.query.order_by(User.username.asc()).all(),
        user_rows=user_rows,
        roles=ROLE_OPTIONS,
    )


@admin_bp.route("/audit")
@login_required
def audit():
    require_admin()
    view = request.args.get("view", "activity")
    if view not in {"activity", "logins"}:
        view = "activity"
    username = request.args.get("username", "").strip()
    limit = request.args.get("limit", 50, type=int)
    limit = limit if limit in {20, 50, 100} else 50
    query = AuditLog.query.outerjoin(User, AuditLog.user_id == User.id)
    if view == "logins":
        query = query.filter(
            AuditLog.action.in_(
                {"auth_login_success", "auth_login_failed", "auth_logout"}
            )
        )
    if username:
        query = query.filter(
            or_(
                User.username.ilike(f"%{username}%"),
                AuditLog.detail.ilike(f"%{username}%"),
            )
        )
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    for log in logs:
        log.display_created_at = hong_kong_datetime(log.created_at)
    return render_template(
        "admin/audit.html",
        logs=logs,
        audit_view=view,
        audit_username=username,
        audit_limit=limit,
        usernames=[row.username for row in User.query.order_by(User.username)],
    )


@admin_bp.route("/historical-review")
@login_required
def historical_review():
    require_admin()
    replaced_rows = replaced_attendance_rows()
    injury_rows = daily_injury_earnings_rows()
    renewal_rows = unlinked_renewal_rows()
    return render_template(
        "admin/historical_review.html",
        replaced_rows=replaced_rows,
        replaced_diff_count=sum(
            1 for row in replaced_rows if row["different_file"] or row["figures_differ"]
        ),
        injury_rows=injury_rows,
        injury_suspect_count=sum(1 for row in injury_rows if row["suspect"]),
        renewal_rows=renewal_rows,
    )


@admin_bp.route("/system")
@login_required
def system_status():
    require_admin()
    return render_template(
        "admin/system.html",
        application_version=CURRENT_VERSION,
        environment=current_app.config.get("HKR_HR_ENV", "development"),
        database_status=database_runtime_status(),
        backup_status=latest_log_status(
            "backup_short_term_*.log",
            "Backup completed:",
        ),
        restore_status=latest_log_status(
            "restore_verify_*.log",
            "Restore verification passed.",
        ),
    )
