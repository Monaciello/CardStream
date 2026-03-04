"""Tests for connectors: validation, ingest, and warehouse loading."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.backend.connectors.warehouse import ingest_transactions, load_to_warehouse
from src.backend.connectors.validation import validate_dataframe
from src.schemas.payments import RawTransaction


class TestValidateDataframe:

    def test_valid_rows_return_typed_objects(
        self, mock_session, transaction_dataframe,
    ):
        results = validate_dataframe(transaction_dataframe, RawTransaction)
        assert len(results) == 3
        assert all(isinstance(r, RawTransaction) for r in results)

    def test_invalid_rows_are_quarantined_not_raised(
        self, mock_session, transaction_dataframe,
    ):
        bad_row = pd.DataFrame([{
            "transaction_id": "TXN-BAD",
            "merchant_id":    "MERCH-X",
            "amount":         -999.0,
            "status":         "SUCCESS",
            "failure_reason": None,
            "txn_date":       "2025-01-15",
        }])
        mixed_df = pd.concat([transaction_dataframe, bad_row], ignore_index=True)
        results = validate_dataframe(mixed_df, RawTransaction)
        assert len(results) == 3

    def test_all_invalid_rows_returns_empty_list(self, mock_session):
        all_bad = pd.DataFrame([{
            "transaction_id": "TXN-BAD",
            "merchant_id":    "MERCH-X",
            "amount":         -1.0,
            "status":         "SUCCESS",
            "failure_reason": None,
            "txn_date":       "2025-01-15",
        }])
        results = validate_dataframe(all_bad, RawTransaction)
        assert results == []

    def test_failed_without_reason_is_quarantined(self, mock_session):
        bad_failed = pd.DataFrame([{
            "transaction_id": "TXN-F",
            "merchant_id":    "MERCH-A",
            "amount":         50.0,
            "status":         "FAILED",
            "failure_reason": None,
            "txn_date":       "2025-01-15",
        }])
        results = validate_dataframe(bad_failed, RawTransaction)
        assert results == []


class TestIngestTransactions:

    def test_returns_transaction_list_on_200(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "transactions": [
                {"transaction_id": "TXN-001", "amount": 100.0}
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch(
            "src.backend.connectors.warehouse.requests.get",
            return_value=mock_response,
        ):
            result = ingest_transactions("https://fake-api/txns", {})

        assert len(result) == 1
        assert result[0]["transaction_id"] == "TXN-001"

    def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch(
            "src.backend.connectors.warehouse.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(Exception, match="404"):
                ingest_transactions("https://fake-api/txns", {})


class TestLoadToWarehouse:

    def test_returns_dataframe_with_correct_shape(
        self, mock_session, valid_transaction_data, valid_failed_transaction_data,
    ):
        transactions = [
            RawTransaction(**valid_transaction_data),
            RawTransaction(**valid_failed_transaction_data),
        ]
        df = load_to_warehouse(mock_session, transactions)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "merchant_id" in df.columns
        assert "amount"      in df.columns
        assert "status"      in df.columns
        assert "txn_date"    in df.columns

    def test_enum_serialized_to_string(
        self, mock_session, valid_transaction_data,
    ):
        transactions = [RawTransaction(**valid_transaction_data)]
        df = load_to_warehouse(mock_session, transactions)
        assert df["status"].iloc[0] == "SUCCESS"
