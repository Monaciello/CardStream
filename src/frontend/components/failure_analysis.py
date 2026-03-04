"""Failure Analysis component — actionable breakdown of why transactions fail.

Provides donut chart, stacked bar by merchant, trend line, and filterable
detail table with CSV download. Replaces the old Migration Tracker which
duplicated overview data without adding insight.
"""
from __future__ import annotations


import pandas as pd
import plotly.express as px
import streamlit as st

from src.schemas.payments import RawTransaction


def render_failure_analysis(raw_transactions: list[RawTransaction]) -> None:
    """Render the full failure analysis section.

    Args:
        raw_transactions: Raw transaction data filtered by sidebar controls.
    """
    st.header("Failure Analysis")

    if not raw_transactions:
        st.info("No transaction data available for the selected window.")
        return

    failed = [t for t in raw_transactions if t.status.value == "FAILED"]

    if not failed:
        st.success("No failed transactions in the selected window.")
        return

    df = pd.DataFrame([t.model_dump() for t in failed])
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["failure_reason"] = df["failure_reason"].fillna("UNKNOWN")

    _render_failure_summary_metrics(df)

    col_l, col_r = st.columns(2)
    with col_l:
        _render_failure_reason_donut(df)
    with col_r:
        _render_failure_by_merchant_bar(df)

    _render_failure_trend_line(df)
    _render_failure_detail_table(df)


def _render_failure_summary_metrics(df: pd.DataFrame) -> None:
    """KPI row: failure summary statistics."""
    total_failures = len(df)
    unique_merchants = df["merchant_id"].nunique()
    top_reason = df["failure_reason"].value_counts().idxmax()
    avg_amount = df["amount"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Failures", f"{total_failures:,}")
    c2.metric("Affected Merchants", unique_merchants)
    c3.metric("Top Reason", top_reason)
    c4.metric("Avg Failed Amount", f"${avg_amount:,.2f}")


def _render_failure_reason_donut(df: pd.DataFrame) -> None:
    """Donut chart — proportion of each failure reason."""
    counts = (
        df.groupby("failure_reason", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )

    fig = px.pie(
        counts,
        names="failure_reason",
        values="count",
        title="Failure Reason Distribution",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_failure_by_merchant_bar(df: pd.DataFrame) -> None:
    """Stacked bar — failure reasons by merchant (top 10 by count)."""
    top_merchants = df["merchant_id"].value_counts().nlargest(10).index

    df_top = df[df["merchant_id"].isin(top_merchants)]

    counts = (
        df_top.groupby(["merchant_id", "failure_reason"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )

    fig = px.bar(
        counts,
        x="merchant_id",
        y="count",
        color="failure_reason",
        title="Failure Reasons by Merchant (Top 10)",
        labels={"merchant_id": "Merchant", "count": "Failures", "failure_reason": "Reason"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_failure_trend_line(df: pd.DataFrame) -> None:
    """Line chart — daily failure count by reason over time."""
    daily = (
        df.groupby(["txn_date", "failure_reason"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )

    fig = px.line(
        daily,
        x="txn_date",
        y="count",
        color="failure_reason",
        title="Failure Trend by Reason",
        labels={"txn_date": "Date", "count": "Failures", "failure_reason": "Reason"},
        color_discrete_sequence=px.colors.qualitative.Set2,
        markers=True,
    )
    fig.update_layout(
        hovermode="x unified",
        margin=dict(l=0, r=0, t=40, b=0),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_failure_detail_table(df: pd.DataFrame) -> None:
    """Interactive data table with filterable columns and CSV download."""
    st.subheader("Failed Transaction Details")

    display_cols = [
        "transaction_id", "merchant_id", "amount", "failure_reason", "txn_date",
    ]
    
    table_df = df[display_cols].copy()
    table_df["amount"] = table_df["amount"].map(lambda x: f"${x:,.2f}")
    table_df["txn_date"] = table_df["txn_date"].dt.strftime("%Y-%m-%d")

    table_df = table_df.rename(columns={
        "transaction_id": "Transaction ID",
        "merchant_id": "Merchant",
        "amount": "Amount",
        "failure_reason": "Failure Reason",
        "txn_date": "Date",
    })

    st.dataframe(table_df, use_container_width=True, height=400)

    csv = table_df.to_csv(index=False)
    st.download_button(
        "Download Failure Report (CSV)",
        data=csv,
        file_name="failed_transactions.csv",
        mime="text/csv",
    )
