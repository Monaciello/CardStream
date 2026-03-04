"""Pure aggregation transforms — no I/O, no session, no caching.

Input and output are typed Python objects.  If you need to call
Snowflake or PostgreSQL, you are in the wrong file.
"""
from __future__ import annotations

import pandas as pd

from src.schemas.payments import TransactionSummary


def compute_daily_summary(df: pd.DataFrame) -> list[TransactionSummary]:
    """Aggregate validated rows into one summary per merchant per day.

    Args:
        df: DataFrame whose columns match ``RawTransaction`` field names.

    Returns:
        One ``TransactionSummary`` per ``(merchant_id, txn_date)`` group.
    """
    grouped = (
        df.groupby(["merchant_id", "txn_date"])
        .agg(
            total_volume =("amount", "sum"),
            txn_count    =("amount", "count"),
            failure_count=("status", lambda s: (s == "FAILED").sum()),
        )
        .reset_index()
    )

    grouped["failure_rate"] = grouped["failure_count"] / grouped["txn_count"]

    summaries: list[TransactionSummary] = []
    for _, row in grouped.iterrows():
        summaries.append(
            TransactionSummary(
                merchant_id  = row["merchant_id"],
                txn_date     = row["txn_date"],
                total_volume = round(float(row["total_volume"]), 2),
                txn_count    = int(row["txn_count"]),
                failure_rate = round(float(row["failure_rate"]), 4),
            )
        )

    return summaries


def to_dataframe(summaries: list[TransactionSummary]) -> pd.DataFrame:
    """Convert summary list to a DataFrame for rendering."""
    return pd.DataFrame([s.model_dump() for s in summaries])
