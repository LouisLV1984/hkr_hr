from datetime import datetime, timedelta
from pathlib import Path
import re
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from jinja2 import ChoiceLoader, FileSystemLoader


load_dotenv()

from hkr_hr.platform.config import Config
from hkr_hr.platform.manifest import TEMPLATE_DIR as PLATFORM_TEMPLATES
from hkr_hr.references.manifest import TEMPLATE_DIR as REFERENCES_TEMPLATES
from hkr_hr.employees.manifest import TEMPLATE_DIR as EMPLOYEES_TEMPLATES
from hkr_hr.documents.manifest import TEMPLATE_DIR as DOCUMENTS_TEMPLATES
from tools.payroll_exchange import hkd_summary
from models import db, login_manager
from routes.admin import admin_bp
from routes.attendance import attendance_bp
from routes.attendance_corrections import bp as attendance_corrections_bp
from hkr_hr.platform.web.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.documents import documents_bp
from routes.employees import employees_bp
from routes.exports import exports_bp
from routes.leave import leave_bp
from routes.payroll import payroll_bp
from routes.salary_records import salary_records_bp
from routes.references import references_bp
from tools.hr_core import (
    attendance_period_bounds,
    current_month,
    format_date,
    format_money,
    parse_year_month,
)
from tools.i18n import (
    LANGUAGE_OPTIONS,
    OPTION_TRANSLATION_KEYS,
    TRANSLATIONS,
    normalize_language,
    translate_system_message,
)
from tools.releases import CURRENT_VERSION
from tools.security import UploadValidationError, get_csrf_token, protect_csrf, document_file_issue
from tools.profile_revision import profile_revision


WEAK_PRODUCTION_SECRETS = {
    "",
    "dev-change-me",
    "change-me-before-production",
}


def create_app(config_overrides=None):
    app = Flask(__name__)
    template_dirs = [
        str(d)
        for d in (
            PLATFORM_TEMPLATES,
            REFERENCES_TEMPLATES,
            EMPLOYEES_TEMPLATES,
            DOCUMENTS_TEMPLATES,
            Path(__file__).resolve().parent / "templates",
        )
        if Path(d).is_dir()
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(attendance_corrections_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(salary_records_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(references_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def profile_editor_response(response):
        # Enhanced employee editors retain their DOM (including selected files)
        # after validation errors. Native submissions and unrelated flows are unchanged.
        if (request.method == "POST" and request.headers.get("X-HKR-Profile-Editor") == "1"
                and request.blueprint in {"employees", "documents", "leave", "attendance", "payroll"}
                and response.status_code in {302, 303}):
            flashes = session.get("_flashes", [])
            errors = [message for category, message in flashes if category in {"error", "danger"}]
            if errors and current_user.is_authenticated:
                session["_flashes"] = [(category, message) for category, message in flashes
                                      if category not in {"error", "danger"}]
                translations = TRANSLATIONS[normalize_language(session.get("lang"))]
                def localize(key, **values):
                    return translations.get(key, key).format(**values)
                response = jsonify(errors=[translate_system_message(message, localize) for message in errors])
                response.status_code = 422
            else:
                # Let the eventual GET consume success/warning flashes exactly once.
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
            from tools.annual_leave_policy import rollover
            rollover()

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
        # Reject boundary years before previous-month/year calculations run.
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

        from tools.absence_integrity import leave_date_label
        from tools.attendance_policy import saved_leave_days, leave_context_text
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
            detail_key.startswith("security.")
            or detail_key.startswith("upload.")
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


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
