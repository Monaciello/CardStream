# PostgreSQL Local Development

## How It Works

PostgreSQL runs with data in `.pgdata/` and a Unix socket in
`/tmp/cardstream-pg` on port **5433**.
The `nix develop` shell exports `DATABASE_URL`,
`PGHOST`, `PGPORT`, and `LD_LIBRARY_PATH` automatically.

## First-Time Setup

```bash
nix develop
./bootstrap.sh
```

This removes any stale `.venv`/`.pgdata`, creates a fresh venv, initializes
PostgreSQL, and seeds ~3500 validated transactions from the bootcamp CSVs.

## Lifecycle

```bash
make db-start       # start existing server
make db-stop        # stop server
make db-seed        # (re-)seed data
make db-reset       # wipe .pgdata + reseed from scratch
```

## Data Validation

`seed.py` enforces these rules **before** INSERT:

| Rule | Layer |
|------|-------|
| No NULL required fields | Python (seed.py) |
| No duplicate transaction_ids | Python + SQL PRIMARY KEY |
| amount > 0 | Python + SQL CHECK |
| FAILED requires failure_reason | Python + SQL CHECK |
| ON CONFLICT DO NOTHING | SQL safety net |

## Data Transformation (seed.py)

| Bootcamp CSV | CardStream Column | Rule |
|-------------|------------------|------|
| `id` | `transaction_id` | `f"TXN-{id:05d}"` |
| `id_merchant` | `merchant_id` | Looked up in `merchant.csv` |
| `amount` | `amount` | Passed through (must be > 0) |
| — | `status` | 92% SUCCESS, 8% FAILED (seeded randomly) |
| — | `failure_reason` | Random choice for FAILED rows |
| `date` | `txn_date` | Remapped to last 30 days |

## Troubleshooting

**Server won't start**
```bash
cat .pgdata/log       # check the actual error
make db-reset         # nuclear option
```

**Connection refused**
```bash
echo $DATABASE_URL    # should contain host=/tmp/cardstream-pg&port=5433
echo $PGHOST          # should be /tmp/cardstream-pg
```
If either is wrong, you're running outside `nix develop`.

**NumPy / libstdc++ import error**
```bash
./bootstrap.sh        # recreates venv with LD_LIBRARY_PATH
```

## Verifying

```bash
./healthcheck.sh
# or manually:
psql -h /tmp/cardstream-pg -p 5433 cardstream -c "SELECT COUNT(*) FROM raw_transactions;"
```
