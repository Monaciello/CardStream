"""PostgreSQL Connector — DataConnector implementation for local development.

Production uses Snowflake (SiSConnector).  Local dev uses PostgreSQL.
Both satisfy the same DataConnector protocol, so ``app.py`` is agnostic.
"""
from __future__ import annotations

import logging
from typing import TypeVar

import pandas as pd
from sqlalchemy import Engine

from src.backend.connectors.validation import validate_dataframe

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PgConnector:
    """Wraps a SQLAlchemy Engine.  Single public method: ``query_validated``."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def query_validated(
        self,
        sql: str,
        schema: type[T],
    ) -> list[T]:
        """Execute *sql* via ``pd.read_sql``, validate rows against *schema*."""
        logger.info("Executing SQL against PostgreSQL: %s", sql[:100])
        df = pd.read_sql(sql, self._engine)
        logger.info("Retrieved %d rows from PostgreSQL", len(df))
        return validate_dataframe(df, schema)
