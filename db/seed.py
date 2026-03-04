#!/usr/bin/env python3
"""Seed raw_transactions from bootcamp CSVs with validation.

Transforms bootcamp ``transaction.csv`` format::

    id, date, amount, card, id_merchant

Into CardStream ``RawTransaction`` format::

    transaction_id, merchant_id, amount, status, failure_reason, txn_date

Validation guarantees before insert:
- No NULL required fields (transaction_id, merchant_id, amount, txn_date)
- No duplicate transaction_ids
- amount > 0
- FAILED rows always have a failure_reason
- Dates remapped to last 30 days for dashboard relevance
"""
from __future__ import annotations

import csv
import logging
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import execute_batch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BOOTCAMP_ROOT = Path(__file__).parent.parent.parent / "_archived" / "bootcamp"
TRANSACTION_CSV = BOOTCAMP_ROOT / "Homework" / "07-SQL" / "Instructions" / "Data" / "transaction.csv"
MERCHANT_CSV = BOOTCAMP_ROOT / "Homework" / "07-SQL" / "Instructions" / "Data" / "merchant.csv"

FAILURE_REASONS = [
    "INSUFFICIENT_FUNDS",
    "TIMEOUT",
    "INVALID_ACCOUNT",
    "FRAUD_SUSPECTED",
    "NETWORK_ERROR",
]

FAILURE_RATE = 0.08

random.seed(42)


def load_merchant_mapping(merchant_csv: Path) -> dict[int, str]:
    """Load merchant ID -> name mapping from the bootcamp CSV."""
    mapping: dict[int, str] = {}
    with open(merchant_csv, "r") as f:
        for row in csv.DictReader(f):
            mapping[int(row["id"])] = row["name"]
    return mapping


def _build_date_map(original_dates: list[date]) -> dict[date, date]:
    """Map original CSV dates onto the last 30 days for dashboard relevance."""
    if not original_dates:
        return {}
    unique = sorted(set(original_dates))
    today = date.today()
    target_days = [today - timedelta(days=i) for i in range(30)]
    return {
        orig: target_days[i % len(target_days)]
        for i, orig in enumerate(unique)
    }


def transform_row(
    row: dict[str, str],
    merchant_map: dict[int, str],
    date_map: dict[date, date],
) -> dict[str, Any] | None:
    """Transform one bootcamp CSV row into CardStream format.

    Returns None if the row fails validation (logged, not raised).
    """
    try:
        txn_id = int(row["id"])
        amount = float(row["amount"])
        merchant_id_raw = int(row["id_merchant"])
        date_str = row["date"]

        if amount <= 0:
            logger.debug("Skipping TXN-%05d: non-positive amount %.2f", txn_id, amount)
            return None

        original_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()
        txn_date = date_map.get(original_date, date.today())
        merchant_name = merchant_map.get(merchant_id_raw, f"MERCH-{merchant_id_raw}")

        is_failed = random.random() < FAILURE_RATE
        status = "FAILED" if is_failed else "SUCCESS"
        failure_reason = random.choice(FAILURE_REASONS) if is_failed else None

        return {
            "transaction_id": f"TXN-{txn_id:05d}",
            "merchant_id": merchant_name,
            "amount": amount,
            "status": status,
            "failure_reason": failure_reason,
            "txn_date": txn_date,
        }
    except (ValueError, KeyError) as exc:
        logger.warning("Skipping invalid row: %s", exc)
        return None


def validate_batch(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove nulls in required fields, duplicates, and cross-field violations.

    Args:
        rows: Transformed dicts ready for INSERT.

    Returns:
        Deduplicated, validated rows.  Rejected rows are logged.
    """
    required_fields = ("transaction_id", "merchant_id", "amount", "status", "txn_date")

    seen_ids: set[str] = set()
    valid: list[dict[str, Any]] = []
    null_count = 0
    dup_count = 0
    xfield_count = 0

    for row in rows:
        # Null check on required fields
        if any(row.get(f) is None for f in required_fields):
            null_count += 1
            continue

        # Duplicate check
        txn_id = row["transaction_id"]
        if txn_id in seen_ids:
            dup_count += 1
            continue
        seen_ids.add(txn_id)

        # Cross-field: FAILED must have failure_reason
        if row["status"] == "FAILED" and not row.get("failure_reason"):
            xfield_count += 1
            continue

        # Amount must be positive
        if row["amount"] <= 0:
            null_count += 1
            continue

        valid.append(row)

    if null_count:
        logger.warning("Rejected %d rows with NULL required fields", null_count)
    if dup_count:
        logger.warning("Rejected %d duplicate transaction_ids", dup_count)
    if xfield_count:
        logger.warning("Rejected %d FAILED rows missing failure_reason", xfield_count)

    return valid


def seed_database(database_url: str) -> None:
    """Load bootcamp CSVs, validate, and insert into PostgreSQL."""
    logger.info("Loading merchant mapping from %s", MERCHANT_CSV)
    merchant_map = load_merchant_mapping(MERCHANT_CSV)
    logger.info("Loaded %d merchants", len(merchant_map))

    logger.info("Reading transactions from %s", TRANSACTION_CSV)

    raw_rows: list[dict[str, str]] = []
    original_dates: list[date] = []
    with open(TRANSACTION_CSV, "r") as f:
        for row in csv.DictReader(f):
            raw_rows.append(row)
            try:
                original_dates.append(
                    datetime.strptime(row["date"], "%Y-%m-%d %H:%M:%S").date()
                )
            except (ValueError, KeyError):
                pass

    date_map = _build_date_map(original_dates)

    transformed: list[dict[str, Any]] = []
    skipped = 0
    for row in raw_rows:
        result = transform_row(row, merchant_map, date_map)
        if result:
            transformed.append(result)
        else:
            skipped += 1

    logger.info("Transformed %d rows (%d skipped at parse stage)", len(transformed), skipped)

    validated = validate_batch(transformed)
    logger.info(
        "Validated %d rows (%d rejected)",
        len(validated),
        len(transformed) - len(validated),
    )

    logger.info("Connecting to %s", database_url)
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM raw_transactions")

    insert_sql = """
        INSERT INTO raw_transactions
            (transaction_id, merchant_id, amount, status, failure_reason, txn_date)
        VALUES
            (%(transaction_id)s, %(merchant_id)s, %(amount)s,
             %(status)s, %(failure_reason)s, %(txn_date)s)
        ON CONFLICT (transaction_id) DO NOTHING
    """
    execute_batch(cursor, insert_sql, validated, page_size=500)

    conn.commit()
    cursor.close()
    conn.close()

    logger.info("Seeded %d transactions successfully", len(validated))


if __name__ == "__main__":
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql:///cardstream?host=/tmp/cardstream-pg&port=5433",
    )

    if not TRANSACTION_CSV.exists():
        logger.error("Transaction CSV not found: %s", TRANSACTION_CSV)
        raise SystemExit(1)

    if not MERCHANT_CSV.exists():
        logger.error("Merchant CSV not found: %s", MERCHANT_CSV)
        raise SystemExit(1)

    seed_database(database_url)
