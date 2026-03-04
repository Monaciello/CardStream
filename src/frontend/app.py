"""Dashboard entry point — composition root.

All executable logic lives inside ``main()`` so tests can import the
module without triggering I/O.  Streamlit calls ``main()`` on each
script rerun.
"""
from __future__ import annotations

import datetime
from datetime import date, timedelta

import streamlit as st

from src.backend.connectors.protocol import DataConnector
from src.backend.connectors.sis_connector import SiSConnector
from src.backend.transforms.alert_models import AlertConfig
from src.backend.transforms.pipeline import run_pipeline
from src.frontend.components.alert_banner import render_alert_banner
from src.frontend.components.charts import render_charts
from src.frontend.components.migration_tracker import render_migration_tracker
from src.frontend.components.risk_dashboard import render_risk_dashboard


def get_session() -> object:
    """Lazy import — only called in SiS production, never in tests."""
    from snowflake.snowpark.context import get_active_session
    return get_active_session()


def build_query(
    date_from: date,
    table_name: str = "PAYMENTS_DB.ANALYTICS.RAW_TRANSACTIONS",
) -> str:
    """SQL for raw transactions in the lookback window.

    Args:
        date_from: Earliest date to include.
        table_name: Fully-qualified table.  Pass ``"raw_transactions"``
            for local PostgreSQL.
    """
    return f"""
        SELECT transaction_id, merchant_id, amount, status,
               failure_reason, txn_date
        FROM   {table_name}
        WHERE  txn_date >= '{date_from}'
    """


def main(connector: DataConnector | None = None) -> None:
    """Composition root — wires data pipeline to UI components.

    Args:
        connector: Injected data source.  Defaults to ``SiSConnector``
            when running in Snowflake; tests and local runners override.
    """
    st.set_page_config(
        page_title="Payments Analytics",
        page_icon="💳",
        layout="wide",
    )

    connector = connector or SiSConnector(get_session())

    st.sidebar.title("Filters")

    lookback_days = st.sidebar.selectbox(
        "Lookback window",
        options=[7, 14, 30],
        index=0,
        format_func=lambda x: f"Last {x} days",
    )

    date_from = date.today() - timedelta(days=lookback_days)

    alert_config = AlertConfig(
        warning_threshold=st.sidebar.slider(
            "Warning threshold", min_value=0.05, max_value=0.50,
            value=0.20, step=0.05, format="%.0f%%",
        ),
        critical_threshold=st.sidebar.slider(
            "Critical threshold", min_value=0.10, max_value=0.75,
            value=0.40, step=0.05, format="%.0f%%",
        ),
        min_transaction_count=st.sidebar.number_input(
            "Min transactions (ignore below)", min_value=1, value=5,
        ),
    )

    result = run_pipeline(
        connector=connector,
        sql=build_query(date_from),
        alert_config=alert_config,
    )

    summaries = result.summaries
    alert = result.alert

    st.title("💳 Payments Platform Analytics")
    st.caption(f"Data from {date_from} · refreshes every 5 minutes")

    render_alert_banner(alert)
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    total_merchants = len({s.merchant_id for s in summaries})
    total_volume = sum(s.total_volume for s in summaries)
    avg_failure_rate = (
        sum(s.failure_rate for s in summaries) / len(summaries)
        if summaries
        else 0.0
    )
    high_risk_count = sum(
        1 for p in result.risk_profiles if p.risk_rating == "HIGH"
    )

    col1.metric("Active Merchants", total_merchants)
    col2.metric("Total Volume", f"${total_volume:,.2f}")
    col3.metric("Avg Failure Rate", f"{avg_failure_rate:.1%}")
    col4.metric("High-Risk Merchants", high_risk_count)

    tab_overview, tab_risk, tab_migration = st.tabs(
        ["📈 Transaction Overview", "📊 Risk Analytics", "🔄 Migration Tracker"]
    )

    with tab_overview:
        render_charts(summaries)

    with tab_risk:
        render_risk_dashboard(result.risk_profiles, result.rolling_df)

    with tab_migration:
        render_migration_tracker(summaries)

    st.caption(
        f"Last refreshed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


if __name__ == "__main__":
    main()
