"""Tests for PgConnector using SQLite in-memory (SQLAlchemy is DB-agnostic)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from src.backend.connectors.pg_connector import PgConnector
from src.schemas.payments import RawTransaction


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine — no file I/O, no cleanup needed."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE raw_transactions (
                transaction_id TEXT PRIMARY KEY,
                merchant_id TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                failure_reason TEXT,
                txn_date DATE NOT NULL
            )
        """))
        conn.commit()
    return engine


@pytest.fixture
def seeded_sqlite_engine(sqlite_engine):
    """SQLite engine with test data already inserted."""
    with sqlite_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO raw_transactions
            (transaction_id, merchant_id, amount, status, failure_reason, txn_date)
            VALUES
            ('TXN-001', 'MERCH-A', 150.00, 'SUCCESS', NULL, '2025-01-15'),
            ('TXN-002', 'MERCH-A', 75.50, 'FAILED', 'INSUFFICIENT_FUNDS', '2025-01-15'),
            ('TXN-003', 'MERCH-B', 200.00, 'SUCCESS', NULL, '2025-01-15')
        """))
        conn.commit()
    return sqlite_engine


class TestPgConnector:

    def test_implements_dataconnector_protocol(self, sqlite_engine):
        from src.backend.connectors.protocol import DataConnector

        connector = PgConnector(sqlite_engine)
        assert isinstance(connector, DataConnector)

    def test_query_validated_returns_typed_objects(self, seeded_sqlite_engine):
        connector = PgConnector(seeded_sqlite_engine)
        results = connector.query_validated(
            sql="SELECT * FROM raw_transactions",
            schema=RawTransaction,
        )
        assert len(results) == 3
        assert all(isinstance(r, RawTransaction) for r in results)

    def test_query_with_filter(self, seeded_sqlite_engine):
        connector = PgConnector(seeded_sqlite_engine)
        results = connector.query_validated(
            sql="SELECT * FROM raw_transactions WHERE merchant_id = 'MERCH-A'",
            schema=RawTransaction,
        )
        assert len(results) == 2
        assert all(r.merchant_id == "MERCH-A" for r in results)

    def test_invalid_rows_are_quarantined(self, sqlite_engine):
        with sqlite_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO raw_transactions
                (transaction_id, merchant_id, amount, status, failure_reason, txn_date)
                VALUES
                ('TXN-GOOD', 'MERCH-A', 100.00, 'SUCCESS', NULL, '2025-01-15'),
                ('TXN-BAD', 'MERCH-B', -50.00, 'SUCCESS', NULL, '2025-01-15')
            """))
            conn.commit()

        connector = PgConnector(sqlite_engine)
        results = connector.query_validated(
            sql="SELECT * FROM raw_transactions",
            schema=RawTransaction,
        )
        assert len(results) == 1
        assert results[0].transaction_id == "TXN-GOOD"

    def test_failed_transaction_without_reason_quarantined(self, sqlite_engine):
        """FAILED status without failure_reason violates cross-field rule."""
        with sqlite_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO raw_transactions
                (transaction_id, merchant_id, amount, status, failure_reason, txn_date)
                VALUES
                ('TXN-001', 'MERCH-A', 100.00, 'FAILED', NULL, '2025-01-15')
            """))
            conn.commit()

        connector = PgConnector(sqlite_engine)
        results = connector.query_validated(
            sql="SELECT * FROM raw_transactions",
            schema=RawTransaction,
        )
        assert results == []

    def test_empty_result_set(self, sqlite_engine):
        connector = PgConnector(sqlite_engine)
        results = connector.query_validated(
            sql="SELECT * FROM raw_transactions WHERE 1=0",
            schema=RawTransaction,
        )
        assert results == []
