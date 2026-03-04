"""Plotly visualizations for the payments dashboard."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.backend.transforms.alert_models import AlertConfig
from src.schemas.payments import RawTransaction, TransactionSummary


def render_charts(
    summaries: list[TransactionSummary],
    raw_transactions: list[RawTransaction],
    alert_config: AlertConfig,
) -> None:
    """Render all dashboard charts from pipeline summaries.

    Args:
        summaries: Output of ``compute_daily_summary``.
        raw_transactions: Raw transaction data for failure analysis.
        alert_config: Threshold configuration for drawing reference lines.
    """
    if not summaries:
        st.info("No data available for charts.")
        return

    df = pd.DataFrame([s.model_dump() for s in summaries])
    df["txn_date"] = pd.to_datetime(df["txn_date"])

    _render_volume_trend(df)

    col_left, col_right = st.columns(2)
    with col_left:
        _render_failure_rate_by_merchant(df, alert_config)
    with col_right:
        _render_failure_reason_breakdown(raw_transactions)

    _render_top_merchants_bar(df)


def _render_volume_trend(df: pd.DataFrame) -> None:
    """Line chart — daily transaction volume across all merchants."""
    daily = (
        df.groupby("txn_date", as_index=False)
        .agg(total_volume=("total_volume", "sum"))
    )
    fig = px.area(
        daily,
        x="txn_date",
        y="total_volume",
        title="Daily Transaction Volume",
        labels={"txn_date": "Date", "total_volume": "Volume ($)"},
        color_discrete_sequence=["#636EFA"],
    )
    fig.update_layout(
        hovermode="x unified",
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        margin=dict(l=0, r=0, t=40, b=0),
        height=320,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_failure_rate_by_merchant(
    df: pd.DataFrame,
    alert_config: AlertConfig,
) -> None:
    """Horizontal bar chart — average failure rate per merchant with thresholds."""
    merchant_avg = (
        df.groupby("merchant_id", as_index=False)
        .agg(
            avg_failure_rate=("failure_rate", "mean"),
            txn_count=("txn_count", "sum"),
        )
        .sort_values("avg_failure_rate", ascending=True)
    )

    colors = [
        "#ff4b4b" if r >= alert_config.critical_threshold
        else "#ffa500" if r >= alert_config.warning_threshold
        else "#21c354"
        for r in merchant_avg["avg_failure_rate"]
    ]

    fig = go.Figure(
        go.Bar(
            x=merchant_avg["avg_failure_rate"],
            y=merchant_avg["merchant_id"],
            orientation="h",
            marker_color=colors,
            text=merchant_avg["avg_failure_rate"].map(lambda v: f"{v:.1%}"),
            textposition="auto",
        )
    )
    
    fig.add_vline(
        x=alert_config.warning_threshold,
        line_dash="dash",
        line_color="#ffa500",
        annotation_text=f"Warning ({alert_config.warning_threshold:.0%})",
        annotation_position="top right",
    )
    fig.add_vline(
        x=alert_config.critical_threshold,
        line_dash="dash",
        line_color="#ff4b4b",
        annotation_text=f"Critical ({alert_config.critical_threshold:.0%})",
        annotation_position="top right",
    )
    
    fig.update_layout(
        title="Failure Rate by Merchant",
        xaxis_title="Avg Failure Rate",
        xaxis_tickformat=".0%",
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_failure_reason_breakdown(raw_transactions: list[RawTransaction]) -> None:
    """Stacked bar chart — failure reason distribution by merchant."""
    if not raw_transactions:
        st.info("No transaction data available.")
        return

    failed = [t for t in raw_transactions if t.status.value == "FAILED"]
    
    if not failed:
        st.info("No failed transactions in selected window.")
        return

    df = pd.DataFrame([
        {
            "merchant_id": t.merchant_id,
            "failure_reason": t.failure_reason or "UNKNOWN",
        }
        for t in failed
    ])

    counts = (
        df.groupby(["failure_reason"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )

    fig = px.bar(
        counts,
        x="failure_reason",
        y="count",
        title="Failure Reason Breakdown",
        labels={"failure_reason": "Reason", "count": "Count"},
        color="failure_reason",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_top_merchants_bar(df: pd.DataFrame) -> None:
    """Stacked bar — top 10 merchants by volume, split SUCCESS vs FAILED."""
    merchant_vol = (
        df.groupby("merchant_id", as_index=False)
        .agg(
            total_volume=("total_volume", "sum"),
            failure_rate=("failure_rate", "mean"),
            txn_count=("txn_count", "sum"),
        )
        .nlargest(10, "total_volume")
        .sort_values("total_volume", ascending=True)
    )

    success_vol = merchant_vol["total_volume"] * (1 - merchant_vol["failure_rate"])
    failed_vol = merchant_vol["total_volume"] * merchant_vol["failure_rate"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=merchant_vol["merchant_id"],
        x=success_vol,
        name="Success",
        orientation="h",
        marker_color="#21c354",
    ))
    fig.add_trace(go.Bar(
        y=merchant_vol["merchant_id"],
        x=failed_vol,
        name="Failed",
        orientation="h",
        marker_color="#ff4b4b",
    ))
    fig.update_layout(
        barmode="stack",
        title="Top 10 Merchants by Volume",
        xaxis_title="Volume ($)",
        xaxis_tickprefix="$",
        xaxis_tickformat=",.0f",
        margin=dict(l=0, r=0, t=60, b=0),
        height=420,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
