# Technical decisions

Notes on how the pipeline was built and why. Each decision points to the section of the brief it answers.

## Data sources

- **Both Kaggle files are the same dataset.** After normalizing three formatting differences (text encoding, `18` vs `18.0` prices, `17850` vs `17850.0` customer IDs), all 536,641 unique lines match one to one. The "history" file adds no extra years.
- **Each file has its own encoding.** Sales is ISO-8859-1 and history is UTF-8. Reading both the same way turns `£` into `Â£` and breaks matching.
- The link in the brief for the second dataset was broken; we used `thedevastator/online-retail-transaction-data`.

## Data model

Star schema in the `dw` schema (diagram: `data_model.png`). Every table has a one-line comment in `sql/ddl/` saying what one row means.

- **Facts:** `fact_sales` (one row per valid sales line), `fact_returns` (one row per return or stock adjustment) and `fact_daily_product_revenue` (one row per product per day).
- **Dimensions:** `dim_date`, `dim_product`, `dim_customer`, `dim_country`.
- **Sales and returns live in separate tables**, so they can never be mixed by accident (section 5, rule 1). Returns are stored as positive quantities and amounts, so net = gross - returns without dealing with negative numbers.
- `return_type` tells customer cancellations (invoices starting with `C`) apart from stock adjustments (negative quantities without `C`, always with price 0: "damaged", "found", "wrongly coded"...). Return rates only count cancellations.
- `fact_daily_product_revenue` stores gross and net revenue per product per day, which is what section 5, rule 5 asks for. A product can have a negative net on a day when it got returns but no sales.
- Category is a column of `dim_product` instead of its own table (no snowflake): it has no attributes of its own, and it saves a join in every query.
- `dim_date` is a fixed calendar for 2010–2011 created by the DDL. It gives month, quarter and year ready for grouping.
- Dimensions use numeric surrogate keys; the original codes (`stock_code`, `customer_id`) stay as unique columns.
- Foreign keys and `CHECK` constraints (quantity and price > 0 in sales) protect the rules at database level too.
- All amounts are rounded to 2 decimals.

## Ambiguous cases (section 5)

- **Transactions without customer ID** (24.9% of lines): kept, assigned to a single `GUEST` customer with `is_identified = false`. Dropping them would have hidden about 15% of revenue, and keeping them makes question 5 possible.
- **Different descriptions for the same code:** descriptions are trimmed and upper-cased, then the canonical name is the most frequent description among that product's sales lines (ties go to the most recent one). Most variants are warehouse notes typed into the description ("found", "wrongly coded 23343"), which only appear on lines with price 0, so they never win. `dim_product.description_variants` keeps how many versions each code had.
- **Duplicates between sources:** see below.

## Duplicates (section 5, ambiguous case 3)

- A line is identified by all its business columns (invoice, stock code, description, quantity, date, price, customer, country) after normalization. `invoice + stock code` alone is not unique: the same product can appear twice in one invoice.
- **Duplicates inside the same file** (5,268 per file) are data-quality issues, so they go to `dw.rejection_log` with reason `duplicate_in_source`.
- **Duplicates between files** (536,641) are expected: history overlaps the daily file by design. When a line exists in both, we keep the sales copy. These are not logged row by row, because they aren't errors and would make up 97% of the log. Their count shows up in the transform task log (`duplicates_across_sources`).

## Rejection log

`dw.rejection_log` keeps every record that broke a rule, with its source and reason (section 6):

| Reason | Meaning |
|---|---|
| `duplicate_in_source` | Exact repeat inside the same file |
| `non_product_code` | Stock code isn't a product (`POST`, `DOT`, `M`, `BANK CHARGES`, ...) |
| `non_positive_price` | Sale with price <= 0 (section 5, rule 2) |
| `invalid_date`, `invalid_number`, `missing_stock_code`, `unmapped_country` | Guard rails; no rows hit them with the current data |

Each record gets only its first failing reason.

## DAG and idempotency (section 6)

- `datamart_etl` runs every day at 02:00 UTC (`0 2 * * *`), with `catchup=False` and one run at a time.
- Tasks: `extract_sales` and `extract_history` (in parallel) -> `transform` -> `validate_quality` -> `load_warehouse`.
- Each task has 2 retries (1 minute apart) and a 15-minute timeout.
- Tasks pass data through a staging folder (`data/processed/`), not XCom. It's overwritten on every run.
- **Idempotency:** every run rebuilds the warehouse from the full source files. `load_warehouse` truncates the model tables and reloads them with `COPY` inside a single transaction, restarting the ID counters and inserting rows in a fixed order. Running the DAG twice gives exactly the same rows and keys; if the load fails halfway, the transaction rolls back and the previous data stays. `scripts/verify_pipeline.py` proves it by loading twice and comparing a hash of every table.
- `validate_quality` stops the run before loading if any check fails (reconciliation, no sales with quantity or price <= 0, etc.).
- Airflow Connection: `dw_postgres`. Airflow Variables: `datamart_data_dir`, `datamart_sales_file`, `datamart_history_file`.

## Currency

All amounts are kept in **GBP**, the currency of the source data, and used as the single reporting currency. The brief's problem is that managers can't compare countries because each one uses a different currency; reporting everything in one currency solves that. Converting to COP, MXN and PEN would need made-up exchange rates and would bring that problem back.

## Countries and time zone

- The source countries (38, mostly United Kingdom) were mapped to DataMart's three countries with `data/seeds/country_mapping.csv`: United Kingdom and Australia go to Colombia, and the rest alternate between Mexico and Peru by number of rows. `scripts/build_country_mapping.py` rebuilds that file. The mapping is by source country, so an invoice or customer never ends up split across countries.
- Raw timestamps are read as Bogotá time (DataMart is a Colombian company, so its production server is assumed to be there) and converted to UTC. Colombia has no daylight saving time, so the conversion is always +5 hours.

## Catalog API (section 4.3)

- `catalog-api` is a small FastAPI service in its own uv project (`api/`) and its own container. Endpoints: `GET /products?page=&page_size=` (paginated, up to 1,000 per page), `GET /products/{stock_code}` and `GET /health`. Interactive docs at http://localhost:8000/docs.
- Each product has its stock code, normalized name, category, supplier country and status (`active` / `discontinued`).
- DataMart has no real product master, so `scripts/build_product_catalog.py` builds the dataset the API serves (`api/data/products.csv`): name and category come from the same rules as the pipeline, status is `discontinued` when a product had no sales in the last 90 days of data, and supplier country is **synthetic** (a fixed hash of the stock code).
- The DAG reads the API address from the Airflow Connection `catalog_api`. The task `extract_catalog` downloads every page and `transform` takes each product's category from it.
- The Variable `datamart_category_source` switches between `api` (default) and `static` (keyword rules only). If the API is down, setting it to `static` keeps the pipeline running; products missing from the catalog also fall back to the keyword rules.
- Categories are assigned with keyword rules over the canonical product name. Some ambiguous names will be misclassified, and products that match no keyword go to `Other`. In a real company the category would come from the product master; here the catalog plays that role.
