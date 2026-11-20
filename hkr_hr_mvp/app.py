"""Thin Waitress / CLI entrypoint delegating to ``hkr_hr.app.create_app``."""
from hkr_hr.app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
