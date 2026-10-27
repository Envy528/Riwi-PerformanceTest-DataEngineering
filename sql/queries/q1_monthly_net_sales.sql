-- Q1. Monthly evolution of gross sales, returns and net sales.
SELECT
    d.year,
    d.month,
    d.month_name,
    SUM(r.gross_revenue) AS gross_revenue,
    SUM(r.return_amount) AS return_amount,
    SUM(r.net_revenue)   AS net_revenue
FROM dw.fact_daily_product_revenue r
JOIN dw.dim_date d ON d.date_key = r.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;
