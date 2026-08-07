from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, redirect, request, session, url_for


load_dotenv()

from config import Config
from models import db, login_manager
from routes.admin import admin_bp
from routes.attendance import attendance_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.documents import documents_bp
from routes.employees import employees_bp
from routes.exports import exports_bp
from routes.leave import leave_bp
from routes.payroll import payroll_bp
from routes.references import references_bp
from tools.hr_core import format_date, format_money
from tools.i18n import (
    LANGUAGE_OPTIONS,
    OPTION_TRANSLATION_KEYS,
    TRANSLATIONS,
    normalize_language,
    translate_system_message,
)
from tools.releases import CURRENT_VERSION


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

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
    app.register_blueprint(payroll_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(references_bp)
    app.register_blueprint(admin_bp)

    @app.before_request
    def capture_language():
        language = request.args.get("lang")
        if language:
            session["lang"] = normalize_language(language)

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

        return {
            "t": t,
            "active_lang": language,
            "languages": LANGUAGE_OPTIONS,
            "lang_url": lang_url,
            "option_t": option_t,
            "message_t": message_t,
            "project_t": project_t,
            "fmt_money": format_money,
            "fmt_date": format_date,
            "current_version": CURRENT_VERSION,
        }

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.dashboard"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
