-- One row per valid sales invoice line (quantity > 0, unit_price > 0).
CREATE TABLE IF NOT EXISTS dw.fact_sales (
    sales_key       SERIAL PRIMARY KEY,
    invoice_no      VARCHAR(20)   NOT NULL,
    date_key        INTEGER       NOT NULL REFERENCES dw.dim_date (date_key),
    product_key     INTEGER       NOT NULL REFERENCES dw.dim_product (product_key),
    customer_key    INTEGER       NOT NULL REFERENCES dw.dim_customer (customer_key),
    country_key     INTEGER       NOT NULL REFERENCES dw.dim_country (country_key),
    invoice_ts_utc  TIMESTAMPTZ   NOT NULL,
    quantity        INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    gross_revenue   NUMERIC(12,2) NOT NULL
);

-- One row per return or stock adjustment line (original quantity <= 0).
-- quantity and amount are stored as positive values so net = gross - returns.
CREATE TABLE IF NOT EXISTS dw.fact_returns (
    return_key      SERIAL PRIMARY KEY,
    invoice_no      VARCHAR(20)   NOT NULL,
    date_key        INTEGER       NOT NULL REFERENCES dw.dim_date (date_key),
    product_key     INTEGER       NOT NULL REFERENCES dw.dim_product (product_key),
    customer_key    INTEGER       NOT NULL REFERENCES dw.dim_customer (customer_key),
    country_key     INTEGER       NOT NULL REFERENCES dw.dim_country (country_key),
    invoice_ts_utc  TIMESTAMPTZ   NOT NULL,
    return_type     VARCHAR(12)   NOT NULL CHECK (return_type IN ('cancellation', 'adjustment')),
    quantity        INTEGER       NOT NULL CHECK (quantity >= 0),
    unit_price      NUMERIC(10,2) NOT NULL,
    return_amount   NUMERIC(12,2) NOT NULL
);

-- One row per product per day. Net revenue nets returns of the same product on the same day.
CREATE TABLE IF NOT EXISTS dw.fact_daily_product_revenue (
    date_key       INTEGER       NOT NULL REFERENCES dw.dim_date (date_key),
    product_key    INTEGER       NOT NULL REFERENCES dw.dim_product (product_key),
    gross_revenue  NUMERIC(14,2) NOT NULL,
    return_amount  NUMERIC(14,2) NOT NULL,
    net_revenue    NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (date_key, product_key)
);

CREATE INDEX IF NOT EXISTS ix_fact_sales_date     ON dw.fact_sales (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_product  ON dw.fact_sales (product_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_customer ON dw.fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_country  ON dw.fact_sales (country_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_invoice  ON dw.fact_sales (invoice_no);
CREATE INDEX IF NOT EXISTS ix_fact_returns_date    ON dw.fact_returns (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_returns_product ON dw.fact_returns (product_key);
