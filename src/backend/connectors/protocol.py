"""DataConnector Protocol — structural subtyping for data sources.

Any class with a matching ``query_validated`` signature satisfies this
contract without inheriting from DataConnector.  Tests pass a
MockConnector, production uses SiSConnector, local dev uses PgConnector.
"""
from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class DataConnector(Protocol):
    """Interface for querying and validating data into typed objects."""

    def query_validated(
        self,
        sql: str,
        schema: type[T],
    ) -> list[T]: ...
