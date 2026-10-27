-- Q7. Evidence for the recommendation: a handful of huge orders explain most cancelled revenue.
-- Cancellations grouped by cancellation invoice, with their share of all cancelled revenue.
WITH cancellations AS (
    SELECT
        f.invoice_no,
        MIN(f.invoice_ts_utc)::DATE AS cancelled_on,
        STRING_AGG(DISTINCT p.description, ', ') AS products,
        SUM(f.quantity) AS units,
        SUM(f.return_amount) AS cancelled_amount
    FROM dw.fact_returns f
    JOIN dw.dim_product p ON p.product_key = f.product_key
    WHERE f.return_type = 'cancellation'
    GROUP BY f.invoice_no
)
SELECT
    invoice_no,
    cancelled_on,
    LEFT(products, 50) AS products,
    units,
    cancelled_amount,
    ROUND(100.0 * cancelled_amount / SUM(cancelled_amount) OVER (), 2) AS share_of_cancelled_pct,
    ROUND(100.0 * SUM(cancelled_amount) OVER (ORDER BY cancelled_amount DESC)
          / SUM(cancelled_amount) OVER (), 2) AS cumulative_pct
FROM cancellations
ORDER BY cancelled_amount DESC
LIMIT 10;
