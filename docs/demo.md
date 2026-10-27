# Demo walkthrough

Every command needed to show the project end to end, starting from a fresh clone. Commands are the same on Linux and Windows unless a step says otherwise.

## 0. Prerequisites

- Docker with Docker Compose v2 (`docker compose version`).
- Git (`git --version`).
- uv (`uv --version`). If it's missing:

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 1. Clone and configure

```bash
git clone <repo-url>
cd Riwi-PerformanceTest-DataEngineering
uv run scripts/setup_env.py
```

`setup_env.py` creates `.env` from `.env.example` and fills in the Airflow secrets (and your user ID on Linux). Open `.env` if you want to change the passwords; the defaults below assume you didn't change the user names.

Optional, to make the first start faster on a slow network:

```bash
docker compose pull
```

## 2. Start everything (one command)

```bash
docker compose up -d --build
```

Check that it's ready (about a minute):

```bash
docker compose ps -a
```

`airflow-init` must show `Exited (0)`; everything else `running` or `healthy`.

| What | Where |
|---|---|
| Airflow | http://localhost:8080 (user and password: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` in `.env`) |
| Catalog API docs | http://localhost:8000/docs |
| Adminer | http://localhost:8081 |
| Warehouse for pgAdmin / DBeaver | `localhost:5434`, database `datamart_dw` |

## 3. Show the Airflow configuration

In http://localhost:8080:

1. **Admin → Connections**: `dw_postgres` and `catalog_api`.
2. **Admin → Variables**: `datamart_data_dir`, `datamart_sales_file`, `datamart_history_file`, `datamart_category_source`.
3. **Dags → smoke_test → Trigger**: both tasks go green. The log of `check_variables` prints the data folder and `check_dw_connection` lists the warehouse schemas.

## 4. Show the warehouse tables were created on startup

```bash
docker compose exec dw-db psql -U datamart -d datamart_dw -c "\dt dw.*"
```

8 tables, all empty except `dim_date`.

## 5. Show the catalog API

- http://localhost:8000/health returns `{"status":"ok","products":3911}`.
- In http://localhost:8000/docs, try `GET /products` (change `page` and `page_size` to move through the catalog; the response shows `total_pages`) and `GET /products/{stock_code}` with `85123A`.

## 6. Run the pipeline

**Dags → datamart_etl → Trigger.** Six tasks, about a minute and a half:

```
extract_sales ──┐
extract_history ├─> transform ─> validate_quality ─> load_warehouse
extract_catalog ┘
```

Useful logs to open:

- `extract_catalog`: `Fetched 3,911 products in 4 pages`.
- `transform`: batch metrics (rows read, duplicates between sources, rejected rows, sales and returns).
- `validate_quality`: every quality check with `[OK]`.
- `load_warehouse`: rows loaded per table.

Check the result:

```bash
docker compose exec dw-db psql -U datamart -d datamart_dw -c "SELECT COUNT(*) FROM dw.fact_sales"
```

Expected: `522504`.

## 7. Show idempotency

Trigger `datamart_etl` again and repeat the count. It's still `522504`, and every other table keeps the same rows and keys.

For hard proof, from the project folder (needs Docker running):

```bash
uv sync
uv run scripts/verify_pipeline.py
```

It ends with `8/8 checks passed`, including two loads with an identical hash of every table.

## 8. Show the data and the answers

**Adminer** (http://localhost:8081): System `PostgreSQL`, Server `dw-db`, Username `datamart`, Password `DW_PASSWORD` from `.env`, Database `datamart_dw`. Open the `dw` schema to browse the tables.

To answer a question: **SQL command**, paste a file from `sql/queries/`, **Execute**.

| File | Question |
|---|---|
| `q1_monthly_net_sales.sql` | Monthly net sales |
| `q2_categories.sql` | Revenue and return rate by category |
| `q3_top_products.sql` | Top 10 by net revenue and by return rate |
| `q4_countries.sql` | Transactions and average ticket by country |
| `q5_identified_vs_guest.sql` | Identified customers vs. guests |
| `q6_descriptions.sql` | Inconsistent descriptions and total products |
| `q7_recommendation.sql` | Evidence for the recommendation |

Results and conclusions: `docs/business_questions.md`.

Rejected records and their reasons:

```sql
SELECT source, reason, COUNT(*) FROM dw.rejection_log GROUP BY source, reason ORDER BY 3 DESC;
```

The same works from **pgAdmin**: host `localhost`, port `5434`, database `datamart_dw`, same user and password.

## 9. Show that the pipeline works without the API

1. **Admin → Variables → `datamart_category_source`** → change `api` to `static`.
2. Trigger `datamart_etl`. `extract_catalog` logs that the API isn't called and `transform` uses the keyword rules.
3. Set it back to `api`.

## 10. Show the data exploration

```bash
uv run scripts/explore.py
```

Prints columns, nulls, ranges, duplicates, invalid codes, countries and the overlap between both files. The findings are written up in `docs/decisions.md`.

## 11. Stop and clean up

```bash
docker compose down        # stop, keep the data
docker compose down -v     # stop and delete all data (fresh start next time)
```

## If something goes wrong

| Problem | Fix |
|---|---|
| `port is already allocated` | Change `AIRFLOW_PORT`, `DW_PORT`, `CATALOG_API_PORT` or `ADMINER_PORT` in `.env`, then `docker compose up -d` |
| A task failed | Open its log in Airflow; it retries twice on its own. After fixing, use **Clear** on the task |
| Changed something in `sql/ddl/` | `docker compose down -v` and start again (DDL only runs on an empty volume) |
| `password authentication failed` from pgAdmin | Another PostgreSQL may be using that port; check `DW_PORT` and use it in the connection |
