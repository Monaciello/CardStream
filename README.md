# CardStream

End-to-end payments analytics pipeline — validates credit card transaction data at the border, transforms it into merchant-level risk metrics, and presents the results in an interactive Streamlit dashboard.

**142 tests · 99% coverage · Zero network required for local development**

---

## Prerequisites

| Requirement | Why | Install |
|-------------|-----|---------|
| [Nix](https://nixos.org/download) | Declarative, reproducible dev environment — installs Python, PostgreSQL, and all dependencies automatically | `curl -L https://nixos.org/nix/install \| sh` |
| Git | Clone the repository | Pre-installed on most systems |

> Nix replaces manual `pip install`, `brew install postgres`, and virtualenv setup. One command gives every contributor the identical environment.

---

## Quick Start

```bash
git clone git@github.com:Monaciello/CardStream.git && cd CardStream
nix develop          # enters reproducible shell with all deps
./bootstrap.sh       # initializes venv + database
make run-pg          # launches dashboard → http://localhost:8501
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `make run-pg` | Dashboard against local PostgreSQL |
| `make run` | Dashboard with synthetic mock data (no database) |
| `make test` | Full test suite (142 tests, 99% coverage) |
| `make lint` | Ruff linter |
| `make typecheck` | mypy --strict |
| `make all` | lint + typecheck + test |
| `make db-reset` | Wipe and rebuild database from scratch |
| `./bootstrap.sh` | Full environment reset (venv + database) |
| `./healthcheck.sh` | Verify everything is working |

---

## Architecture

```
DataConnector (Snowflake │ PostgreSQL │ Mock)
    → query_validated(sql, RawTransaction)    # Pydantic validation at the border
    → run_pipeline(connector, sql, config)    # orchestrates all stages
        → compute_daily_summary()             # merchant × day aggregation
        → compute_risk_profiles()             # Sharpe, Sortino, VaR, drawdown
        → check_success_rate_alert()          # configurable RAG thresholds
    → Streamlit dashboard (3 tabs + sidebar filters)
```

All connectors satisfy the `DataConnector` protocol (PEP 544 structural subtyping). Swapping between Snowflake, PostgreSQL, and mock data changes one line — zero impact on transforms or dashboard.

---

## Dashboard

| Tab | What it shows |
|-----|---------------|
| **Transaction Overview** | Daily volume trend, failure rate by merchant with threshold lines, failure reason breakdown, top-10 merchants by volume |
| **Risk Analytics** | Sharpe/Sortino scatter, VaR distribution, risk heatmap, rolling success rates, downloadable risk report |
| **Failure Analysis** | Failure reason donut, failures by merchant (stacked), trend over time, filterable detail table with CSV export |

Sidebar controls (lookback window, merchant filter, alert thresholds) apply globally across all tabs.

---

## Data Validation

Every row passes two independent gates before reaching the dashboard:

1. **Database layer** — PostgreSQL `CHECK` constraint enforces `status <> 'FAILED' OR failure_reason IS NOT NULL`
2. **Application layer** — Pydantic schema validates every field (typed amounts, enum statuses, cross-field rules). Invalid rows are quarantined and logged, never silently dropped.

---

## Use Cases

| Dimension | How CardStream applies |
|-----------|----------------------|
| **Operational monitoring** | Real-time failure rate tracking by merchant with configurable alert thresholds — surface problems before clients escalate |
| **Risk assessment** | Sharpe ratio, max drawdown, and Value at Risk (95%) score each merchant's payment reliability over time |
| **Migration tracking** | Filter by merchant and date range to validate entitlement status and go-live readiness during platform migrations |
| **Executive reporting** | Self-serve dashboard designed for non-technical audiences — every chart has a one-line business takeaway |
| **Compliance evidence** | Quarantine log provides auditable record of every rejected row and the exact validation rule it violated |

---

## Secrets

Secrets are encrypted with [SOPS](https://github.com/getsops/sops) + age. The `secrets.yaml` file is safe to commit (AES-256 encrypted). `nix develop` automatically decrypts and exports secrets into the shell.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| NumPy import error (`libstdc++`) | `./bootstrap.sh` |
| PostgreSQL won't start | `cat .pgdata/log` then `make db-reset` |
| Connection refused | PostgreSQL uses Unix socket on port 5433, not TCP 5432 — verify with `echo $DATABASE_URL` inside `nix develop` |
| Stale venv after config change | `rm -rf .venv && nix develop` |

---

## Project Layout

```
src/
  schemas/payments.py            Domain models (Pydantic)
  backend/
    connectors/                  Protocol + Postgres/Snowflake/Mock connectors
    transforms/                  Pure functions: aggregation, risk, alerts, pipeline
  frontend/
    app.py                       Streamlit composition root
    components/                  Charts, alert banner, risk dashboard, failure analysis
db/
  schema.sql                     PostgreSQL DDL
  seed.py                        CSV → validated PostgreSQL rows
tests/                           142 tests across 9 files
```

---

*See [DESIGN.md](specs/DESIGN.md) for architectural decisions and [SPEC.md](specs/SPEC.md) for system behavior.*
