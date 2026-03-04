"""Risk analytics dashboard — interactive Plotly + Seaborn visualizations.

Renders financial-style risk metrics (Sharpe, Sortino, VaR, drawdown)
applied to payment success rates.  Designed for self-service reporting
by the Fund Manager Payments Team.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from src.frontend.components.seaborn_charts import render_risk_heatmap, render_var_distribution
from src.schemas.payments import MerchantRiskProfile

_RISK_COLORS = {"LOW": "#21c354", "MEDIUM": "#ffa500", "HIGH": "#ff4b4b"}


def render_risk_dashboard(
    profiles: list[MerchantRiskProfile],
    rolling_df: pd.DataFrame,
) -> None:
    """Render the full risk analytics section.

    Args:
        profiles: Per-merchant risk profiles from the pipeline.
        rolling_df: Rolling success rate time-series for line charts.
    """
    st.header("📊 Risk Analytics")

    if not profiles:
        st.info("Need at least 2 days of data per merchant for risk metrics.")
        return

    selected = _render_merchant_filter(profiles)

    _render_risk_scorecards(selected)
    render_risk_heatmap(selected)

    col_l, col_r = st.columns(2)
    with col_l:
        _render_sharpe_sortino_scatter(selected)
    with col_r:
        render_var_distribution(selected)

    if not rolling_df.empty:
        merchant_ids = [p.merchant_id for p in selected]
        filtered_rolling = rolling_df[rolling_df["merchant_id"].isin(merchant_ids)]
        if not filtered_rolling.empty:
            _render_rolling_success_chart(filtered_rolling)

    _render_risk_table(selected)


def _render_merchant_filter(
    profiles: list[MerchantRiskProfile],
) -> list[MerchantRiskProfile]:
    """Sidebar multiselect for merchant filtering."""
    all_ids = [p.merchant_id for p in profiles]
    chosen = st.multiselect(
        "Filter merchants",
        options=all_ids,
        default=all_ids,
        key="risk_merchant_filter",
    )
    if not chosen:
        return profiles
    return [p for p in profiles if p.merchant_id in chosen]


def _render_risk_scorecards(profiles: list[MerchantRiskProfile]) -> None:
    """KPI row: portfolio-level risk summary."""
    sharpe_vals = [p.sharpe_ratio for p in profiles if p.sharpe_ratio is not None]
    sortino_vals = [p.sortino_ratio for p in profiles if p.sortino_ratio is not None]
    mdd_vals = [p.max_drawdown for p in profiles]
    var_vals = [p.value_at_risk_95 for p in profiles]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Avg Sharpe", f"{_safe_mean(sharpe_vals):.2f}")
    c2.metric("Avg Sortino", f"{_safe_mean(sortino_vals):.2f}")
    c3.metric("Worst Drawdown", f"{max(mdd_vals):.1%}" if mdd_vals else "N/A")
    c4.metric("Avg VaR (95%)", f"{_safe_mean(var_vals):.1%}")
    c5.metric(
        "High-Risk Merchants",
        sum(1 for p in profiles if p.risk_rating == "HIGH"),
    )


def _render_sharpe_sortino_scatter(profiles: list[MerchantRiskProfile]) -> None:
    """Scatter plot: Sharpe vs Sortino, sized by volume, colored by risk."""
    rows = [
        {
            "Merchant": p.merchant_id,
            "Sharpe": p.sharpe_ratio or 0,
            "Sortino": p.sortino_ratio or 0,
            "Volume": p.total_volume,
            "Risk": p.risk_rating,
            "VaR 95%": p.value_at_risk_95,
        }
        for p in profiles
    ]
    df = pd.DataFrame(rows)

    fig = px.scatter(
        df,
        x="Sharpe",
        y="Sortino",
        size="Volume",
        color="Risk",
        hover_name="Merchant",
        hover_data={"VaR 95%": ":.1%", "Volume": ":$,.0f"},
        color_discrete_map=_RISK_COLORS,
        title="Sharpe vs Sortino Ratio (bubble = volume)",
    )
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
    fig.add_vline(x=0, line_dash="dot", line_color="gray", opacity=0.5)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=400)
    st.plotly_chart(fig, use_container_width=True)


def _render_rolling_success_chart(rolling_df: pd.DataFrame) -> None:
    """Plotly line chart: rolling 7-day success rate per merchant."""
    fig = px.line(
        rolling_df,
        x="txn_date",
        y="rolling_success",
        color="merchant_id",
        title="Rolling 7-Day Success Rate by Merchant",
        labels={
            "txn_date": "Date",
            "rolling_success": "Success Rate (7d avg)",
            "merchant_id": "Merchant",
        },
    )
    fig.add_hline(
        y=0.95, line_dash="dash", line_color="red",
        annotation_text="95% SLA Target",
    )
    fig.update_layout(
        yaxis_tickformat=".0%",
        hovermode="x unified",
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_risk_table(profiles: list[MerchantRiskProfile]) -> None:
    """Interactive data table with risk ratings and CSV download."""
    st.subheader("Merchant Risk Profiles")

    rows = [p.model_dump() for p in profiles]
    df = pd.DataFrame(rows)

    display_cols = [
        "merchant_id", "days_observed", "avg_success_rate", "sharpe_ratio",
        "sortino_ratio", "calmar_ratio", "max_drawdown", "value_at_risk_95",
        "avg_daily_volume", "total_volume", "risk_rating",
    ]
    df = df[display_cols]

    rename = {
        "merchant_id": "Merchant",
        "days_observed": "Days",
        "avg_success_rate": "Avg Success",
        "sharpe_ratio": "Sharpe",
        "sortino_ratio": "Sortino",
        "calmar_ratio": "Calmar",
        "max_drawdown": "Max DD",
        "value_at_risk_95": "VaR 95%",
        "avg_daily_volume": "Avg Daily Vol",
        "total_volume": "Total Vol",
        "risk_rating": "Risk",
    }
    df = df.rename(columns=rename)

    def _style_risk(val: Any) -> str:
        color = _RISK_COLORS.get(str(val), "")
        return f"background-color: {color}; color: white" if color else ""

    styled = df.style.map(_style_risk, subset=["Risk"])
    st.dataframe(styled, use_container_width=True, height=400)

    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Download Risk Report (CSV)",
        data=csv,
        file_name="merchant_risk_report.csv",
        mime="text/csv",
    )


def _safe_mean(values: list[float]) -> float:
    """Return arithmetic mean, or 0.0 for empty input."""
    return sum(values) / len(values) if values else 0.0
