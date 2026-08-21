import argparse
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from sqlalchemy.engine import make_url


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
load_dotenv(PROJECT_DIR / ".env")

from app import create_app
from models import User, db
from tools.hr_core import ensure_reference_seed
from tools.schema_migrations import (
    apply_additive_migrations,
    ensure_schema,
    format_schema_issues,
    reset_postgres_schema,
    schema_compatibility_issues,
)


INCOMPATIBLE_SCHEMA_EXIT = 20


def psycopg_url_from_sqlalchemy(url_text, database):
    url = make_url(url_text)
    driverless = url.set(drivername="postgresql", database=database)
    return driverless.render_as_string(hide_password=False)


def ensure_database(database_url, database_name):
    maintenance_url = psycopg_url_from_sqlalchemy(database_url, "postgres")
    with psycopg.connect(maintenance_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select 1 from pg_database where datname = %s",
                (database_name,),
            )
            if cur.fetchone() is not None:
                print(f"Database already exists: {database_name}")
                return
            cur.execute(sql.SQL("create database {}").format(sql.Identifier(database_name)))
            print(f"Database created: {database_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap HKR HR production database."
    )
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--role", default=os.getenv("ADMIN_ROLE", "admin"))
    parser.add_argument("--reset-admin-password", action="store_true")
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

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")
    database_name = make_url(database_url).database
    if database_name != "hkr_hr_db":
        raise RuntimeError(
            f"Refusing to bootstrap non-HR database: {database_name!r}."
        )

    ensure_database(database_url, database_name)
    app = create_app()
    with app.app_context():
        if args.reset:
            if args.confirm_reset != "hkr_hr_db":
                raise RuntimeError(
                    "--reset requires --confirm-reset hkr_hr_db."
                )
            reset_postgres_schema("hkr_hr_db")
        else:
            added_columns = apply_additive_migrations()
            if added_columns:
                print(
                    "Applied non-destructive HKR HR schema upgrade: "
                    + ", ".join(added_columns)
                )
            issues = schema_compatibility_issues()
            if issues:
                print("")
                print("HKR HR V1 database upgrade is required.")
                print(
                    "The existing test schema is missing columns: "
                    + format_schema_issues(issues)
                )
                print(
                    "Run D:\\HKR_HR\\scripts\\"
                    "mini_pc_upgrade_hkr_hr_v1_and_restart.bat once."
                )
                print(
                    "The upgrade file requires an explicit RESET "
                    "confirmation and rebuilds only hkr_hr_db."
                )
                return INCOMPATIBLE_SCHEMA_EXIT
        repair_results = ensure_schema()
        repaired_special_days = repair_results.get(
            "legacy_special_day_summaries",
            0,
        )
        if repaired_special_days:
            print(
                "Repaired legacy inferred Sunday/statutory-holiday "
                f"attendance summaries: {repaired_special_days}"
            )
        ensure_reference_seed()
        user = User.query.filter_by(username=args.username).first()
        password_required = user is None or args.reset_admin_password
        if password_required and not args.password:
            raise RuntimeError(
                "ADMIN_PASSWORD or --password is required when creating or "
                "resetting the admin account."
            )
        if user is None:
            user = User(username=args.username, role=args.role, active=True)
            db.session.add(user)
            result = "created"
            user.set_password(args.password)
        else:
            user.role = args.role
            user.active = True
            result = "already exists"
            if args.reset_admin_password:
                user.set_password(args.password)
                result = "updated and password reset"
        db.session.commit()
        print(f"Tables are ready in hkr_hr_db. Admin user {result}: {args.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
