"""Tests for the pipeline orchestrator."""
from __future__ import annotations

from datetime import date
from typing import Type, TypeVar

import pandas as pd
import pytest

from src.backend.transforms.alert_models import AlertConfig, AlertSeverity
from src.backend.transforms.pipeline import PipelineResult, run_pipeline
from src.schemas.payments import MerchantRiskProfile, RawTransaction, TransactionSummary

T = TypeVar("T")


class MockConnector:
    """Minimal DataConnector that returns pre-built rows."""

    def __init__(self, rows: list[RawTransaction]) -> None:
        self._rows = rows

    def query_validated(self, sql: str, schema: Type[T]) -> list[T]:
        return self._rows  # type: ignore[return-value]


@pytest.fixture
def default_config() -> AlertConfig:
    return AlertConfig(
        warning_threshold=0.20,
        critical_threshold=0.40,
        min_transaction_count=5,
    )


@pytest.fixture
def healthy_rows() -> list[RawTransaction]:
    return [
        RawTransaction(
            transaction_id=f"TXN-{i:03d}",
            merchant_id="MERCH-A",
            amount=100.0,
            status="SUCCESS",
            failure_reason=None,
            txn_date=date(2025, 1, 15),
        )
        for i in range(10)
    ]


@pytest.fixture
def mixed_rows() -> list[RawTransaction]:
    """10 rows: 6 SUCCESS + 4 FAILED = 40% failure rate."""
    rows = [
        RawTransaction(
            transaction_id=f"TXN-S{i}",
            merchant_id="MERCH-A",
            amount=100.0,
            status="SUCCESS",
            failure_reason=None,
            txn_date=date(2025, 1, 15),
        )
        for i in range(6)
    ] + [
        RawTransaction(
            transaction_id=f"TXN-F{i}",
            merchant_id="MERCH-A",
            amount=50.0,
            status="FAILED",
            failure_reason="TIMEOUT",
            txn_date=date(2025, 1, 15),
        )
        for i in range(4)
    ]
    return rows


class TestRunPipeline:

    def test_returns_pipeline_result(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        assert isinstance(result, PipelineResult)

    def test_raw_transactions_passed_through(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        assert result.raw_transactions == healthy_rows

    def test_summaries_are_transaction_summaries(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        assert len(result.summaries) > 0
        assert all(isinstance(s, TransactionSummary) for s in result.summaries)

    def test_summary_df_is_dataframe(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        assert isinstance(result.summary_df, pd.DataFrame)
        assert len(result.summary_df) == len(result.summaries)

    def test_healthy_data_produces_ok_alert(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        assert result.alert.severity == AlertSeverity.OK

    def test_high_failure_rate_produces_critical(self, mixed_rows, default_config):
        result = run_pipeline(MockConnector(mixed_rows), "SELECT 1", default_config)
        assert result.alert.severity == AlertSeverity.CRITICAL

    def test_risk_profiles_populated(self, default_config):
        rows = []
        for day in range(5):
            for i in range(10):
                rows.append(RawTransaction(
                    transaction_id=f"TXN-{day}-{i}",
                    merchant_id="MERCH-A",
                    amount=100.0,
                    status="SUCCESS" if i < 8 else "FAILED",
                    failure_reason="TIMEOUT" if i >= 8 else None,
                    txn_date=date(2025, 1, 15 + day),
                ))
        result = run_pipeline(MockConnector(rows), "SELECT 1", default_config)
        assert isinstance(result.risk_profiles, list)
        assert all(isinstance(p, MerchantRiskProfile) for p in result.risk_profiles)

    def test_rolling_df_populated(self, default_config):
        rows = []
        for day in range(5):
            for i in range(10):
                rows.append(RawTransaction(
                    transaction_id=f"TXN-{day}-{i}",
                    merchant_id="MERCH-A",
                    amount=100.0,
                    status="SUCCESS",
                    failure_reason=None,
                    txn_date=date(2025, 1, 15 + day),
                ))
        result = run_pipeline(MockConnector(rows), "SELECT 1", default_config)
        assert isinstance(result.rolling_df, pd.DataFrame)
        assert not result.rolling_df.empty

    def test_empty_input_returns_empty_summaries(self, default_config):
        result = run_pipeline(MockConnector([]), "SELECT 1", default_config)
        assert result.raw_transactions == []
        assert result.summaries == []
        assert result.summary_df.empty
        assert result.alert.severity == AlertSeverity.OK
        assert result.risk_profiles == []
        assert result.rolling_df.empty

    def test_multi_merchant_produces_separate_summaries(self, default_config):
        rows = [
            RawTransaction(
                transaction_id=f"TXN-A{i}", merchant_id="MERCH-A",
                amount=100.0, status="SUCCESS", failure_reason=None,
                txn_date=date(2025, 1, 15),
            )
            for i in range(5)
        ] + [
            RawTransaction(
                transaction_id=f"TXN-B{i}", merchant_id="MERCH-B",
                amount=200.0, status="SUCCESS", failure_reason=None,
                txn_date=date(2025, 1, 15),
            )
            for i in range(5)
        ]
        result = run_pipeline(MockConnector(rows), "SELECT 1", default_config)
        assert {s.merchant_id for s in result.summaries} == {"MERCH-A", "MERCH-B"}

    def test_summary_df_columns_match_model(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        expected = {"merchant_id", "txn_date", "total_volume", "txn_count", "failure_rate"}
        assert expected.issubset(set(result.summary_df.columns))


class TestPipelineResult:

    def test_slots_prevent_arbitrary_attributes(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        with pytest.raises(AttributeError):
            result.nonexistent = "should fail"  # type: ignore[attr-defined]

    def test_all_slots_accessible(self, healthy_rows, default_config):
        result = run_pipeline(MockConnector(healthy_rows), "SELECT 1", default_config)
        assert hasattr(result, "raw_transactions")
        assert hasattr(result, "summaries")
        assert hasattr(result, "summary_df")
        assert hasattr(result, "alert")
        assert hasattr(result, "risk_profiles")
        assert hasattr(result, "rolling_df")
