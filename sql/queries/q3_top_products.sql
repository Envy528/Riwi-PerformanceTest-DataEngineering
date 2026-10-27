-- Q3a. Top 10 products by net revenue.
SELECT
    p.stock_code,
    p.description,
    p.category,
    SUM(r.gross_revenue) AS gross_revenue,
    SUM(r.return_amount) AS return_amount,
    SUM(r.net_revenue)   AS net_revenue
FROM dw.fact_daily_product_revenue r
JOIN dw.dim_product p ON p.product_key = r.product_key
GROUP BY p.stock_code, p.description, p.category
ORDER BY net_revenue DESC
LIMIT 10;

-- Q3b. Top 10 products by return rate (units cancelled / units sold).
-- Products with fewer than 100 units sold are left out so tiny volumes don't dominate.
WITH sold AS (
    SELECT product_key, SUM(quantity) AS units_sold
    FROM dw.fact_sales
    GROUP BY product_key
),
returned AS (
    SELECT product_key, SUM(quantity) AS units_returned
    FROM dw.fact_returns
    WHERE return_type = 'cancellation'
    GROUP BY product_key
)
SELECT
    p.stock_code,
    p.description,
    p.category,
    s.units_sold,
    r.units_returned,
    ROUND(100.0 * r.units_returned / s.units_sold, 2) AS return_rate_pct
FROM sold s
JOIN returned r ON r.product_key = s.product_key
JOIN dw.dim_product p ON p.product_key = s.product_key
WHERE s.units_sold >= 100
ORDER BY return_rate_pct DESC, r.units_returned DESC
LIMIT 10;
