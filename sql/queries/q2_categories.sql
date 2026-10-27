-- Q2. Gross revenue by category and the share of it that was returned.
-- Only customer cancellations count as returns; stock adjustments are excluded.
WITH sales AS (
    SELECT p.category, SUM(f.gross_revenue) AS gross_revenue, SUM(f.quantity) AS units_sold
    FROM dw.fact_sales f
    JOIN dw.dim_product p ON p.product_key = f.product_key
    GROUP BY p.category
),
returns AS (
    SELECT p.category, SUM(f.return_amount) AS returned_amount, SUM(f.quantity) AS units_returned
    FROM dw.fact_returns f
    JOIN dw.dim_product p ON p.product_key = f.product_key
    WHERE f.return_type = 'cancellation'
    GROUP BY p.category
)
SELECT
    s.category,
    s.gross_revenue,
    COALESCE(r.returned_amount, 0) AS returned_amount,
    ROUND(100.0 * COALESCE(r.returned_amount, 0) / s.gross_revenue, 2) AS return_rate_pct,
    s.units_sold,
    COALESCE(r.units_returned, 0) AS units_returned
FROM sales s
LEFT JOIN returns r ON r.category = s.category
ORDER BY s.gross_revenue DESC;
