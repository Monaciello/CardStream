"""Tests for transforms: daily_summary, to_dataframe, and alert logic."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.backend.transforms.alert_engine import check_success_rate_alert
from src.backend.transforms.alert_models import AlertConfig, AlertSeverity
from src.backend.transforms.daily_summary import compute_daily_summary, to_dataframe
from src.schemas.payments import TransactionSummary


class TestComputeDailySummary:

    def test_returns_list_of_transaction_summaries(self, transaction_dataframe):
        results = compute_daily_summary(transaction_dataframe)
        assert isinstance(results, list)
        assert all(isinstance(r, TransactionSummary) for r in results)

    def test_produces_one_row_per_merchant_per_day(self, transaction_dataframe):
        results = compute_daily_summary(transaction_dataframe)
        assert len(results) == 2

    def test_merchant_a_volume_is_correct(self, transaction_dataframe):
        results = compute_daily_summary(transaction_dataframe)
        merch_a = next(r for r in results if r.merchant_id == "MERCH-A")
        assert merch_a.total_volume == 225.50

    def test_merchant_a_failure_rate_is_fifty_percent(self, transaction_dataframe):
        """failure_rate = failures / total, NOT failures / successes."""
        results = compute_daily_summary(transaction_dataframe)
        merch_a = next(r for r in results if r.merchant_id == "MERCH-A")
        assert merch_a.failure_rate == 0.5

    def test_merchant_b_failure_rate_is_zero(self, transaction_dataframe):
        results = compute_daily_summary(transaction_dataframe)
        merch_b = next(r for r in results if r.merchant_id == "MERCH-B")
        assert merch_b.failure_rate == 0.0

    def test_merchant_b_volume_is_correct(self, transaction_dataframe):
        results = compute_daily_summary(transaction_dataframe)
        merch_b = next(r for r in results if r.merchant_id == "MERCH-B")
        assert merch_b.total_volume == 200.00

    def test_txn_count_is_correct(self, transaction_dataframe):
        results = compute_daily_summary(transaction_dataframe)
        merch_a = next(r for r in results if r.merchant_id == "MERCH-A")
        assert merch_a.txn_count == 2

    def test_all_failures_produces_rate_of_one(self):
        all_failed = pd.DataFrame([
            {
                "transaction_id": "TXN-F1",
                "merchant_id":    "MERCH-DOWN",
                "amount":         100.0,
                "status":         "FAILED",
                "failure_reason": "TIMEOUT",
                "txn_date":       "2025-01-15",
            },
            {
                "transaction_id": "TXN-F2",
                "merchant_id":    "MERCH-DOWN",
                "amount":         200.0,
                "status":         "FAILED",
                "failure_reason": "TIMEOUT",
                "txn_date":       "2025-01-15",
            },
        ])
        results = compute_daily_summary(all_failed)
        assert len(results) == 1
        assert results[0].failure_rate == 1.0

    def test_multi_day_produces_separate_rows(self):
        two_days = pd.DataFrame([
            {
                "transaction_id": "TXN-D1",
                "merchant_id":    "MERCH-A",
                "amount":         100.0,
                "status":         "SUCCESS",
                "failure_reason": None,
                "txn_date":       "2025-01-15",
            },
            {
                "transaction_id": "TXN-D2",
                "merchant_id":    "MERCH-A",
                "amount":         150.0,
                "status":         "SUCCESS",
                "failure_reason": None,
                "txn_date":       "2025-01-16",
            },
        ])
        results = compute_daily_summary(two_days)
        assert len(results) == 2

    def test_empty_dataframe_returns_empty_list(self):
        empty_df = pd.DataFrame(
            columns=["merchant_id", "txn_date", "amount", "status",
                     "failure_reason", "transaction_id"]
        )
        results = compute_daily_summary(empty_df)
        assert results == []


class TestToDataframe:

    def test_returns_dataframe(self, transaction_dataframe):
        summaries = compute_daily_summary(transaction_dataframe)
        df = to_dataframe(summaries)
        assert isinstance(df, pd.DataFrame)

    def test_columns_match_summary_fields(self, transaction_dataframe):
        summaries = compute_daily_summary(transaction_dataframe)
        df = to_dataframe(summaries)
        expected = {"merchant_id", "txn_date", "total_volume",
                    "txn_count", "failure_rate"}
        assert expected.issubset(set(df.columns))

    def test_row_count_matches_summary_count(self, transaction_dataframe):
        summaries = compute_daily_summary(transaction_dataframe)
        df = to_dataframe(summaries)
        assert len(df) == len(summaries)


@pytest.fixture
def default_config() -> AlertConfig:
    return AlertConfig(
        warning_threshold     = 0.20,
        critical_threshold    = 0.40,
        min_transaction_count = 5,
    )


@pytest.fixture
def summary_factory():
    def _make(merchant_id="MERCH-A", failure_rate=0.0, txn_count=10):
        return TransactionSummary(
            merchant_id  = merchant_id,
            txn_date     = date(2025, 1, 15),
            total_volume = 1000.0,
            txn_count    = txn_count,
            failure_rate = failure_rate,
        )
    return _make


class TestAlertLogic:

    def test_all_ok_returns_ok_severity(self, default_config, summary_factory):
        summaries = [
            summary_factory("MERCH-A", failure_rate=0.05),
            summary_factory("MERCH-B", failure_rate=0.10),
        ]
        result = check_success_rate_alert(summaries, default_config)
        assert result.severity == AlertSeverity.OK
        assert result.breaching_merchants == []

    def test_warning_threshold_breach(self, default_config, summary_factory):
        summaries = [summary_factory("MERCH-A", failure_rate=0.25)]
        result = check_success_rate_alert(summaries, default_config)
        assert result.severity == AlertSeverity.WARNING
        assert "MERCH-A" in result.breaching_merchants

    def test_critical_threshold_breach(self, default_config, summary_factory):
        summaries = [summary_factory("MERCH-A", failure_rate=0.45)]
        result = check_success_rate_alert(summaries, default_config)
        assert result.severity == AlertSeverity.CRITICAL
        assert "MERCH-A" in result.breaching_merchants

    def test_critical_wins_over_warning(self, default_config, summary_factory):
        summaries = [
            summary_factory("MERCH-WARN", failure_rate=0.25),
            summary_factory("MERCH-CRIT", failure_rate=0.45),
        ]
        result = check_success_rate_alert(summaries, default_config)
        assert result.severity == AlertSeverity.CRITICAL

    def test_below_min_volume_is_ignored(self, default_config, summary_factory):
        summaries = [summary_factory("MERCH-TINY", failure_rate=1.0, txn_count=2)]
        result = check_success_rate_alert(summaries, default_config)
        assert result.severity == AlertSeverity.OK

    def test_empty_summaries_returns_ok(self, default_config):
        result = check_success_rate_alert([], default_config)
        assert result.severity == AlertSeverity.OK
        assert "No transaction data" in result.human_summary

    def test_human_summary_names_breaching_merchant(self, default_config, summary_factory):
        summaries = [summary_factory("MERCH-BAD", failure_rate=0.45)]
        result = check_success_rate_alert(summaries, default_config)
        assert "MERCH-BAD" in result.human_summary

    def test_invalid_config_threshold_raises(self):
        with pytest.raises(ValueError):
            AlertConfig(
                warning_threshold     = 1.5,
                critical_threshold    = 0.40,
                min_transaction_count = 5,
            )

    def test_min_count_valid_value_passes(self):
        config = AlertConfig(
            warning_threshold=0.20,
            critical_threshold=0.40,
            min_transaction_count=1,
        )
        assert config.min_transaction_count == 1

    def test_is_actionable_true_on_warning(self, default_config, summary_factory):
        summaries = [summary_factory("MERCH-A", failure_rate=0.25)]
        result = check_success_rate_alert(summaries, default_config)
        assert result.is_actionable is True

    def test_is_actionable_false_on_ok(self, default_config, summary_factory):
        summaries = [summary_factory("MERCH-A", failure_rate=0.05)]
        result = check_success_rate_alert(summaries, default_config)
        assert result.is_actionable is False
