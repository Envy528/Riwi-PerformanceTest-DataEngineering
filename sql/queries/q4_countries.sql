-- Q4. Share of transactions by country and average ticket (gross revenue per invoice).
WITH invoices AS (
    SELECT f.invoice_no, c.country_name, SUM(f.gross_revenue) AS invoice_total
    FROM dw.fact_sales f
    JOIN dw.dim_country c ON c.country_key = f.country_key
    GROUP BY f.invoice_no, c.country_name
)
SELECT
    country_name,
    COUNT(*) AS invoices,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS invoice_share_pct,
    SUM(invoice_total) AS gross_revenue,
    ROUND(AVG(invoice_total), 2) AS avg_ticket
FROM invoices
GROUP BY country_name
ORDER BY invoices DESC;
