# CardStream
  End-to-end payments analytics pipeline for credit card transaction data — Pydantic validation at the border, pure transform functions, Snowflake-native Python, and a Streamlit executive dashboard with real-time failure rate alerting. Built with TDD and deployed on Streamlit-in-Snowflake.



# 

Clone the repo and enter the reproducible development environment with `nix-shell` (requires [Nix](https://nixos.org/download));

dependencies are declared in `shell.nix` and installed automatically via `uv` into `.venv`. 


Run the full test suite with `make test` (54 tests, 93% coverage, no Snowflake connection required — all I/O is mocked via `conftest.py` fixtures). 

To preview the dashboard locally against synthetic credit card data, run `make run`, which launches Streamlit at `http://localhost:8501` with a seeded mock session simulating 10 merchants over 30 days including engineered failure-rate anomalies. 

For production deployment, upload `src/` to a Snowflake Streamlit-in-Snowflake workspace — `app.py` calls `get_active_session()` at the app boundary and requires `PAYMENTS_DB.ANALYTICS.RAW_TRANSACTIONS` to exist (DDL in `specs/`); 

all secrets are managed through Snowflake's native secret store, not `.streamlit/secrets.toml`.
