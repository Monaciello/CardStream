# Contributing Guide

## Prerequisites

- [Nix](https://nixos.org/download) (flakes enabled)
- Git
- Age key for SOPS (see [secrets.md](secrets.md))

## Setup

```bash
git clone git@github.com:Monaciello/CardStream.git
cd CardStream
nix develop
./bootstrap.sh
```

## Workflow

```bash
make all         # lint, typecheck, test
make run         # dashboard w/ mock data
make run-pg      # dashboard + Postgres
```

## Quality Gates

| Command         | Tool         | What It Checks              |
|-----------------|-------------|-----------------------------|
| make lint       | ruff        | Imports, unused, style      |
| make typecheck  | mypy        | Static type checking        |
| make test       | pytest      | 99%+ coverage, all tests    |

---

## New Features

### Connector

1. Add `src/backend/connectors/your_connector.py`
2. Implement:

   ```python
   class YourConnector:
       def query_validated(self, sql: str, schema: type[T]) -> list[T]:
           df = ...
           return validate_dataframe(df, schema)
   ```
3. No inheritance needed, just match method
4. Register in `__init__.py`
5. Test in `tests/test_your_connector.py`
6. Optionally create an entrypoint script

### Chart

1. Add `_render_your_chart(df, ...)` to the right frontend file
2. Call from parent `render_*`
3. Test (function runs) in `tests/test_render_components.py`

### Risk Metric

1. Update `_compute_single_profile()` in `risk_metrics.py`
2. Add to `MerchantRiskProfile`
3. Update `_classify_risk()` if needed
4. Test in `tests/test_risk_metrics.py`
5. Add to dashboard and `data-dictionary.md`

### Sidebar Filter

1. Add widget in `app.py` sidebar section
2. Apply in "Apply filters"
3. All tabs get filtered data

### Dashboard Tab

1. Create `src/frontend/components/your_tab.py` with `render_your_tab(...)`
2. Register in `__init__.py`
3. Add as tab in `app.py`
4. Test in `tests/test_render_components.py`
5. Update `README.md`/`specs/SPEC.md`

---

## Project Layout

```
src/
  schemas/payments.py         # Pydantic models
  backend/
    connectors/              # Data sources
    transforms/              # Aggregations/transforms
  frontend/
    app.py                   # Streamlit root
    components/              # UI
tests/                       # 9+ test files, 140+ tests
docs/                        # Guides, architecture
specs/                       # SPEC, DESIGN
db/                          # DB schema, seeds
```

## Code Style

- PEP 8 (ruff)
- PEP 257 (docstrings)
- PEP 604 (`X | None`)
- PEP 544 (protocols)
- Full typing (`mypy --strict`)
- No useless comments
