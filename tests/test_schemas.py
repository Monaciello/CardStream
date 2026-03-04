"""Tests for Pydantic schemas: RawTransaction and TransactionSummary."""
from __future__ import annotations

from datetime import date

import pytest

from src.schemas.payments import RawTransaction, TransactionStatus, TransactionSummary


class TestRawTransactionValid:

    def test_success_transaction_passes(self, valid_transaction_data):
        txn = RawTransaction(**valid_transaction_data)
        assert txn.transaction_id == "TXN-001"
        assert txn.status == TransactionStatus.SUCCESS
        assert txn.txn_date == date(2025, 1, 15)

    def test_failed_transaction_with_reason_passes(self, valid_failed_transaction_data):
        txn = RawTransaction(**valid_failed_transaction_data)
        assert txn.status == TransactionStatus.FAILED
        assert txn.failure_reason == "INSUFFICIENT_FUNDS"

    def test_pending_transaction_passes(self, valid_transaction_data):
        data = {**valid_transaction_data, "status": "PENDING"}
        txn = RawTransaction(**data)
        assert txn.status == TransactionStatus.PENDING

    def test_date_string_coerced_to_date(self, valid_transaction_data):
        txn = RawTransaction(**valid_transaction_data)
        assert isinstance(txn.txn_date, date)


class TestAmountValidator:

    def test_zero_amount_raises(self, valid_transaction_data):
        data = {**valid_transaction_data, "amount": 0.0}
        with pytest.raises(ValueError, match="amount must be positive"):
            RawTransaction(**data)

    def test_negative_amount_raises(self, valid_transaction_data):
        data = {**valid_transaction_data, "amount": -50.00}
        with pytest.raises(ValueError, match="amount must be positive"):
            RawTransaction(**data)

    def test_very_small_positive_passes(self, valid_transaction_data):
        data = {**valid_transaction_data, "amount": 0.01}
        txn = RawTransaction(**data)
        assert txn.amount == 0.01


class TestFailedRequiresReason:

    def test_failed_without_reason_raises(self, valid_transaction_data):
        data = {
            **valid_transaction_data,
            "status": "FAILED",
            "failure_reason": None,
        }
        with pytest.raises(ValueError, match="must include failure_reason"):
            RawTransaction(**data)

    def test_failed_with_empty_string_raises(self, valid_transaction_data):
        data = {
            **valid_transaction_data,
            "status": "FAILED",
            "failure_reason": "",
        }
        with pytest.raises(ValueError):
            RawTransaction(**data)

    def test_success_without_reason_passes(self, valid_transaction_data):
        txn = RawTransaction(**valid_transaction_data)
        assert txn.failure_reason is None


class TestTransactionStatus:

    def test_unknown_status_raises(self, valid_transaction_data):
        data = {**valid_transaction_data, "status": "REVERSED"}
        with pytest.raises(ValueError):
            RawTransaction(**data)


class TestTransactionSummary:

    def test_valid_summary_passes(self):
        summary = TransactionSummary(
            merchant_id="MERCH-A", txn_date=date(2025, 1, 15),
            total_volume=225.50, txn_count=2, failure_rate=0.5,
        )
        assert summary.failure_rate == 0.5

    def test_failure_rate_above_one_raises(self):
        with pytest.raises(ValueError, match="failure_rate must be 0"):
            TransactionSummary(
                merchant_id="MERCH-A", txn_date=date(2025, 1, 15),
                total_volume=100.0, txn_count=1, failure_rate=1.5,
            )

    def test_failure_rate_negative_raises(self):
        with pytest.raises(ValueError, match="failure_rate must be 0"):
            TransactionSummary(
                merchant_id="MERCH-A", txn_date=date(2025, 1, 15),
                total_volume=100.0, txn_count=1, failure_rate=-0.1,
            )

    def test_zero_failure_rate_passes(self):
        summary = TransactionSummary(
            merchant_id="MERCH-B", txn_date=date(2025, 1, 15),
            total_volume=200.0, txn_count=1, failure_rate=0.0,
        )
        assert summary.failure_rate == 0.0

    def test_full_failure_rate_passes(self):
        summary = TransactionSummary(
            merchant_id="MERCH-A", txn_date=date(2025, 1, 15),
            total_volume=75.50, txn_count=1, failure_rate=1.0,
        )
        assert summary.failure_rate == 1.0
