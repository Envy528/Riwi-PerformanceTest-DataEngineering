# Technical decisions

Notes on how the pipeline was built and why. Each decision points to the section of the brief it answers.

## Data sources

- **Both Kaggle files are the same dataset.** After normalizing three formatting differences (text encoding, `18` vs `18.0` prices, `17850` vs `17850.0` customer IDs), all 536,641 unique lines match one to one. The "history" file adds no extra years.
- **Each file has its own encoding.** Sales is ISO-8859-1 and history is UTF-8. Reading both the same way turns `£` into `Â£` and breaks matching.
- The link in the brief for the second dataset was broken; we used `thedevastator/online-retail-transaction-data`.

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
