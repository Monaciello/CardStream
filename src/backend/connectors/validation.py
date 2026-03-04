"""Shared row-by-row Pydantic validation with quarantine pattern.

Both SiSConnector and PgConnector delegate validation here so the
quarantine logic lives in exactly one place.
"""
from __future__ import annotations

import logging
from typing import Any, TypeVar

import pandas as pd

logger = logging.getLogger(__name__)

T = TypeVar("T")


def validate_dataframe(
    df: pd.DataFrame,
    schema: type[T],
) -> list[T]:
    """Validate each row against *schema*; quarantine failures.

    Invalid rows are logged and excluded — never raised — so that a
    small number of malformed rows don't halt the entire pipeline.

    Args:
        df: DataFrame whose columns match *schema* field names.
        schema: Pydantic model class to validate against.

    Returns:
        Only the rows that pass validation.
    """
    valid: list[T] = []
    invalid: list[dict[str, Any]] = []

    for raw in df.to_dict(orient="records"):
        record: dict[str, Any] = raw  # type: ignore[assignment]
        try:
            valid.append(schema(**record))
        except (ValueError, TypeError) as exc:
            invalid.append({"record": record, "error": str(exc)})

    if invalid:
        logger.warning(
            "%d rows failed validation — quarantined", len(invalid)
        )
        for item in invalid:
            logger.warning("  → %s", item["error"])

    return valid
