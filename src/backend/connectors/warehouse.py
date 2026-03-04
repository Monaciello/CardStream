"""Warehouse I/O helpers — ingest from external APIs, load to Snowflake.

Separated from ``sis_connector`` because these functions operate on raw
dicts and validated models, not on a Snowpark session.  They can be
tested independently and reused across different connector backends.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import requests

from src.schemas.payments import RawTransaction

logger = logging.getLogger(__name__)


def ingest_transactions(
    api_url: str,
    headers: dict[str, str],
) -> list[dict[str, Any]]:
    """Fetch raw transactions from an external API.

    Args:
        api_url: Fully-qualified endpoint URL.
        headers: HTTP headers (typically auth tokens).

    Returns:
        List of raw transaction dicts from the ``"transactions"`` key.

    Raises:
        requests.HTTPError: On non-2xx responses.
    """
    response = requests.get(api_url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()["transactions"]  # type: ignore[no-any-return]


def load_to_warehouse(
    session: Any,
    transactions: list[RawTransaction],
) -> pd.DataFrame:
    """Serialize validated rows to a DataFrame for warehouse loading.

    Args:
        session: Snowpark session (unused for serialization, kept for
            interface consistency with future write-back).
        transactions: Pre-validated ``RawTransaction`` objects.

    Returns:
        DataFrame suitable for ``session.write_pandas()`` or similar.
    """
    rows = [t.model_dump() for t in transactions]
    df = pd.DataFrame(rows)
    logger.info("Loaded %d rows → RAW_TRANSACTIONS", len(df))
    return df
