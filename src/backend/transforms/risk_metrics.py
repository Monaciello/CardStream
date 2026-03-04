"""Risk analytics engine — pure functions, no I/O.

Maps traditional financial risk ratios to payments performance metrics:
- Daily success rate (1 - failure_rate) is the "return"
- Target SLA (e.g. 99%) is the "risk-free rate"
- Downside deviation only considers days below SLA target

Ratios computed per merchant:
- Sharpe:  (mean_success - target) / std_success
- Sortino: (mean_success - target) / downside_std
- Calmar:  (mean_success - target) / max_drawdown
- VaR95:   5th percentile of daily success rates
- Max Drawdown: largest peak-to-trough drop in cumulative success
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.schemas.payments import MerchantRiskProfile, TransactionSummary

DEFAULT_TARGET_SLA = 0.95


def compute_risk_profiles(
    summaries: list[TransactionSummary],
    target_sla: float = DEFAULT_TARGET_SLA,
) -> list[MerchantRiskProfile]:
    """Compute risk analytics for each merchant with >= 2 data points."""
    if not summaries:
        return []

    df = pd.DataFrame([s.model_dump() for s in summaries])
    df["success_rate"] = 1.0 - df["failure_rate"]

    profiles: list[MerchantRiskProfile] = []
    for merchant_id, group in df.groupby("merchant_id"):
        if len(group) < 2:
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
    """All ratio math for one merchant."""
    rates = group["success_rate"].to_numpy(dtype=np.float64)
    volumes = group["total_volume"].to_numpy(dtype=np.float64)

    mean_rate = float(np.mean(rates))
    std_rate = float(np.std(rates, ddof=1))
    excess = mean_rate - target_sla

    sharpe = excess / std_rate if std_rate > 0 else None

    downside = rates[rates < target_sla] - target_sla
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = excess / downside_std if downside_std > 0 else None

    mdd = _max_drawdown(rates)
    calmar = excess / mdd if mdd > 0 else None

    var_95 = float(np.percentile(rates, 5))

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
    """Largest peak-to-trough decline in cumulative success rates."""
    cumulative = np.cumprod(rates / rates[0]) if rates[0] > 0 else rates
    peak = np.maximum.accumulate(cumulative)
    drawdowns = (peak - cumulative) / np.where(peak > 0, peak, 1.0)
    return float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0


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
    """Rolling average success rate per merchant for time-series charts.

    Returns a DataFrame with columns:
    merchant_id, txn_date, success_rate, rolling_success, rolling_volume
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
        g["rolling_success"] = g["success_rate"].rolling(window, min_periods=1).mean()
        g["rolling_volume"] = g["total_volume"].rolling(window, min_periods=1).mean()
        parts.append(g)

    rolling = pd.concat(parts, ignore_index=True) if parts else df
    return rolling[
        ["merchant_id", "txn_date", "success_rate", "rolling_success", "rolling_volume"]
    ].reset_index(drop=True)
