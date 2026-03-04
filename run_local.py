"""Local mock runner — generates fake data and patches the Snowflake session.

Usage::

    streamlit run run_local.py
    make run
"""
from __future__ import annotations

import random
import runpy
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

_MERCHANTS = [
    "MERCH-ALPHA", "MERCH-BETA", "MERCH-GAMMA",
    "MERCH-DELTA", "MERCH-EPSILON", "MERCH-ZETA",
    "MERCH-ETA", "MERCH-THETA", "MERCH-IOTA", "MERCH-KAPPA",
]

_FAILURE_REASONS = [
    "INSUFFICIENT_FUNDS", "TIMEOUT", "INVALID_ACCOUNT",
    "FRAUD_SUSPECTED", "NETWORK_ERROR",
]

_BASE_FAILURE_RATES: dict[str, float] = {
    "MERCH-ALPHA":   0.02,
    "MERCH-BETA":    0.05,
    "MERCH-GAMMA":   0.45,
    "MERCH-DELTA":   0.08,
    "MERCH-EPSILON": 0.25,
    "MERCH-ZETA":    0.01,
    "MERCH-ETA":     0.03,
    "MERCH-THETA":   0.12,
    "MERCH-IOTA":    0.07,
    "MERCH-KAPPA":   0.04,
}


def generate_mock_transactions(
    days: int = 30,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a deterministic DataFrame of mock payment transactions.

    Args:
        days: Number of trailing days to generate data for.
        seed: RNG seed for reproducibility.

    Returns:
        DataFrame with columns matching ``RawTransaction`` fields.
    """
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    txn_id = 1

    for day_offset in range(days):
        txn_date = date.today() - timedelta(days=day_offset)
        for merchant in _MERCHANTS:
            rate = _BASE_FAILURE_RATES.get(merchant, 0.05)
            for _ in range(rng.randint(8, 20)):
                status = "FAILED" if rng.random() < rate else "SUCCESS"
                rows.append({
                    "transaction_id": f"TXN-{txn_id:05d}",
                    "merchant_id":    merchant,
                    "amount":         round(rng.uniform(10, 5000), 2),
                    "status":         status,
                    "failure_reason": (
                        rng.choice(_FAILURE_REASONS) if status == "FAILED" else None
                    ),
                    "txn_date":       txn_date,
                })
                txn_id += 1

    return pd.DataFrame(rows)


def main() -> None:
    """Patch Snowflake session with mock data and launch the dashboard."""
    mock_df = generate_mock_transactions()

    mock_session = MagicMock()
    mock_session.sql.return_value.to_pandas.return_value = mock_df

    app_path = Path(__file__).parent / "src" / "frontend" / "app.py"

    with patch(
        "snowflake.snowpark.context.get_active_session",
        return_value=mock_session,
    ):
        runpy.run_path(str(app_path), run_name="__main__")


if __name__ == "__main__":
    main()
else:
    main()
