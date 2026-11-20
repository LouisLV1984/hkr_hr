import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
load_dotenv(PROJECT_DIR / ".env")

from app import create_app
from hkr_hr.platform.db import User, db
from hkr_hr.references.api import ensure_reference_seed
from hkr_hr.workbench.api import ensure_schema, reset_postgres_schema


def main():
    parser = argparse.ArgumentParser(description="Initialize HKR HR database.")
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--role", default=os.getenv("ADMIN_ROLE", "admin"))
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Destructively recreate the HKR HR schema.",
    )
    parser.add_argument(
        "--confirm-reset",
        default="",
        help="Required with --reset; must be exactly hkr_hr_db.",
    )
    args = parser.parse_args()
    if not args.password:
        parser.error("--password or ADMIN_PASSWORD is required.")

    app = create_app()
    database_name = make_url(app.config["SQLALCHEMY_DATABASE_URI"]).database
    if database_name != "hkr_hr_db":
        raise RuntimeError(
            f"Refusing to initialize non-HR database: {database_name!r}."
        )

    with app.app_context():
        if args.reset:
            if args.confirm_reset != "hkr_hr_db":
                raise RuntimeError(
                    "--reset requires --confirm-reset hkr_hr_db."
                )
            reset_postgres_schema("hkr_hr_db")
        ensure_schema()
        ensure_reference_seed()
        user = User.query.filter_by(username=args.username).first()
        if not user:
            user = User(username=args.username, role=args.role, active=True)
            db.session.add(user)
            result = "created"
        else:
            user.role = args.role
            user.active = True
            result = "updated"
        user.set_password(args.password)
        db.session.commit()
        print(f"Database initialized. Admin user {result}: {args.username}")


if __name__ == "__main__":
    main()
