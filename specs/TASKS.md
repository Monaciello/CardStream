# TASKS.md — Ordered Build Checklist

One TDD cycle per task: write failing test → implement → refactor → check off.

## Round A — Schemas (contracts first)

- [x] Define TransactionStatus enum (SUCCESS / FAILED / PENDING)
- [x] Define RawTransaction with amount > 0 validator
- [x] Add cross-field validator: FAILED requires failure_reason
- [x] Define TransactionSummary with failure_rate 0–1 validator
- [x] Define MerchantRiskProfile with risk analytics fields
- [x] Write test_schemas.py — 16 tests, 100% coverage

## Round B — Connector (I/O boundary)

- [x] Define DataConnector protocol (PEP 544)
- [x] Implement SiSConnector with injected session (_self pattern)
- [x] Implement query_validated(sql, schema) with quarantine pattern
- [x] Add @st.cache_data(ttl=300) on query_validated
- [x] Extract ingest_transactions() + load_to_warehouse() → warehouse.py
- [x] Write test_connector.py — 8 tests, 100% coverage

## Round C — Transforms (pure logic)

- [x] Implement compute_daily_summary(df) groupby merchant + date
- [x] Implement to_dataframe() serialization helper
- [x] Implement AlertConfig with threshold validators
- [x] Implement AlertResult with is_actionable property
- [x] Implement check_success_rate_alert() worst-case severity logic
- [x] Implement compute_risk_profiles() — Sharpe, Sortino, VaR, drawdown
- [x] Implement compute_rolling_success() — 7-day rolling averages
- [x] Extend PipelineResult with risk_profiles + rolling_df
- [x] Write test_transforms.py + test_risk_metrics.py — 54 tests, 100%

## Round D — Dashboard (rendering layer)

- [x] Implement migration_tracker.py with RAG coloring
- [x] Implement alert_banner.py with severity-mapped st calls
- [x] Implement charts.py — 4 Plotly charts
- [x] Implement risk_dashboard.py — scatter, table, rolling, CSV download
- [x] Extract seaborn_charts.py — heatmap, VaR distribution
- [x] Implement app.py as tabbed composition root
- [x] Write test_dashboard.py + test_render_components.py — 36 tests

## Round E — PostgreSQL & Infrastructure

- [x] PostgreSQL bootstrap (schema with CHECK constraints, Makefile targets)
- [x] PgConnector implementing DataConnector protocol
- [x] Seed script with null/duplicate/cross-field validation
- [x] ON CONFLICT DO NOTHING as database-level safety net
- [x] sops-nix for secret management

## Round F — Quality & Documentation

- [x] Reorganize src/ into backend/ + frontend/ + schemas/
- [x] PEP 257 docstrings on all public functions
- [x] PEP 604 union syntax (X | None) throughout
- [x] PEP 544 Protocol alignment (unbounded TypeVar)
- [x] mypy --strict clean (26 source files)
- [x] ruff clean
- [x] 130 tests, 99% coverage
- [x] README, SPEC, DESIGN, TASKS documentation

## Remaining (post-MVP)

- [ ] QUARANTINE table write path
- [ ] pipeline.py integration test with @pytest.mark.integration
- [ ] Snowflake deploy and SiS smoke test
