"""Local PostgreSQL runner — injects PgConnector into the dashboard.

Usage::

    streamlit run run_local_pg.py
    make run-pg

Prerequisites: ``make db-init && make db-seed``
"""
from __future__ import annotations

import os
import sys
from datetime import date

from sqlalchemy import create_engine, text

from src.backend.connectors.pg_connector import PgConnector
from src.frontend import app

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql:///cardstream?host=/tmp/cardstream-pg&port=5433",
)


def main() -> None:
    """Connect to PostgreSQL, patch the query builder, and launch the app."""
    print(f"Connecting to PostgreSQL: {DATABASE_URL}")

    try:
        engine = create_engine(DATABASE_URL, echo=False)

        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM raw_transactions")
            ).scalar()
            print(f"Found {count} transactions in database")

        pg_connector = PgConnector(engine)

        original_build_query = app.build_query

        def pg_build_query(
            date_from: date,
            table_name: str = "raw_transactions",
        ) -> str:
            """Redirect queries to the local PostgreSQL table name."""
            return original_build_query(date_from, table_name)

        app.build_query = pg_build_query

        app.main(connector=pg_connector)

    except Exception as exc:
        print(f"Failed to connect to PostgreSQL: {exc}")
        print()
        print("Make sure:")
        print("  1. PostgreSQL is running: make db-start")
        print("  2. Database is initialized: make db-init")
        print("  3. Data is seeded: make db-seed")
        print(f"  4. DATABASE_URL is correct: {DATABASE_URL}")
        sys.exit(1)


if __name__ == "__main__":
    main()
else:
    main()
