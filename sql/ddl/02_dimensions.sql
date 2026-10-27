-- One row per calendar day. Static calendar, never truncated by the pipeline.
CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key     INTEGER PRIMARY KEY,
    full_date    DATE        NOT NULL UNIQUE,
    year         SMALLINT    NOT NULL,
    quarter      SMALLINT    NOT NULL,
    month        SMALLINT    NOT NULL,
    month_name   VARCHAR(10) NOT NULL,
    day          SMALLINT    NOT NULL,
    day_of_week  SMALLINT    NOT NULL,
    is_weekend   BOOLEAN     NOT NULL
);

INSERT INTO dw.dim_date
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
    d::DATE,
    EXTRACT(YEAR FROM d),
    EXTRACT(QUARTER FROM d),
    EXTRACT(MONTH FROM d),
    TRIM(TO_CHAR(d, 'Month')),
    EXTRACT(DAY FROM d),
    EXTRACT(ISODOW FROM d),
    EXTRACT(ISODOW FROM d) IN (6, 7)
FROM GENERATE_SERIES('2010-01-01'::DATE, '2011-12-31'::DATE, INTERVAL '1 day') AS d
ON CONFLICT (date_key) DO NOTHING;

-- One row per DataMart country (CO, MX, PE).
CREATE TABLE IF NOT EXISTS dw.dim_country (
    country_key   SERIAL PRIMARY KEY,
    country_code  CHAR(2)     NOT NULL UNIQUE,
    country_name  VARCHAR(50) NOT NULL
);

-- One row per customer. Transactions without CustomerID share the 'GUEST' row.
CREATE TABLE IF NOT EXISTS dw.dim_customer (
    customer_key   SERIAL PRIMARY KEY,
    customer_id    VARCHAR(20) NOT NULL UNIQUE,
    is_identified  BOOLEAN     NOT NULL
);

-- One row per normalized stock code.
CREATE TABLE IF NOT EXISTS dw.dim_product (
    product_key          SERIAL PRIMARY KEY,
    stock_code           VARCHAR(20)  NOT NULL UNIQUE,
    description          VARCHAR(255) NOT NULL,
    category             VARCHAR(30)  NOT NULL,
    description_variants SMALLINT     NOT NULL
);
