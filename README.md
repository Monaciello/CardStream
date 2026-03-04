# CardStream

Payments Platform Analytics ETL & Self-Service Dashboard for the
Fund Manager Payments Team.

## Quick Start

```bash
git clone git@github.com:Monaciello/CardStream.git && cd CardStream
nix develop
./bootstrap.sh
make run-pg          # http://localhost:8501
```

## Commands

| Command | Description |
|---------|-------------|
| `make run-pg` | Dashboard against local PostgreSQL |
| `make run` | Dashboard with mock data (no database) |
| `make test` | 142 tests, 99% coverage |
| `make lint` | ruff |
| `make typecheck` | mypy --strict |
| `make all` | lint + typecheck + test |
| `make db-init` | Initialize PostgreSQL |
| `make db-seed` | Seed with bootcamp CSV data |
| `make db-start` | Start existing server |
| `make db-stop` | Stop server |
| `make db-reset` | Wipe and rebuild |
| `./bootstrap.sh` | Full reset (venv + database) |
| `./healthcheck.sh` | Verify environment |

## Secrets

Secrets are encrypted with [SOPS](https://github.com/getsops/sops) + age.
The `secrets.yaml` file is safe to commit — it's AES-256 encrypted.

```bash
sops secrets.yaml           # edit (decrypts in $EDITOR, re-encrypts on save)
sops --decrypt secrets.yaml # view plaintext
```

`nix develop` automatically decrypts and exports secrets into the shell.

## Architecture

```
DataConnector (Snowflake | PostgreSQL | Mock)
    → query_validated(sql, RawTransaction)
    → run_pipeline(connector, sql, alert_config)
        → compute_daily_summary(df)        → list[TransactionSummary]
        → compute_risk_profiles(summaries) → list[MerchantRiskProfile]
        → check_success_rate_alert()       → AlertResult
    → Tabs: Transaction Overview | Risk Analytics | Failure Analysis
    → Sidebar: Lookback window, Merchant filter (global), Alert thresholds
```

All connectors satisfy the `DataConnector` protocol (PEP 544).
Sidebar merchant filter applies across all tabs and charts.

## Dashboard Tabs

| Tab | Contents |
|-----|----------|
| **Transaction Overview** | Volume trend, failure rate by merchant (with threshold lines), failure reason breakdown, top-10 merchants |
| **Risk Analytics** | Sharpe/Sortino scatter, VaR distribution, risk heatmap, rolling success rates (mean/volatility/change distribution), downloadable risk report |
| **Failure Analysis** | Failure reason donut chart, failure by merchant (stacked bar), failure trend line, filterable transaction detail table with CSV download |

## Project Layout

```
src/
  schemas/payments.py               Pydantic domain models (RawTransaction,
                                      TransactionSummary, MerchantRiskProfile)
  backend/
    connectors/
      protocol.py                   DataConnector protocol (PEP 544)
      validation.py                 Shared row-by-row validation + quarantine
      sis_connector.py              Snowflake (production)
      pg_connector.py               PostgreSQL (local dev)
      warehouse.py                  API ingest + warehouse load helpers
    transforms/
      daily_summary.py              Aggregation (merchant × day)
      risk_metrics.py               Sharpe, Sortino, VaR, drawdown, rolling
      alert_models.py               AlertConfig, AlertResult, AlertSeverity
      alert_engine.py               Threshold evaluation
      pipeline.py                   Orchestrator (extract → transform → alert → risk)
  frontend/
    app.py                          Streamlit composition root (tabbed layout)
    components/
      alert_banner.py               Severity-coloured banner
      charts.py                     Plotly transaction charts (3 charts)
      failure_analysis.py           Failure reason breakdown, trend, detail table
      risk_dashboard.py             Risk analytics: Plotly scatter, table, download
      seaborn_charts.py             Risk analytics: Seaborn heatmap, VaR histogram
db/
  schema.sql                        PostgreSQL DDL with CHECK constraints
  seed.py                           Bootcamp CSV → PostgreSQL with validation
tests/                              142 tests across 9 test files (99% coverage)
```

## Data Validation (seed.py)

Before insertion, `seed.py` enforces:
- No NULL values in required fields
- No duplicate `transaction_id` values
- `amount > 0`
- FAILED status requires `failure_reason`
- `ON CONFLICT DO NOTHING` as a database-level safety net

## Data Sources

| Mode | Entrypoint | Data | Use Case |
|------|-----------|------|----------|
| Mock | `make run` | Synthetic in-memory | Fast iteration |
| PostgreSQL | `make run-pg` | Bootcamp CSVs in local DB | Local dev, demos |
| Snowflake | `app.py` direct | Production warehouse | Deployment |

## Troubleshooting

**NumPy import error** (`libstdc++.so.6`): `./bootstrap.sh`

**PostgreSQL won't start**: `cat .pgdata/log` — then `make db-reset`

**Connection refused**: PostgreSQL uses a Unix socket in `/tmp/cardstream-pg`
on port 5433 (not TCP localhost:5432).  Verify with `echo $DATABASE_URL`
inside `nix develop`.

**Stale venv after flake/pyproject change**: `rm -rf .venv && nix develop`
