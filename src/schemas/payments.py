"""Pydantic models for the payments domain."""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, field_validator, model_validator


class TransactionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED  = "FAILED"
    PENDING = "PENDING"


class RawTransaction(BaseModel):
    """Row-level contract validated immediately after ingest."""

    transaction_id:  str
    merchant_id:     str
    amount:          float
    status:          TransactionStatus
    failure_reason:  str | None = None
    txn_date:        date

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"amount must be positive, got {v}")
        return v

    @model_validator(mode="after")
    def failed_requires_reason(self) -> RawTransaction:
        if self.status == TransactionStatus.FAILED and not self.failure_reason:
            raise ValueError("FAILED transactions must include failure_reason")
        return self


class TransactionSummary(BaseModel):
    """Post-load aggregate: one row per merchant per day."""

    merchant_id:   str
    txn_date:      date
    total_volume:  float
    txn_count:     int
    failure_rate:  float

    @field_validator("failure_rate")
    @classmethod
    def rate_must_be_valid(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"failure_rate must be 0–1, got {v}")
        return v


class MerchantRiskProfile(BaseModel):
    """Risk analytics for a single merchant over a time window.

    Maps traditional financial ratios to payments performance:
    - "return" = daily success rate (1 - failure_rate)
    - "risk-free rate" = target SLA (e.g. 99% success)
    - "downside" = days where success rate < target
    """

    merchant_id:          str
    days_observed:        int
    avg_success_rate:     float
    success_rate_std:     float
    sharpe_ratio:         float | None = None
    sortino_ratio:        float | None = None
    calmar_ratio:         float | None = None
    max_drawdown:         float
    value_at_risk_95:     float
    avg_daily_volume:     float
    total_volume:         float
    risk_rating:          str
