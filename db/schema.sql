-- CardStream PostgreSQL Schema
-- raw_transactions table matching RawTransaction Pydantic model

CREATE TABLE IF NOT EXISTS raw_transactions (
    transaction_id  VARCHAR(50)  PRIMARY KEY,
    merchant_id     VARCHAR(255) NOT NULL,
    amount          NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    status          VARCHAR(20)  NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PENDING')),
    failure_reason  VARCHAR(255),
    txn_date        DATE NOT NULL,

    -- Cross-field: FAILED rows must carry a reason
    CONSTRAINT failed_requires_reason
        CHECK (status <> 'FAILED' OR failure_reason IS NOT NULL)
);

-- Indexes for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_merchant_date ON raw_transactions(merchant_id, txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_date      ON raw_transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_status        ON raw_transactions(status);
