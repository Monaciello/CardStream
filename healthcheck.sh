#!/usr/bin/env bash
# Quick environment health check.  Run inside `nix develop`.
set -u

PGDIR="${PGDATA:-$PWD/.pgdata}"
PGSOCK="${PGHOST:-/tmp/cardstream-pg}"
PGPORT_VAL="${PGPORT:-5433}"
OK=true

check() { "$@" 2>/dev/null; }

fail()  { echo "[FAIL] $1"; OK=false; }
warn()  { echo "[warn] $1"; }
pass()  { echo "[ ok ] $1"; }

echo "=== CardStream health check ==="

# nix develop
[ -n "${PGDATA:-}" ]         && pass "nix develop shell" || fail "not in nix develop"

# Python
[ -f .venv/bin/python ]      && pass "venv ($(.venv/bin/python --version))" || fail "venv missing"

# NumPy
check .venv/bin/python -c "import numpy" \
    && pass "numpy" || fail "numpy import"

# PostgreSQL data
[ -d "$PGDIR" ]              && pass "pgdata exists" || fail "pgdata missing"
[ -d "$PGSOCK" ]             && pass "socket dir"    || warn "socket dir missing"

# PostgreSQL running
check pg_ctl -D "$PGDIR" status \
    && pass "server running" || warn "server not running"

# Data
if COUNT=$(psql -h "$PGSOCK" -p "$PGPORT_VAL" cardstream -tAc \
    "SELECT COUNT(*) FROM raw_transactions;" 2>/dev/null); then
    [ "$COUNT" -gt 0 ] && pass "$COUNT transactions" || warn "database empty"
else
    warn "cannot query database"
fi

echo
$OK && echo "Healthy." || { echo "Issues detected."; exit 1; }
