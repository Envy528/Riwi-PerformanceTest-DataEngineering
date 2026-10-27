-- Q6a. Total number of distinct product codes loaded.
SELECT COUNT(*) AS distinct_products FROM dw.dim_product;

-- Q6b. Products whose description is not consistent across transactions.
SELECT COUNT(*) AS inconsistent_products
FROM dw.dim_product
WHERE description_variants > 1;

-- Q6c. The products with the most description variants.
SELECT stock_code, description AS canonical_description, category, description_variants
FROM dw.dim_product
WHERE description_variants > 1
ORDER BY description_variants DESC, stock_code
LIMIT 20;
