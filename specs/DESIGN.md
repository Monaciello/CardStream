# DESIGN.md — Why Decisions Were Made

## Backend / Frontend / Schemas layering

```
src/
├── schemas/     — shared Pydantic models (used by both layers)
├── backend/     — connectors (I/O) + transforms (pure logic)
└── frontend/    — Streamlit app + UI components
```

`schemas/` is the shared vocabulary.  `backend/` never imports from
`frontend/`; `frontend/` depends on `backend/` and `schemas/`.  This
keeps the data pipeline independently testable and deployable.

## Inject the session, never call get_active_session() internally

`get_active_session()` is called once in `frontend/app.py` and passed
into `SiSConnector`.  Every layer below is testable without Snowflake
credentials.  The `_self` prefix prevents Streamlit from hashing the
session object for cache keying.

## Validate at the border, not in transforms

`RawTransaction` validation happens inside `SiSConnector.query_validated()`
(and identically in `PgConnector`).  Transform functions receive
pre-validated typed objects.  If a transform raises, it is a logic bug,
not a data quality issue.

## Quarantine pattern over fail-fast

Invalid rows are collected and logged rather than raising immediately.
A single malformed row should not halt ingestion for thousands of valid
rows.  The quarantine log surfaces the problem without stopping the run.

## Seed-time validation (defense in depth)

`db/seed.py` validates before INSERT: null checks on required fields,
duplicate `transaction_id` rejection, cross-field `FAILED` requires
`failure_reason`, and `amount > 0`.  The SQL schema reinforces these
with CHECK constraints and a PRIMARY KEY.  Defense in depth: Python
catches errors early, SQL is the final safety net.

## Two transform stages + risk analytics

T1 (pre-load): validate raw data into `RawTransaction`.
T2 (post-load): aggregate into `TransactionSummary`.
T3 (risk): compute `MerchantRiskProfile` from summaries.

Each stage is a pure function in `backend/transforms/` — no I/O.

## Financial ratios mapped to payments

Traditional Sharpe, Sortino, and VaR ratios assume "returns" and a
"risk-free rate."  In payments:
- "Return" = daily success rate (1 - failure_rate)
- "Risk-free rate" = SLA target (default 95%)
- "Downside" = days where success < SLA

This lets payment ops teams use familiar financial language to assess
merchant reliability.

## SRP extraction: warehouse.py and seaborn_charts.py

`sis_connector.py` originally contained `ingest_transactions()` and
`load_to_warehouse()` alongside the connector class.  These standalone
I/O helpers were extracted to `warehouse.py` for SRP.

Similarly, matplotlib/seaborn rendering (figure lifecycle, PNG buffer)
was extracted from `risk_dashboard.py` into `seaborn_charts.py` to
keep the main risk dashboard module focused on layout and Plotly charts.

## Secrets via sops-nix

`.env` files are not committed.  Secrets live in `secrets.yaml`,
encrypted with SOPS + age.  `nix develop` decrypts and exports them.

## AlertConfig as a Pydantic model

Threshold values are validated by the same system that validates
transaction data.  A misconfigured alert fails loudly at construction.

## Worst-case severity governs the banner

`check_success_rate_alert()` returns one `AlertResult` with the highest
severity found.  If any merchant is CRITICAL, the team sees CRITICAL.
