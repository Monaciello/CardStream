"""Tests for frontend rendering components — charts, risk dashboard, seaborn.

These tests exercise the Streamlit render functions directly by mocking
``st.*`` calls.  They verify that the functions run without errors for
various inputs, not pixel-level correctness (that's visual QA).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.backend.transforms.alert_models import AlertConfig
from src.schemas.payments import MerchantRiskProfile, RawTransaction, TransactionSummary, TransactionStatus


def _make_summaries(
    merchants: int = 3,
    days: int = 7,
) -> list[TransactionSummary]:
    """Generate multi-day, multi-merchant summaries for rendering tests."""
    result = []
    for m in range(merchants):
        for d in range(days):
            result.append(TransactionSummary(
                merchant_id=f"MERCH-{chr(65 + m)}",
                txn_date=date(2025, 1, 10) + timedelta(days=d),
                total_volume=1000.0 + m * 100 + d * 10,
                txn_count=50 + m * 5,
                failure_rate=round(0.05 + m * 0.15, 2),
            ))
    return result


def _make_profiles(count: int = 3) -> list[MerchantRiskProfile]:
    """Generate risk profiles for rendering tests."""
    ratings = ["LOW", "MEDIUM", "HIGH"]
    return [
        MerchantRiskProfile(
            merchant_id=f"MERCH-{chr(65 + i)}",
            days_observed=10,
            avg_success_rate=round(0.98 - i * 0.02, 2),
            success_rate_std=round(0.01 + i * 0.005, 4),
            sharpe_ratio=round(2.0 - i * 0.5, 2),
            sortino_ratio=round(2.5 - i * 0.6, 2),
            calmar_ratio=round(1.5 - i * 0.3, 2) if i < 4 else None,
            max_drawdown=round(0.02 + i * 0.02, 4),
            value_at_risk_95=round(0.96 - i * 0.01, 4),
            avg_daily_volume=1000.0 + i * 500,
            total_volume=10000.0 + i * 5000,
            risk_rating=ratings[i % len(ratings)],
        )
        for i in range(count)
    ]


def _make_rolling_df(merchants: int = 3, days: int = 10) -> pd.DataFrame:
    """Generate a rolling statistics DataFrame."""
    rng = np.random.default_rng(99)
    rows = []
    for m in range(merchants):
        base_rate = 0.95 - m * 0.03
        for d in range(days):
            rate = base_rate + rng.normal(0, 0.01)
            rows.append({
                "merchant_id": f"MERCH-{chr(65 + m)}",
                "txn_date": pd.Timestamp(date(2025, 1, 1) + timedelta(days=d)),
                "success_rate": rate,
                "daily_change": rng.normal(0, 0.01) if d > 0 else float("nan"),
                "rolling_mean": rate - 0.005,
                "rolling_std": abs(rng.normal(0.01, 0.003)),
            })
    return pd.DataFrame(rows)


def _make_raw_transactions(merchants: int = 3, per_merchant: int = 10) -> list[RawTransaction]:
    """Generate raw transactions with some failures for testing."""
    result = []
    txn_id = 1
    for m in range(merchants):
        for i in range(per_merchant):
            is_failed = i % 4 == 0
            result.append(RawTransaction(
                transaction_id=f"TXN-{txn_id:05d}",
                merchant_id=f"MERCH-{chr(65 + m)}",
                amount=100.0 + i * 10,
                status=TransactionStatus.FAILED if is_failed else TransactionStatus.SUCCESS,
                failure_reason="TIMEOUT" if is_failed else None,
                txn_date=date(2025, 1, 10) + timedelta(days=i % 7),
            ))
            txn_id += 1
    return result


# ── charts.py ──────────────────────────────────────────────────────

class TestRenderCharts:
    """Exercise all Plotly chart functions in charts.py."""

    def test_render_charts_with_data(self) -> None:
        from src.frontend.components.charts import render_charts
        alert_config = AlertConfig(warning_threshold=0.20, critical_threshold=0.40, min_transaction_count=5)
        render_charts(_make_summaries(), _make_raw_transactions(), alert_config)

    def test_render_charts_empty_shows_info(self) -> None:
        from src.frontend.components.charts import render_charts
        alert_config = AlertConfig(warning_threshold=0.20, critical_threshold=0.40, min_transaction_count=5)
        render_charts([], [], alert_config)

    def test_render_charts_single_merchant(self) -> None:
        from src.frontend.components.charts import render_charts
        alert_config = AlertConfig(warning_threshold=0.20, critical_threshold=0.40, min_transaction_count=5)
        render_charts(_make_summaries(merchants=1, days=5), _make_raw_transactions(merchants=1), alert_config)

    def test_volume_trend_runs(self) -> None:
        from src.frontend.components.charts import _render_volume_trend
        df = pd.DataFrame([s.model_dump() for s in _make_summaries()])
        df["txn_date"] = pd.to_datetime(df["txn_date"])
        _render_volume_trend(df)

    def test_failure_rate_by_merchant_runs(self) -> None:
        from src.frontend.components.charts import _render_failure_rate_by_merchant
        alert_config = AlertConfig(warning_threshold=0.20, critical_threshold=0.40, min_transaction_count=5)
        df = pd.DataFrame([s.model_dump() for s in _make_summaries()])
        df["txn_date"] = pd.to_datetime(df["txn_date"])
        _render_failure_rate_by_merchant(df, alert_config)

    def test_failure_reason_breakdown_runs(self) -> None:
        from src.frontend.components.charts import _render_failure_reason_breakdown
        _render_failure_reason_breakdown(_make_raw_transactions())

    def test_top_merchants_bar_runs(self) -> None:
        from src.frontend.components.charts import _render_top_merchants_bar
        df = pd.DataFrame([s.model_dump() for s in _make_summaries()])
        df["txn_date"] = pd.to_datetime(df["txn_date"])
        _render_top_merchants_bar(df)


# ── risk_dashboard.py ──────────────────────────────────────────────

class TestRiskDashboardComponents:
    """Exercise risk dashboard render functions."""

    def test_render_risk_dashboard_with_profiles(self) -> None:
        from src.frontend.components.risk_dashboard import render_risk_dashboard
        render_risk_dashboard(_make_profiles(), _make_rolling_df())

    def test_render_risk_dashboard_empty_profiles(self) -> None:
        from src.frontend.components.risk_dashboard import render_risk_dashboard
        render_risk_dashboard([], pd.DataFrame())

    def test_render_risk_dashboard_empty_rolling(self) -> None:
        from src.frontend.components.risk_dashboard import render_risk_dashboard
        render_risk_dashboard(_make_profiles(), pd.DataFrame())

    def test_risk_scorecards(self) -> None:
        from src.frontend.components.risk_dashboard import _render_risk_scorecards
        _render_risk_scorecards(_make_profiles())

    def test_risk_scorecards_all_none_ratios(self) -> None:
        from src.frontend.components.risk_dashboard import _render_risk_scorecards
        profiles = _make_profiles()
        for p in profiles:
            p.sharpe_ratio = None
            p.sortino_ratio = None
        _render_risk_scorecards(profiles)

    def test_sharpe_sortino_scatter(self) -> None:
        from src.frontend.components.risk_dashboard import _render_sharpe_sortino_scatter
        _render_sharpe_sortino_scatter(_make_profiles())

    def test_rolling_statistics(self) -> None:
        from src.frontend.components.risk_dashboard import _render_rolling_statistics
        _render_rolling_statistics(_make_rolling_df())

    def test_rolling_mean_chart(self) -> None:
        from src.frontend.components.risk_dashboard import _render_rolling_mean_chart
        _render_rolling_mean_chart(_make_rolling_df())

    def test_rolling_volatility_chart(self) -> None:
        from src.frontend.components.risk_dashboard import _render_rolling_volatility_chart
        _render_rolling_volatility_chart(_make_rolling_df())

    def test_rolling_volatility_empty(self) -> None:
        from src.frontend.components.risk_dashboard import _render_rolling_volatility_chart
        empty_df = pd.DataFrame(columns=[
            "merchant_id", "txn_date", "success_rate", "daily_change",
            "rolling_mean", "rolling_std",
        ])
        _render_rolling_volatility_chart(empty_df)

    def test_daily_change_histogram(self) -> None:
        from src.frontend.components.risk_dashboard import _render_daily_change_histogram
        _render_daily_change_histogram(_make_rolling_df())

    def test_daily_change_empty(self) -> None:
        from src.frontend.components.risk_dashboard import _render_daily_change_histogram
        empty_df = pd.DataFrame({"daily_change": pd.Series([], dtype=float)})
        _render_daily_change_histogram(empty_df)

    def test_top_n_merchants_limits(self) -> None:
        from src.frontend.components.risk_dashboard import _top_n_merchants
        big_df = _make_rolling_df(merchants=15, days=5)
        trimmed = _top_n_merchants(big_df, 5)
        assert trimmed["merchant_id"].nunique() == 5

    def test_top_n_merchants_passthrough_small(self) -> None:
        from src.frontend.components.risk_dashboard import _top_n_merchants
        small_df = _make_rolling_df(merchants=3, days=5)
        result = _top_n_merchants(small_df, 10)
        assert len(result) == len(small_df)

    def test_risk_table(self) -> None:
        from src.frontend.components.risk_dashboard import _render_risk_table
        _render_risk_table(_make_profiles())

    def test_safe_mean_with_values(self) -> None:
        from src.frontend.components.risk_dashboard import _safe_mean
        assert _safe_mean([1.0, 2.0, 3.0]) == 2.0

    def test_safe_mean_empty(self) -> None:
        from src.frontend.components.risk_dashboard import _safe_mean
        assert _safe_mean([]) == 0.0


# ── seaborn_charts.py ──────────────────────────────────────────────

class TestSeabornCharts:
    """Exercise seaborn chart rendering."""

    def test_var_distribution_with_profiles(self) -> None:
        from src.frontend.components.seaborn_charts import render_var_distribution
        render_var_distribution(_make_profiles(5))

    def test_var_distribution_too_few_profiles(self) -> None:
        from src.frontend.components.seaborn_charts import render_var_distribution
        render_var_distribution(_make_profiles(1))

    def test_risk_heatmap_with_profiles(self) -> None:
        from src.frontend.components.seaborn_charts import render_risk_heatmap
        render_risk_heatmap(_make_profiles(5))

    def test_risk_heatmap_too_few_profiles(self) -> None:
        from src.frontend.components.seaborn_charts import render_risk_heatmap
        render_risk_heatmap(_make_profiles(1))

    def test_risk_heatmap_many_profiles(self) -> None:
        """Trigger the nlargest(15) branch."""
        from src.frontend.components.seaborn_charts import render_risk_heatmap
        profiles = [
            MerchantRiskProfile(
                merchant_id=f"MERCH-{i:03d}",
                days_observed=10,
                avg_success_rate=round(0.99 - i * 0.005, 4),
                success_rate_std=0.01,
                sharpe_ratio=1.0,
                sortino_ratio=1.2,
                calmar_ratio=0.8,
                max_drawdown=0.03,
                value_at_risk_95=0.95,
                avg_daily_volume=1000.0,
                total_volume=10000.0,
                risk_rating="LOW",
            )
            for i in range(20)
        ]
        render_risk_heatmap(profiles)

    def test_render_figure_helper(self) -> None:
        """Verify the PNG buffer pipeline works end-to-end."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from src.frontend.components.seaborn_charts import _render_figure
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        _render_figure(fig)


# ── failure_analysis.py ───────────────────────────────────────────

class TestFailureAnalysis:

    def test_render_with_failed_transactions(self) -> None:
        from src.frontend.components.failure_analysis import render_failure_analysis
        render_failure_analysis(_make_raw_transactions(merchants=3, per_merchant=10))

    def test_render_empty_shows_info(self) -> None:
        from src.frontend.components.failure_analysis import render_failure_analysis
        render_failure_analysis([])

    def test_render_no_failures_shows_success(self) -> None:
        from src.frontend.components.failure_analysis import render_failure_analysis
        all_success = [
            RawTransaction(
                transaction_id=f"TXN-{i:05d}",
                merchant_id="MERCH-A",
                amount=100.0,
                status=TransactionStatus.SUCCESS,
                failure_reason=None,
                txn_date=date(2025, 1, 10),
            )
            for i in range(5)
        ]
        render_failure_analysis(all_success)


# ── alert_models edge case ─────────────────────────────────────────

class TestAlertModelsEdgeCases:

    def test_min_transaction_count_zero_raises(self) -> None:
        from src.backend.transforms.alert_models import AlertConfig
        with pytest.raises(ValueError, match="min_transaction_count must be >= 1"):
            AlertConfig(
                warning_threshold=0.20,
                critical_threshold=0.40,
                min_transaction_count=0,
            )

    def test_min_transaction_count_negative_raises(self) -> None:
        from src.backend.transforms.alert_models import AlertConfig
        with pytest.raises(ValueError, match="min_transaction_count must be >= 1"):
            AlertConfig(
                warning_threshold=0.20,
                critical_threshold=0.40,
                min_transaction_count=-5,
            )
