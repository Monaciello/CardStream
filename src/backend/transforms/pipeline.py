"""Pipeline orchestration — sequences extract, transform, and alert stages.

``run_pipeline`` contains no logic of its own; it wires the independently
testable stages together.  Accepts any ``DataConnector`` (Snowflake,
PostgreSQL, mock) via the Protocol so callers stay agnostic.
"""
from __future__ import annotations

import pandas as pd

from src.backend.connectors.protocol import DataConnector
from src.backend.transforms.alert_engine import check_success_rate_alert
from src.backend.transforms.alert_models import AlertConfig, AlertResult
from src.backend.transforms.daily_summary import compute_daily_summary, to_dataframe
from src.backend.transforms.risk_metrics import compute_risk_profiles, compute_rolling_success
from src.schemas.payments import MerchantRiskProfile, RawTransaction, TransactionSummary


def run_pipeline(
    connector: DataConnector,
    sql: str,
    alert_config: AlertConfig,
) -> PipelineResult:
    """Extract → Transform → Alert.

    Args:
        connector: Any ``DataConnector`` implementation.
        sql: Query to execute against the connector.
        alert_config: Thresholds for alert evaluation.

    Returns:
        ``PipelineResult`` with raw transactions, summaries, summary
        DataFrame, and alert evaluation.
    """
    raw: list[RawTransaction] = connector.query_validated(sql, RawTransaction)

    df = pd.DataFrame([t.model_dump() for t in raw]) if raw else pd.DataFrame()

    summaries: list[TransactionSummary] = (
        compute_daily_summary(df) if not df.empty else []
    )

    alert: AlertResult = check_success_rate_alert(summaries, alert_config)
    risk_profiles: list[MerchantRiskProfile] = compute_risk_profiles(summaries)
    rolling_df: pd.DataFrame = compute_rolling_success(summaries)

    return PipelineResult(
        raw_transactions=raw,
        summaries=summaries,
        summary_df=to_dataframe(summaries) if summaries else pd.DataFrame(),
        alert=alert,
        risk_profiles=risk_profiles,
        rolling_df=rolling_df,
    )


class PipelineResult:
    """Typed container for the full pipeline output."""

    __slots__ = (
        "raw_transactions", "summaries", "summary_df",
        "alert", "risk_profiles", "rolling_df",
    )

    def __init__(
        self,
        raw_transactions: list[RawTransaction],
        summaries: list[TransactionSummary],
        summary_df: pd.DataFrame,
        alert: AlertResult,
        risk_profiles: list[MerchantRiskProfile],
        rolling_df: pd.DataFrame,
    ) -> None:
        self.raw_transactions = raw_transactions
        self.summaries = summaries
        self.summary_df = summary_df
        self.alert = alert
        self.risk_profiles = risk_profiles
        self.rolling_df = rolling_df
