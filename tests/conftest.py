"""Shared fixtures for the full test suite.

Golden record pattern: one canonical ``valid_transaction_data`` dict
lives here.  Every edge-case test takes this dict, changes ONE field,
and asserts the result.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def valid_transaction_data() -> dict[str, Any]:
    """Canonical SUCCESS transaction row."""
    return {
        "transaction_id": "TXN-001",
        "merchant_id":    "MERCH-A",
        "amount":         150.00,
        "status":         "SUCCESS",
        "failure_reason": None,
        "txn_date":       "2025-01-15",
    }


@pytest.fixture
def valid_failed_transaction_data() -> dict[str, Any]:
    """Canonical FAILED transaction row with a valid failure_reason."""
    return {
        "transaction_id": "TXN-002",
        "merchant_id":    "MERCH-A",
        "amount":         75.50,
        "status":         "FAILED",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "txn_date":       "2025-01-15",
    }


@pytest.fixture
def transaction_dataframe() -> pd.DataFrame:
    """Three rows, two merchants, one day.

    Expected aggregates::

        MERCH-A: volume=225.50, count=2, failure_rate=0.5
        MERCH-B: volume=200.00, count=1, failure_rate=0.0
    """
    return pd.DataFrame([
        {
            "transaction_id": "TXN-001",
            "merchant_id":    "MERCH-A",
            "amount":         150.00,
            "status":         "SUCCESS",
            "failure_reason": None,
            "txn_date":       "2025-01-15",
        },
        {
            "transaction_id": "TXN-002",
            "merchant_id":    "MERCH-A",
            "amount":         75.50,
            "status":         "FAILED",
            "failure_reason": "INSUFFICIENT_FUNDS",
            "txn_date":       "2025-01-15",
        },
        {
            "transaction_id": "TXN-003",
            "merchant_id":    "MERCH-B",
            "amount":         200.00,
            "status":         "SUCCESS",
            "failure_reason": None,
            "txn_date":       "2025-01-15",
        },
    ])


@pytest.fixture
def mock_session(transaction_dataframe: pd.DataFrame) -> MagicMock:
    """Snowpark session mock: ``session.sql(q).to_pandas()`` returns *transaction_dataframe*."""
    session = MagicMock()
    session.sql.return_value.to_pandas.return_value = transaction_dataframe
    return session
