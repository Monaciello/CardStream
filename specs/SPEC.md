# SPEC.md — What This System Does

## Purpose

A Streamlit analytics dashboard for the Fund Manager Payments Team.
Surfaces transaction health metrics, financial risk ratios (Sharpe,
Sortino, VaR), and failure rate alerts — giving Product leaders and
operations teams a single, reliable self-service reporting view.

Runs locally against PostgreSQL (dev) or Streamlit-in-Snowflake (prod).

## Data Flow

```
Data source (Snowflake / PostgreSQL)
    │
    ▼  DataConnector.query_validated(sql, RawTransaction)
list[RawTransaction]              ← border: Pydantic rejects bad rows
    │
    ▼  compute_daily_summary(df)
list[TransactionSummary]          ← one row per merchant per day
    │
    ├──▶ check_success_rate_alert()   → AlertResult           → alert banner
    ├──▶ compute_risk_profiles()      → MerchantRiskProfile   → risk analytics tab
    ├──▶ compute_rolling_success()    → DataFrame              → rolling charts
    ├──▶ render_charts()              → Plotly charts           → overview tab
    └──▶ render_failure_analysis()    → failure breakdown       → failure analysis tab
```

## Inputs

- Data source: `DataConnector` (PostgreSQL locally, Snowflake in prod)
- Table: `raw_transactions` (local) / `PAYMENTS_DB.ANALYTICS.RAW_TRANSACTIONS`
- Columns: transaction_id, merchant_id, amount, status, failure_reason, txn_date
- User controls: 
  - Lookback window (7/14/30 days)
  - Merchant filter (global, applies to all tabs)
  - Warning/critical thresholds for alert coloring
  - Min transaction count

## Outputs

- Alert banner: OK / WARNING / CRITICAL with merchant names
- Four KPI metrics: active merchants, total volume, avg failure rate, high-risk count
- Transaction Overview tab: 3 Plotly charts (volume trend, failure rate by merchant with threshold lines, top-10 merchants)
- Risk Analytics tab: Sharpe/Sortino scatter, VaR distribution, heatmap, rolling success rate (mean/volatility/change distribution), interactive risk table with CSV download
- Failure Analysis tab: Failure reason donut chart, failure by merchant stacked bar, failure trend line, filterable detail table with CSV download

## Validation Rules

- amount > 0 (positive payments only)
- status ∈ {SUCCESS, FAILED, PENDING}
- FAILED requires failure_reason (cross-field rule, enforced in Python + SQL)
- failure_rate ∈ [0.0, 1.0]
- No NULL required fields, no duplicate transaction_ids (seed validation)
- Invalid rows quarantined, pipeline continues with valid rows

## Risk Metrics

| Metric | Maps to |
|--------|---------|
| Sharpe Ratio | (avg_success - SLA_target) / std_success |
| Sortino Ratio | Same, only penalising below-SLA days |
| Calmar Ratio | Excess return / max drawdown |
| VaR (95%) | 5th percentile of daily success rates |
| Max Drawdown | Largest peak-to-trough in cumulative success |
| Risk Rating | LOW / MEDIUM / HIGH based on combined metrics |

## Alert Logic

- WARNING: failure_rate >= warning_threshold (default 20%)
- CRITICAL: failure_rate >= critical_threshold (default 40%)
- Merchants below min_transaction_count excluded
- Worst-case severity governs the single banner shown
