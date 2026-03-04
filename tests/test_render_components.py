"""Tests for frontend rendering components — charts, risk dashboard, seaborn.

These tests exercise the Streamlit render functions directly by mocking
``st.*`` calls.  They verify that the functions run without errors for
various inputs, not pixel-level correctness (that's visual QA).
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.schemas.payments import MerchantRiskProfile, TransactionSummary


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
    """Generate a rolling success DataFrame."""
    rows = []
    for m in range(merchants):
        for d in range(days):
            rows.append({
                "merchant_id": f"MERCH-{chr(65 + m)}",
                "txn_date": pd.Timestamp(date(2025, 1, 1) + timedelta(days=d)),
                "success_rate": 0.95 - m * 0.03,
                "rolling_success": 0.94 - m * 0.03,
                "rolling_volume": 1000.0 + m * 100,
            })
    return pd.DataFrame(rows)


# ── charts.py ──────────────────────────────────────────────────────

class TestRenderCharts:
    """Exercise all Plotly chart functions in charts.py."""

    def test_render_charts_with_data(self) -> None:
        from src.frontend.components.charts import render_charts
        render_charts(_make_summaries())

    def test_render_charts_empty_shows_info(self) -> None:
        from src.frontend.components.charts import render_charts
        render_charts([])

    def test_render_charts_single_merchant(self) -> None:
        from src.frontend.components.charts import render_charts
        render_charts(_make_summaries(merchants=1, days=5))

    def test_volume_trend_runs(self) -> None:
        from src.frontend.components.charts import _render_volume_trend
        df = pd.DataFrame([s.model_dump() for s in _make_summaries()])
        df["txn_date"] = pd.to_datetime(df["txn_date"])
        _render_volume_trend(df)

    def test_failure_rate_by_merchant_runs(self) -> None:
        from src.frontend.components.charts import _render_failure_rate_by_merchant
        df = pd.DataFrame([s.model_dump() for s in _make_summaries()])
        df["txn_date"] = pd.to_datetime(df["txn_date"])
        _render_failure_rate_by_merchant(df)

    def test_daily_txn_counts_runs(self) -> None:
        from src.frontend.components.charts import _render_daily_txn_counts
        df = pd.DataFrame([s.model_dump() for s in _make_summaries()])
        df["txn_date"] = pd.to_datetime(df["txn_date"])
        _render_daily_txn_counts(df)

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

    def test_rolling_success_chart(self) -> None:
        from src.frontend.components.risk_dashboard import _render_rolling_success_chart
        _render_rolling_success_chart(_make_rolling_df())

    def test_risk_table(self) -> None:
        from src.frontend.components.risk_dashboard import _render_risk_table
        _render_risk_table(_make_profiles())

    def test_safe_mean_with_values(self) -> None:
        from src.frontend.components.risk_dashboard import _safe_mean
        assert _safe_mean([1.0, 2.0, 3.0]) == 2.0

    def test_safe_mean_empty(self) -> None:
        from src.frontend.components.risk_dashboard import _safe_mean
        assert _safe_mean([]) == 0.0

    def test_merchant_filter_returns_all_by_default(self) -> None:
        from src.frontend.components.risk_dashboard import _render_merchant_filter
        profiles = _make_profiles()
        result = _render_merchant_filter(profiles)
        assert len(result) == len(profiles)

    @patch("src.frontend.components.risk_dashboard.st")
    def test_merchant_filter_empty_selection_returns_all(self, mock_st: MagicMock) -> None:
        """When multiselect returns [] (user cleared all), fall back to full list."""
        from src.frontend.components.risk_dashboard import _render_merchant_filter
        mock_st.multiselect.return_value = []
        profiles = _make_profiles()
        result = _render_merchant_filter(profiles)
        assert result == profiles


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


# ── migration_tracker.py ───────────────────────────────────────────

class TestMigrationTracker:

    def test_render_with_data(self) -> None:
        from src.frontend.components.migration_tracker import render_migration_tracker
        render_migration_tracker(_make_summaries(merchants=2, days=3))

    def test_render_empty_shows_info(self) -> None:
        from src.frontend.components.migration_tracker import render_migration_tracker
        render_migration_tracker([])


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
