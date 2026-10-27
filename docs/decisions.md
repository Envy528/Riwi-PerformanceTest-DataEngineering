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
