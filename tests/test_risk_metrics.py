"""Tests for risk metrics engine — annualized Sharpe/Sortino, VaR, drawdown, rolling."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.backend.transforms.risk_metrics import (
    ANNUALIZATION_FACTOR,
    _classify_risk,
    _max_drawdown,
    compute_risk_profiles,
    compute_rolling_success,
)
from src.schemas.payments import MerchantRiskProfile, TransactionSummary


def _make_summaries(
    merchant_id: str = "MERCH-A",
    days: int = 10,
    base_failure_rate: float = 0.05,
    volume: float = 1000.0,
    volatility: float = 0.0,
) -> list[TransactionSummary]:
    """Generate N daily summaries with optional failure-rate noise."""
    result = []
    rng = np.random.default_rng(42)
    for i in range(days):
        noise = rng.normal(0, volatility) if volatility > 0 else 0.0
        rate = max(0.0, min(1.0, base_failure_rate + noise))
        result.append(
            TransactionSummary(
                merchant_id=merchant_id,
                txn_date=date(2025, 1, 1) + timedelta(days=i),
                total_volume=volume,
                txn_count=100,
                failure_rate=round(rate, 4),
            )
        )
    return result


class TestComputeRiskProfiles:

    def test_returns_list_of_profiles(self):
        summaries = _make_summaries(days=5)
        profiles = compute_risk_profiles(summaries)
        assert isinstance(profiles, list)
        assert all(isinstance(p, MerchantRiskProfile) for p in profiles)

    def test_single_day_skipped(self):
        summaries = _make_summaries(days=1)
        profiles = compute_risk_profiles(summaries)
        assert len(profiles) == 0

    def test_two_days_skipped(self):
        """Minimum is 3 data points for first-difference returns."""
        summaries = _make_summaries(days=2)
        profiles = compute_risk_profiles(summaries)
        assert len(profiles) == 0

    def test_three_days_minimum(self):
        summaries = _make_summaries(days=3, volatility=0.01)
        profiles = compute_risk_profiles(summaries)
        assert len(profiles) == 1

    def test_empty_input(self):
        assert compute_risk_profiles([]) == []

    def test_multiple_merchants(self):
        s1 = _make_summaries("MERCH-A", days=5, volatility=0.01)
        s2 = _make_summaries("MERCH-B", days=5, volatility=0.01)
        profiles = compute_risk_profiles(s1 + s2)
        ids = {p.merchant_id for p in profiles}
        assert ids == {"MERCH-A", "MERCH-B"}

    def test_low_failure_produces_positive_sharpe(self):
        summaries = _make_summaries(days=10, base_failure_rate=0.01, volatility=0.005)
        profiles = compute_risk_profiles(summaries, target_sla=0.95)
        assert profiles[0].sharpe_ratio is not None
        assert profiles[0].sharpe_ratio > 0

    def test_declining_rates_produce_negative_sharpe(self):
        """A merchant whose success rate trends downward has negative daily returns."""
        summaries = [
            TransactionSummary(
                merchant_id="MERCH-DECLINING",
                txn_date=date(2025, 1, 1) + timedelta(days=i),
                total_volume=1000.0,
                txn_count=100,
                failure_rate=round(0.05 + i * 0.05, 2),
            )
            for i in range(10)
        ]
        profiles = compute_risk_profiles(summaries, target_sla=0.95)
        p = profiles[0]
        assert p.sharpe_ratio is not None
        assert p.sharpe_ratio < 0

    def test_days_observed_correct(self):
        summaries = _make_summaries(days=7)
        profiles = compute_risk_profiles(summaries)
        assert profiles[0].days_observed == 7

    def test_total_volume_correct(self):
        summaries = _make_summaries(days=5, volume=200.0)
        profiles = compute_risk_profiles(summaries)
        assert profiles[0].total_volume == 1000.0

    def test_var_95_between_0_and_1(self):
        summaries = _make_summaries(days=20, volatility=0.05)
        profiles = compute_risk_profiles(summaries)
        assert 0.0 <= profiles[0].value_at_risk_95 <= 1.0

    def test_max_drawdown_non_negative(self):
        summaries = _make_summaries(days=20, volatility=0.1)
        profiles = compute_risk_profiles(summaries)
        assert profiles[0].max_drawdown >= 0.0

    def test_sortino_only_uses_downside(self):
        summaries = _make_summaries(days=10, base_failure_rate=0.01, volatility=0.005)
        profiles = compute_risk_profiles(summaries, target_sla=0.95)
        p = profiles[0]
        if p.sortino_ratio is not None and p.sharpe_ratio is not None:
            assert p.sortino_ratio >= p.sharpe_ratio or p.sortino_ratio is None

    def test_calmar_none_when_no_drawdown(self):
        summaries = _make_summaries(days=5, base_failure_rate=0.0, volatility=0.0)
        profiles = compute_risk_profiles(summaries)
        if profiles:
            p = profiles[0]
            assert p.calmar_ratio is None or p.max_drawdown == 0.0

    def test_profiles_sorted_by_sharpe(self):
        s_good = _make_summaries("MERCH-GOOD", days=10, base_failure_rate=0.01, volatility=0.005)
        s_bad = _make_summaries("MERCH-BAD", days=10, base_failure_rate=0.20, volatility=0.05)
        profiles = compute_risk_profiles(s_good + s_bad, target_sla=0.95)
        sharpes = [p.sharpe_ratio or float("-inf") for p in profiles]
        assert sharpes == sorted(sharpes)

    def test_annualization_factor_is_365(self):
        """Payments use 365-day annualization (not 252 trading days)."""
        assert ANNUALIZATION_FACTOR == 365

    def test_no_inf_or_nan_in_profiles(self):
        """First-difference returns should never produce inf/NaN."""
        summaries = []
        for i in range(15):
            summaries.append(TransactionSummary(
                merchant_id="MERCH-ZERO",
                txn_date=date(2025, 1, 1) + timedelta(days=i),
                total_volume=200.0,
                txn_count=2,
                failure_rate=1.0 if i % 5 == 0 else 0.0,
            ))
        profiles = compute_risk_profiles(summaries)
        for p in profiles:
            if p.sharpe_ratio is not None:
                assert np.isfinite(p.sharpe_ratio)
            if p.sortino_ratio is not None:
                assert np.isfinite(p.sortino_ratio)


class TestMaxDrawdown:

    def test_no_drawdown_constant_rates(self):
        rates = np.array([0.95, 0.95, 0.95, 0.95])
        assert _max_drawdown(rates) == 0.0

    def test_simple_drawdown(self):
        rates = np.array([1.0, 0.9, 0.8, 0.95])
        dd = _max_drawdown(rates)
        assert dd > 0

    def test_single_element(self):
        assert _max_drawdown(np.array([0.95])) == 0.0

    def test_drawdown_peak_to_trough(self):
        rates = np.array([1.0, 0.95, 0.90, 0.92, 0.88])
        dd = _max_drawdown(rates)
        assert 0 < dd < 1.0


class TestClassifyRisk:

    def test_low_risk(self):
        assert _classify_risk(sharpe=1.5, mdd=0.02, var_95=0.97, target_sla=0.95) == "LOW"

    def test_high_risk_negative_sharpe(self):
        assert _classify_risk(sharpe=-0.5, mdd=0.05, var_95=0.90, target_sla=0.95) == "HIGH"

    def test_high_risk_large_drawdown(self):
        assert _classify_risk(sharpe=0.5, mdd=0.20, var_95=0.90, target_sla=0.95) == "HIGH"

    def test_high_risk_low_var(self):
        assert _classify_risk(sharpe=0.5, mdd=0.05, var_95=0.80, target_sla=0.95) == "HIGH"

    def test_medium_risk_default(self):
        assert _classify_risk(sharpe=0.5, mdd=0.08, var_95=0.90, target_sla=0.95) == "MEDIUM"

    def test_none_sharpe_not_low(self):
        assert _classify_risk(sharpe=None, mdd=0.02, var_95=0.97, target_sla=0.95) != "LOW"


class TestComputeRollingSuccess:

    def test_empty_input(self):
        df = compute_rolling_success([])
        assert df.empty

    def test_columns_present(self):
        summaries = _make_summaries(days=10)
        df = compute_rolling_success(summaries)
        expected_cols = {
            "merchant_id", "txn_date", "success_rate",
            "daily_change", "rolling_mean", "rolling_std",
        }
        assert expected_cols.issubset(set(df.columns))

    def test_row_count_matches_input(self):
        summaries = _make_summaries(days=10)
        df = compute_rolling_success(summaries)
        assert len(df) == 10

    def test_rolling_smooths_values(self):
        summaries = _make_summaries(days=14, volatility=0.1)
        df = compute_rolling_success(summaries, window=7)
        raw_std = df["success_rate"].std()
        rolling_std = df["rolling_mean"].std()
        assert rolling_std <= raw_std

    def test_window_of_1_equals_raw(self):
        summaries = _make_summaries(days=5)
        df = compute_rolling_success(summaries, window=1)
        np.testing.assert_array_almost_equal(
            df["success_rate"].values, df["rolling_mean"].values
        )

    def test_daily_change_is_first_difference(self):
        """Verify daily_change is diff() not pct_change()."""
        summaries = _make_summaries(days=5, volatility=0.02)
        df = compute_rolling_success(summaries)
        rates = df["success_rate"].values
        expected = np.diff(rates)
        actual = df["daily_change"].dropna().values
        np.testing.assert_array_almost_equal(actual, expected)

    def test_no_inf_in_rolling(self):
        """Verify first-difference never produces inf (unlike pct_change)."""
        summaries = []
        for i in range(10):
            summaries.append(TransactionSummary(
                merchant_id="MERCH-FLIP",
                txn_date=date(2025, 1, 1) + timedelta(days=i),
                total_volume=200.0,
                txn_count=2,
                failure_rate=1.0 if i % 2 == 0 else 0.0,
            ))
        df = compute_rolling_success(summaries)
        assert not df["daily_change"].replace([np.inf, -np.inf], np.nan).isna().all()
        assert np.all(np.isfinite(df["daily_change"].dropna()))
