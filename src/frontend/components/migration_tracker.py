"""Migration tracker component — merchant summary table with RAG colouring."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.schemas.payments import TransactionSummary

_WARNING_RATE  = 0.20
_CRITICAL_RATE = 0.40


def _color_failure_rate(val: Any) -> str:
    """CSS background for a single failure_rate cell."""
    if val >= _CRITICAL_RATE:
        return "background-color: #ff4b4b; color: white"
    if val >= _WARNING_RATE:
        return "background-color: #ffa500; color: white"
    return "background-color: #21c354; color: white"


def render_migration_tracker(summaries: list[TransactionSummary]) -> None:
    """Render the merchant summary table with failure-rate heat-mapping.

    Args:
        summaries: Output of ``compute_daily_summary``.  An empty list
            renders a friendly empty-state message.
    """
    st.subheader("Merchant Transaction Summary")

    if not summaries:
        st.info("No transaction data available for the selected window.")
        return

    df = pd.DataFrame([s.model_dump() for s in summaries])

    df["failure_rate"] = df["failure_rate"].map(lambda x: round(x, 4))
    df["total_volume"] = df["total_volume"].map(lambda x: f"${x:,.2f}")
    df["txn_date"]     = pd.to_datetime(df["txn_date"]).dt.strftime("%Y-%m-%d")

    df = df.rename(columns={
        "merchant_id":   "Merchant",
        "txn_date":      "Date",
        "total_volume":  "Volume",
        "txn_count":     "Transactions",
        "failure_rate":  "Failure Rate",
    })

    styled = df.style.map(_color_failure_rate, subset=["Failure Rate"])
    st.dataframe(styled, width="stretch")
