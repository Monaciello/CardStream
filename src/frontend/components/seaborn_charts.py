"""Seaborn-based chart helpers for the risk analytics dashboard.

Separated from ``risk_dashboard`` so that matplotlib/seaborn rendering
logic (figure lifecycle, PNG buffer) is encapsulated in one place.
Plotly charts remain in the parent module since they render natively
in Streamlit without manual buffer management.
"""
from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

from src.schemas.payments import MerchantRiskProfile


def render_var_distribution(profiles: list[MerchantRiskProfile]) -> None:
    """Histogram + KDE of VaR(95%) across merchants."""
    var_vals = [p.value_at_risk_95 for p in profiles]
    if len(var_vals) < 2:
        st.info("Need more merchants for VaR distribution.")
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(var_vals, kde=True, color="#636EFA", ax=ax, bins=min(15, len(var_vals)))
    ax.axvline(float(np.mean(var_vals)), color="#ff4b4b", linestyle="--", label="Mean VaR")
    ax.set_xlabel("Success Rate at 95% Confidence")
    ax.set_ylabel("Merchant Count")
    ax.set_title("Value at Risk Distribution")
    ax.legend()
    plt.tight_layout()

    _render_figure(fig)


def render_risk_heatmap(profiles: list[MerchantRiskProfile]) -> None:
    """Heatmap of merchants x risk metrics (top 15 by success rate)."""
    if len(profiles) < 2:
        return

    rows = [
        {
            "Merchant": p.merchant_id,
            "Success Rate": p.avg_success_rate,
            "Sharpe": p.sharpe_ratio or 0,
            "Sortino": p.sortino_ratio or 0,
            "Max Drawdown": p.max_drawdown,
            "VaR 95%": p.value_at_risk_95,
            "Volatility": p.success_rate_std,
        }
        for p in profiles
    ]

    df = pd.DataFrame(rows).set_index("Merchant")
    top_n = df.nlargest(15, "Success Rate") if len(df) > 15 else df

    fig, ax = plt.subplots(figsize=(10, max(4, len(top_n) * 0.4)))
    sns.heatmap(
        top_n,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        linewidths=0.5,
        ax=ax,
    )
    ax.set_title("Merchant Risk Heatmap")
    plt.tight_layout()

    _render_figure(fig)


def _render_figure(fig: plt.Figure) -> None:  # type: ignore[name-defined]
    """Serialize a matplotlib figure to PNG and display via ``st.image``."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    st.image(buf, use_container_width=True)
