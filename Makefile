.PHONY: test lint typecheck all run run-pg
.PHONY: db-init db-start db-stop db-seed db-reset

PGDIR  := $(CURDIR)/.pgdata
PGSOCK := /tmp/cardstream-pg
PGPORT := 5433
PGOPTS := -k $(PGSOCK) -p $(PGPORT)

# ── Quality ──────────────────────────────────────────────────────────

test:
	pytest -v

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

all: lint typecheck test

# ── Run ──────────────────────────────────────────────────────────────

run:
	streamlit run run_local.py

run-pg:
	streamlit run run_local_pg.py

# ── PostgreSQL ───────────────────────────────────────────────────────
# Data lives in .pgdata/; socket lives in /tmp/cardstream-pg so that
# `nix develop -c` never encounters a Unix socket in the source tree.

db-init: $(PGDIR)/PG_VERSION
	@mkdir -p $(PGSOCK)
	@pg_ctl -D $(PGDIR) -l $(PGDIR)/log start -w -o "$(PGOPTS)" 2>/dev/null || true
	@sleep 1
	@createdb -h $(PGSOCK) -p $(PGPORT) cardstream 2>/dev/null || true
	@psql -h $(PGSOCK) -p $(PGPORT) cardstream -f db/schema.sql
	@echo "Database initialized"

$(PGDIR)/PG_VERSION:
	@initdb -D $(PGDIR)
	@echo "unix_socket_directories = '$(PGSOCK)'" >> $(PGDIR)/postgresql.conf
	@echo "port = $(PGPORT)"                      >> $(PGDIR)/postgresql.conf
	@echo "listen_addresses = ''"                  >> $(PGDIR)/postgresql.conf

db-start:
	@mkdir -p $(PGSOCK)
	@pg_ctl -D $(PGDIR) -l $(PGDIR)/log start -w -o "$(PGOPTS)"

db-stop:
	@pg_ctl -D $(PGDIR) stop -m fast

db-seed:
	@python db/seed.py

db-reset:
	@-pg_ctl -D $(PGDIR) stop -m fast 2>/dev/null || true
	@rm -rf $(PGDIR) $(PGSOCK)
	@$(MAKE) db-init
	@$(MAKE) db-seed
