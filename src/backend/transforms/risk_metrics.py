"""Risk analytics engine — pure functions, no I/O.

Maps traditional financial risk ratios to payments performance metrics.

Key mappings (adapted from bootcamp stock-analysis patterns):
- Daily "return" = first-difference of success rate (bounded [0,1])
- Annualization factor = 365 (payments operate every calendar day)
- Sharpe = (mean_daily_return * 365) / (std_daily_return * sqrt(365))
- Sortino = same but only downside std (days with negative returns)

NOTE: ``pct_change()`` is intentionally NOT used because success rates
can be 0.0 on low-volume days, producing inf/NaN.  First-difference
(``np.diff``) is the correct analogue for bounded [0,1] metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.schemas.payments import MerchantRiskProfile, TransactionSummary

DEFAULT_TARGET_SLA = 0.95
ANNUALIZATION_FACTOR = 365


def compute_risk_profiles(
    summaries: list[TransactionSummary],
    target_sla: float = DEFAULT_TARGET_SLA,
) -> list[MerchantRiskProfile]:
    """Compute risk analytics for each merchant with >= 3 data points."""
    if not summaries:
        return []

    df = pd.DataFrame([s.model_dump() for s in summaries])
    df["success_rate"] = 1.0 - df["failure_rate"]
    df = df.sort_values(["merchant_id", "txn_date"])

    profiles: list[MerchantRiskProfile] = []
    for merchant_id, group in df.groupby("merchant_id"):
        if len(group) < 3:
            continue
        profile = _compute_single_profile(str(merchant_id), group, target_sla)
        profiles.append(profile)

    profiles.sort(key=lambda p: p.sharpe_ratio or float("-inf"))
    return profiles


def _compute_single_profile(
    merchant_id: str,
    group: pd.DataFrame,
    target_sla: float,
) -> MerchantRiskProfile:
    """All ratio math for one merchant using first-difference daily returns."""
    rates = group["success_rate"].to_numpy(dtype=np.float64)
    volumes = group["total_volume"].to_numpy(dtype=np.float64)

    daily_returns = np.diff(rates)

    mean_return = float(np.mean(daily_returns))
    std_return = float(np.std(daily_returns, ddof=1))

    ann = ANNUALIZATION_FACTOR
    sharpe = (
        (mean_return * ann) / (std_return * np.sqrt(ann))
        if std_return > 0 else None
    )

    downside_returns = daily_returns[daily_returns < 0]
    downside_std = (
        float(np.std(downside_returns, ddof=1))
        if len(downside_returns) > 1 else 0.0
    )
    sortino = (
        (mean_return * ann) / (downside_std * np.sqrt(ann))
        if downside_std > 0 else None
    )

    mdd = _max_drawdown(rates)
    ann_excess = mean_return * ann
    calmar = ann_excess / mdd if mdd > 0 else None

    var_95 = float(np.percentile(rates, 5))

    mean_rate = float(np.mean(rates))
    std_rate = float(np.std(rates, ddof=1))

    return MerchantRiskProfile(
        merchant_id=merchant_id,
        days_observed=len(rates),
        avg_success_rate=round(mean_rate, 4),
        success_rate_std=round(std_rate, 4),
        sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
        sortino_ratio=round(sortino, 4) if sortino is not None else None,
        calmar_ratio=round(calmar, 4) if calmar is not None else None,
        max_drawdown=round(mdd, 4),
        value_at_risk_95=round(var_95, 4),
        avg_daily_volume=round(float(np.mean(volumes)), 2),
        total_volume=round(float(np.sum(volumes)), 2),
        risk_rating=_classify_risk(sharpe, mdd, var_95, target_sla),
    )


def _max_drawdown(rates: np.ndarray) -> float:
    """Largest peak-to-trough decline in absolute success rate."""
    if len(rates) < 2:
        return 0.0
    peak = np.maximum.accumulate(rates)
    drawdowns = (peak - rates) / np.where(peak > 0, peak, 1.0)
    return float(np.max(drawdowns))


def _classify_risk(
    sharpe: float | None,
    mdd: float,
    var_95: float,
    target_sla: float,
) -> str:
    """Assign a RAG risk rating based on combined metrics."""
    if sharpe is not None and sharpe >= 1.0 and mdd < 0.05 and var_95 >= target_sla:
        return "LOW"
    if sharpe is not None and sharpe < 0:
        return "HIGH"
    if mdd >= 0.15 or var_95 < target_sla * 0.90:
        return "HIGH"
    return "MEDIUM"


def compute_rolling_success(
    summaries: list[TransactionSummary],
    window: int = 7,
) -> pd.DataFrame:
    """Rolling statistics per merchant for time-series charts.

    Uses first-difference (not pct_change) for daily returns because
    success rates are bounded [0,1] and can be 0.0 on low-volume days.

    Returns columns: merchant_id, txn_date, success_rate, daily_change,
    rolling_mean, rolling_std
    """
    if not summaries:
        return pd.DataFrame()

    df = pd.DataFrame([s.model_dump() for s in summaries])
    df["success_rate"] = 1.0 - df["failure_rate"]
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df = df.sort_values(["merchant_id", "txn_date"])

    parts: list[pd.DataFrame] = []
    for _, group in df.groupby("merchant_id", sort=False):
        g = group.copy()
        g["daily_change"] = g["success_rate"].diff()
        g["rolling_mean"] = g["success_rate"].rolling(window, min_periods=1).mean()
        g["rolling_std"] = g["success_rate"].rolling(
            window, min_periods=min(2, window),
        ).std()
        parts.append(g)

    rolling = pd.concat(parts, ignore_index=True) if parts else df
    return rolling[
        [
            "merchant_id", "txn_date", "success_rate", "daily_change",
            "rolling_mean", "rolling_std",
        ]
    ].reset_index(drop=True)
