"""Composition root: assembles all 8 HKR HR modules into the Flask WSGI app."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from jinja2 import ChoiceLoader, FileSystemLoader

load_dotenv()

# Ensure all ORM models and trilingual word catalogues are registered once.
import hkr_hr.app.models as _registered_models  # noqa: F401
import hkr_hr.app.words as _registered_words  # noqa: F401

from hkr_hr.attendance import manifest as attendance_manifest
from hkr_hr.attendance.api import (
    leave_context_text,
    profile_revision,
    saved_leave_days,
)
from hkr_hr.documents import manifest as documents_manifest
from hkr_hr.employees import manifest as employees_manifest
from hkr_hr.leave import manifest as leave_manifest
from hkr_hr.leave.api import leave_date_label, rollover as annual_leave_rollover_service
from hkr_hr.payroll import manifest as payroll_manifest
from hkr_hr.payroll.api import hkd_summary
from hkr_hr.platform import manifest as platform_manifest
from hkr_hr.platform.config import BASE_DIR, Config
from hkr_hr.platform.dates import (
    attendance_period_bounds,
    current_month,
    format_date,
    format_money,
    parse_year_month,
)
from hkr_hr.platform.db import db, login_manager
from hkr_hr.platform.i18n import (
    LANGUAGE_OPTIONS,
    OPTION_TRANSLATION_KEYS,
    TRANSLATIONS,
    normalize_language,
    translate_system_message,
)
from hkr_hr.platform.security import (
    UploadValidationError,
    document_file_issue,
    get_csrf_token,
    protect_csrf,
)
from hkr_hr.references import manifest as references_manifest
from hkr_hr.workbench import manifest as workbench_manifest
from hkr_hr.workbench.api import CURRENT_VERSION


MODULE_MANIFESTS = (
    platform_manifest,
    references_manifest,
    employees_manifest,
    documents_manifest,
    attendance_manifest,
    leave_manifest,
    payroll_manifest,
    workbench_manifest,
)

WEAK_PRODUCTION_SECRETS = {
    "",
    "dev-change-me",
    "change-me-before-production",
}


def create_app(config_overrides=None):
    app = Flask(
        "hkr_hr",
        root_path=str(BASE_DIR),
        static_folder=str(BASE_DIR / "static"),
    )
    template_dirs = [
        str(m.TEMPLATE_DIR)
        for m in MODULE_MANIFESTS
        if getattr(m, "TEMPLATE_DIR", None) and Path(m.TEMPLATE_DIR).is_dir()
    ]
    app.jinja_loader = ChoiceLoader([FileSystemLoader(d) for d in template_dirs])

    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    if (
        app.config.get("HKR_HR_ENV") == "production"
        and app.config.get("SECRET_KEY") in WEAK_PRODUCTION_SECRETS
    ):
        raise RuntimeError(
            "Production SECRET_KEY is missing or still uses a placeholder."
        )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = TRANSLATIONS["zh-Hant"]["auth.login_required"]

    for manifest in MODULE_MANIFESTS:
        for bp in getattr(manifest, "BLUEPRINTS", ()):
            app.register_blueprint(bp)

    @app.after_request
    def profile_editor_response(response):
        # Enhanced employee editors retain their DOM (including selected files)
        # after validation errors. Native submissions and unrelated flows are unchanged.
        if (
            request.method == "POST"
            and request.headers.get("X-HKR-Profile-Editor") == "1"
            and request.blueprint in {"employees", "documents", "leave", "attendance", "payroll"}
            and response.status_code in {302, 303}
        ):
            flashes = session.get("_flashes", [])
            errors = [message for category, message in flashes if category in {"error", "danger"}]
            if errors and current_user.is_authenticated:
                session["_flashes"] = [
                    (category, message)
                    for category, message in flashes
                    if category not in {"error", "danger"}
                ]
                translations = TRANSLATIONS[normalize_language(session.get("lang"))]

                def localize(key, **values):
                    return translations.get(key, key).format(**values)

                response = jsonify(
                    errors=[translate_system_message(message, localize) for message in errors]
                )
                response.status_code = 422
            else:
                response = jsonify(redirect=response.location)
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.before_request
    def capture_language():
        language = request.args.get("lang")
        if language:
            session["lang"] = normalize_language(language)

    @app.before_request
    def verify_csrf():
        if app.config.get("CSRF_ENABLED", True):
            protect_csrf()

    @app.before_request
    def annual_leave_rollover():
        if current_user.is_authenticated and request.endpoint != "static" and request.method == "GET":
            annual_leave_rollover_service()

    @app.before_request
    def record_recent_user_activity():
        if not current_user.is_authenticated or request.endpoint == "static":
            return
        now = datetime.utcnow()
        if (
            current_user.last_seen_at is None
            or now - current_user.last_seen_at >= timedelta(minutes=2)
        ):
            current_user.last_seen_at = now
            db.session.commit()

    @app.before_request
    def validate_calendar_inputs():
        for values in (request.args, request.form):
            for key in ("month", "year_month"):
                for value in values.getlist(key):
                    if not value:
                        continue
                    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value) or not 2 <= int(value[:4]) <= 9998:
                        abort(400, description="security.invalid_period")
            for value in values.getlist("year"):
                if value and (not re.fullmatch(r"\d{4}", value) or not 2 <= int(value) <= 9998):
                    abort(400, description="security.invalid_period")

    @app.context_processor
    def inject_ui_helpers():
        language = normalize_language(session.get("lang"))
        messages = TRANSLATIONS[language]

        def t(key, **values):
            text = (
                messages.get(key)
                or TRANSLATIONS["zh-Hant"].get(key)
                or TRANSLATIONS["en"].get(key)
                or key
            )
            return text.format(**values) if values else text

        def lang_url(code):
            args = request.args.to_dict(flat=True)
            args["lang"] = code
            query = urlencode(args)
            return f"{request.path}?{query}" if query else request.path

        def option_t(group, code, fallback=None):
            key = OPTION_TRANSLATION_KEYS.get(group, {}).get(code)
            return t(key) if key else (fallback if fallback is not None else code)

        def message_t(value):
            return translate_system_message(value, t)

        def project_t(project, fallback=None):
            if project and getattr(project, "code", None) == "UNASSIGNED":
                return t("common.unassigned")
            if project:
                return project.name
            return fallback if fallback is not None else t("common.not_set")

        def month_t(year_month):
            start, _ = parse_year_month(year_month)
            return t("common.year_month", year=start.year, month=start.month)

        def attendance_period_t(year_month, period_kind):
            start, end = attendance_period_bounds(year_month)[period_kind]
            suffix_key = {
                "current_1_20": "attendance.period_actual_suffix",
                "current_21_end_forecast": "attendance.period_forecast_suffix",
                "previous_21_end": "attendance.period_actual_suffix",
                "previous_21_end_forecast": "attendance.period_original_forecast_suffix",
            }[period_kind]
            return t(
                "attendance.period_date_range",
                year=start.year,
                month=start.month,
                start=start.day,
                end=end.day,
                suffix=t(suffix_key),
            )

        return {
            "leave_context_text": lambda employee: leave_context_text(employee, language=language),
            "leave_date_label": lambda record: leave_date_label(record, t),
            "leave_days_match": lambda record: record.days == saved_leave_days(record),
            "t": t,
            "hkd_summary": hkd_summary,
            "active_lang": language,
            "languages": LANGUAGE_OPTIONS,
            "lang_url": lang_url,
            "option_t": option_t,
            "message_t": message_t,
            "project_t": project_t,
            "month_t": month_t,
            "attendance_period_t": attendance_period_t,
            "fmt_money": format_money,
            "fmt_date": format_date,
            "current_version": CURRENT_VERSION,
            "operating_month": session.get("operating_month") or current_month(),
            "csrf_token": get_csrf_token,
            "profile_revision": profile_revision,
            "document_file_issue": document_file_issue,
        }

    def render_http_error(error, status_code):
        detail_key = (
            str(error)
            if isinstance(error, UploadValidationError)
            else getattr(error, "description", "")
        )
        if not isinstance(detail_key, str) or not (
            detail_key.startswith("security.") or detail_key.startswith("upload.")
        ):
            detail_key = f"error.{status_code}.message"
        return (
            render_template(
                "errors/error.html",
                status_code=status_code,
                title_key=f"error.{status_code}.title",
                detail_key=detail_key,
            ),
            status_code,
        )

    @app.errorhandler(400)
    def bad_request(error):
        return render_http_error(error, 400)

    @app.errorhandler(403)
    def forbidden(error):
        return render_http_error(error, 403)

    @app.errorhandler(404)
    def not_found(error):
        return render_http_error(error, 404)

    @app.errorhandler(413)
    def too_large(error):
        return render_http_error(error, 413)

    @app.errorhandler(UploadValidationError)
    def invalid_upload(error):
        return render_http_error(error, 400)

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error("Unhandled HKR HR request error", exc_info=True)
        return render_http_error(error, 500)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.dashboard"))

    return app
