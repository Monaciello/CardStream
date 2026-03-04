"""Tests for the Streamlit dashboard rendering."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.schemas.payments import RawTransaction


def _make_mock_session(df: pd.DataFrame) -> MagicMock:
    session = MagicMock()
    session.sql.return_value.to_pandas.return_value = df
    return session


def _validated_rows(df: pd.DataFrame) -> list[RawTransaction]:
    rows: list[RawTransaction] = []
    for record in df.to_dict(orient="records"):
        try:
            rows.append(RawTransaction(**record))
        except Exception:
            pass
    return rows


def _healthy_dataframe() -> pd.DataFrame:
    """Multi-day data so risk analytics tab has enough for profile computation."""
    rows = []
    txn_id = 1
    for day in range(5):
        for merchant in ("MERCH-A", "MERCH-B"):
            for _ in range(4):
                rows.append({
                    "transaction_id": f"TXN-{txn_id:04d}",
                    "merchant_id": merchant,
                    "amount": 150.00,
                    "status": "SUCCESS",
                    "failure_reason": None,
                    "txn_date": date(2025, 1, 15 + day),
                })
                txn_id += 1
    return pd.DataFrame(rows)


def _critical_dataframe() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "transaction_id": f"TXN-F{i}", "merchant_id": "MERCH-BAD",
            "amount": 100.00, "status": "FAILED",
            "failure_reason": "TIMEOUT", "txn_date": date(2025, 1, 15),
        }
        for i in range(5)
    ])


def _run_app(df: pd.DataFrame) -> AppTest:
    """Patch Snowflake session + query_validated, then run the app."""
    mock_session = _make_mock_session(df)
    valid_rows = _validated_rows(df)

    with patch(
        "snowflake.snowpark.context.get_active_session",
        return_value=mock_session,
    ), patch(
        "src.backend.connectors.sis_connector.SiSConnector.query_validated",
        return_value=valid_rows,
    ):
        at = AppTest.from_file("src/frontend/app.py", default_timeout=10)
        at.run()

    return at


class TestDashboardRenders:

    def test_app_runs_without_exception(self):
        at = _run_app(_healthy_dataframe())
        assert not at.exception, f"App raised: {at.exception}"

    def test_title_is_present(self):
        at = _run_app(_healthy_dataframe())
        assert any("Payments" in t.value for t in at.title)

    def test_metric_cards_rendered(self):
        at = _run_app(_healthy_dataframe())
        assert len(at.metric) >= 4

    def test_ok_state_renders_success_banner(self):
        at = _run_app(_healthy_dataframe())
        assert not at.exception
        assert len(at.success) >= 1

    def test_critical_state_renders_error_banner(self):
        at = _run_app(_critical_dataframe())
        assert not at.exception
        assert len(at.error) >= 1

    def test_empty_data_does_not_crash(self):
        empty_df = pd.DataFrame(columns=[
            "transaction_id", "merchant_id", "amount",
            "status", "failure_reason", "txn_date",
        ])
        at = _run_app(empty_df)
        assert not at.exception
