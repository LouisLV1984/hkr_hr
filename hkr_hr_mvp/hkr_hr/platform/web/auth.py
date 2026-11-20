"""Platform authentication blueprint."""
from __future__ import annotations

from datetime import datetime
from math import ceil

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from hkr_hr.platform.audit import write_audit
from hkr_hr.platform.db import User, db
from hkr_hr.platform.security import login_rate_limiter, safe_next_url


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        retry_after = login_rate_limiter.retry_after(
            username,
            request.remote_addr,
        )
        if retry_after:
            flash(
                f"security.login_limited|minutes={ceil(retry_after / 60)}",
                "error",
            )
            return render_template("auth/login.html"), 429
        account = User.query.filter_by(username=username).first()
        user = account if account and account.active else None
        if user and user.check_password(password):
            login_rate_limiter.clear(username, request.remote_addr)
            login_user(user)
            now = datetime.utcnow()
            user.last_login_at = now
            user.last_seen_at = now
            write_audit(
                "auth_login_success",
                "User",
                user.id,
                detail=user.username,
                user_id=user.id,
            )
            db.session.commit()
            return redirect(
                safe_next_url(
                    request.args.get("next"),
                    url_for("dashboard.dashboard"),
                )
            )
        login_rate_limiter.record_failure(username, request.remote_addr)
        write_audit(
            "auth_login_failed",
            "User",
            account.id if account else None,
            detail=username or "-",
            user_id=account.id if account else None,
        )
        db.session.commit()
        flash("登入資料不正確。", "error")
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    now = datetime.utcnow()
    current_user.last_seen_at = now
    current_user.last_logout_at = now
    write_audit(
        "auth_logout",
        "User",
        current_user.id,
        detail=current_user.username,
    )
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))
