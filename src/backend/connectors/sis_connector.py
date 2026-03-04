"""SiS Connector — Snowflake data access behind the DataConnector protocol.

All Snowpark session management, SQL execution, and validation lives here.
Every other module receives typed Python objects and never touches Snowflake.
The session is injected, never fetched internally, so tests work without
credentials.
"""
from __future__ import annotations

import logging
from typing import Any, TypeVar

import streamlit as st

from src.backend.connectors.validation import validate_dataframe

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SiSConnector:
    """Wraps a Snowpark session.  Single public method: ``query_validated``."""

    def __init__(self, session: Any) -> None:
        self._session = session

    @st.cache_data(ttl=300)
    def query_validated(
        _self,
        sql: str,
        schema: type[T],
    ) -> list[T]:
        """Execute *sql*, validate every row against *schema*.

        Caching at this layer skips the Snowflake round-trip on repeat
        calls within the TTL window.  Transforms and dashboard components
        never cache — they receive already-cached data.
        """
        df = _self._session.sql(sql).to_pandas()
        return validate_dataframe(df, schema)
