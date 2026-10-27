-- One row per rejected source record, with the reason it was rejected.
CREATE TABLE IF NOT EXISTS dw.rejection_log (
    rejection_key  SERIAL PRIMARY KEY,
    source         VARCHAR(10) NOT NULL,
    invoice_no     VARCHAR(20),
    stock_code     VARCHAR(20),
    reason         VARCHAR(40) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rejection_log_reason ON dw.rejection_log (source, reason);
