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
_MAX_CHART_MERCHANTS = 10


def render_risk_dashboard(
    profiles: list[MerchantRiskProfile],
    rolling_df: pd.DataFrame,
) -> None:
    """Render the full risk analytics section.

    Args:
        profiles: Per-merchant risk profiles filtered by sidebar controls.
        rolling_df: Rolling success rate time-series for line charts.
    """
    st.header("Risk Analytics")

    if not profiles:
        st.info("Need at least 3 days of data per merchant for risk metrics.")
        return

    _render_risk_scorecards(profiles)
    render_risk_heatmap(profiles)

    col_l, col_r = st.columns(2)
    with col_l:
        _render_sharpe_sortino_scatter(profiles)
    with col_r:
        render_var_distribution(profiles)

    if not rolling_df.empty:
        _render_rolling_statistics(rolling_df)

    _render_risk_table(profiles)


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


def _top_n_merchants(rolling_df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Limit to top N merchants by total volume to keep charts readable."""
    if rolling_df["merchant_id"].nunique() <= n:
        return rolling_df
    vol = rolling_df.groupby("merchant_id")["success_rate"].count().nlargest(n)
    return rolling_df[rolling_df["merchant_id"].isin(vol.index)]


def _render_rolling_statistics(rolling_df: pd.DataFrame) -> None:
    """Multi-panel rolling statistics."""
    st.subheader("Rolling Statistics")

    chart_df = _top_n_merchants(rolling_df, _MAX_CHART_MERCHANTS)

    tab_mean, tab_vol, tab_dist = st.tabs(
        ["Rolling Mean", "Rolling Volatility", "Daily Change Distribution"]
    )

    with tab_mean:
        _render_rolling_mean_chart(chart_df)
    with tab_vol:
        _render_rolling_volatility_chart(chart_df)
    with tab_dist:
        _render_daily_change_histogram(rolling_df)


def _render_rolling_mean_chart(rolling_df: pd.DataFrame) -> None:
    """Line chart: rolling 7-day average success rate per merchant."""
    fig = px.line(
        rolling_df,
        x="txn_date",
        y="rolling_mean",
        color="merchant_id",
        title="Rolling 7-Day Avg Success Rate",
        labels={
            "txn_date": "Date",
            "rolling_mean": "Success Rate (7d avg)",
            "merchant_id": "Merchant",
        },
    )
    fig.add_hline(
        y=0.95, line_dash="dash", line_color="red",
        annotation_text="95% SLA",
    )
    y_min = max(0, rolling_df["rolling_mean"].min() - 0.05)
    fig.update_layout(
        yaxis_tickformat=".0%",
        yaxis_range=[y_min, 1.02],
        hovermode="x unified",
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_rolling_volatility_chart(rolling_df: pd.DataFrame) -> None:
    """Line chart: rolling 7-day std of success rate (volatility)."""
    plot_df = rolling_df.dropna(subset=["rolling_std"])
    if plot_df.empty:
        st.info("Not enough data points for rolling volatility.")
        return

    fig = px.line(
        plot_df,
        x="txn_date",
        y="rolling_std",
        color="merchant_id",
        title="Rolling 7-Day Volatility (Std Dev of Success Rate)",
        labels={
            "txn_date": "Date",
            "rolling_std": "Volatility (σ)",
            "merchant_id": "Merchant",
        },
    )
    fig.update_layout(
        yaxis_tickformat=".1%",
        hovermode="x unified",
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_daily_change_histogram(rolling_df: pd.DataFrame) -> None:
    """Histogram of daily first-difference returns across all merchants."""
    changes = rolling_df["daily_change"].dropna()
    if changes.empty:
        st.info("No daily change data available.")
        return

    fig = px.histogram(
        changes,
        nbins=min(50, max(10, len(changes) // 5)),
        title="Distribution of Daily Success Rate Changes",
        labels={"value": "Daily Change (pp)", "count": "Frequency"},
        color_discrete_sequence=["#636EFA"],
    )
    fig.update_layout(
        xaxis_tickformat=".0%",
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
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
        "Download Risk Report (CSV)",
        data=csv,
        file_name="merchant_risk_report.csv",
        mime="text/csv",
    )


def _safe_mean(values: list[float]) -> float:
    """Return arithmetic mean, or 0.0 for empty input."""
    return sum(values) / len(values) if values else 0.0
