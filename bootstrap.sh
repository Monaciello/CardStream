#!/usr/bin/env bash
# First-time setup (or full reset) for CardStream.
# Run inside `nix develop`.
set -euo pipefail

if [ -z "${PGDATA:-}" ]; then
    echo "Error: not inside nix develop.  Run 'nix develop' first."
    exit 1
fi

PGSOCK=/tmp/cardstream-pg
PGPORT=5433

echo "=== CardStream bootstrap ==="

# 1. Stop any running PostgreSQL, wipe state
pg_ctl -D .pgdata stop -m fast 2>/dev/null || true
rm -rf .pgdata "$PGSOCK" .venv

# 2. Recreate venv (LD_LIBRARY_PATH is already set by nix develop)
uv sync --extra dev --extra postgresql
source .venv/bin/activate
python -c "import numpy; print(f'NumPy {numpy.__version__}')"

# 3. Database
make db-init
make db-seed

# 4. Verify
COUNT=$(psql -h "$PGSOCK" -p "$PGPORT" cardstream -tAc \
    "SELECT COUNT(*) FROM raw_transactions;")
echo "Database: $COUNT transactions"

echo
echo "Ready.  Run:  make run-pg"
