"""Data connectors — Protocol + implementations (Snowflake, PostgreSQL)."""

from src.backend.connectors.pg_connector import PgConnector
from src.backend.connectors.protocol import DataConnector
from src.backend.connectors.sis_connector import SiSConnector
from src.backend.connectors.validation import validate_dataframe
from src.backend.connectors.warehouse import ingest_transactions, load_to_warehouse

__all__ = [
    "DataConnector",
    "PgConnector",
    "SiSConnector",
    "ingest_transactions",
    "load_to_warehouse",
    "validate_dataframe",
]
