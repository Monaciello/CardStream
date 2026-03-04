"""Alert data contracts — enums and Pydantic models only.

Separated from ``alert_engine`` because models evolve with business rules
(thresholds, severity levels) while the algorithm evolves with logic.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, field_validator


class AlertSeverity(str, Enum):
    OK       = "OK"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"


class AlertConfig(BaseModel):
    """Configurable alert thresholds — always injected, never hardcoded."""

    warning_threshold:      float
    critical_threshold:     float
    min_transaction_count:  int

    @field_validator("warning_threshold", "critical_threshold")
    @classmethod
    def threshold_must_be_valid_rate(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError(f"threshold must be between 0 and 1, got {v}")
        return v

    @field_validator("min_transaction_count")
    @classmethod
    def min_count_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"min_transaction_count must be >= 1, got {v}")
        return v


class AlertResult(BaseModel):
    """Immutable output delivered to the dashboard banner and on-call."""

    severity:             AlertSeverity
    breaching_merchants:  list[str]
    human_summary:        str

    @property
    def is_actionable(self) -> bool:
        return self.severity != AlertSeverity.OK
