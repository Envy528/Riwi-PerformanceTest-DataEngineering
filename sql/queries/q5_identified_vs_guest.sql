-- Q5. Buying behaviour of identified customers vs. transactions without CustomerID (GUEST).
WITH invoices AS (
    SELECT
        cu.is_identified,
        f.invoice_no,
        COUNT(*)             AS lines,
        SUM(f.quantity)      AS units,
        SUM(f.gross_revenue) AS invoice_total
    FROM dw.fact_sales f
    JOIN dw.dim_customer cu ON cu.customer_key = f.customer_key
    GROUP BY cu.is_identified, f.invoice_no
)
SELECT
    CASE WHEN is_identified THEN 'Identified' ELSE 'Guest' END AS customer_type,
    COUNT(*) AS invoices,
    SUM(invoice_total) AS gross_revenue,
    ROUND(100.0 * SUM(invoice_total) / SUM(SUM(invoice_total)) OVER (), 2) AS revenue_share_pct,
    ROUND(AVG(invoice_total), 2) AS avg_ticket,
    ROUND(AVG(lines), 1) AS avg_lines_per_invoice,
    ROUND(SUM(invoice_total) / SUM(units), 2) AS avg_price_per_unit
FROM invoices
GROUP BY is_identified
ORDER BY is_identified DESC;
