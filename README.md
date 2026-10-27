# DataMart ETL pipeline

Daily ETL for DataMart S.A.S.: two Kaggle sales files and a product catalog API go through Apache Airflow into a PostgreSQL star schema that answers the business questions in the brief.

```
data/raw/*.zip ──┐
                 ├─> Airflow DAG (extract -> transform -> validate -> load) ──> PostgreSQL (dw schema)
catalog-api ─────┘                                                                 │
                                                                     Adminer / pgAdmin / SQL queries
```

Everything runs in Docker:

| Service | What it is | URL |
|---|---|---|
| `airflow-apiserver` | Airflow UI and API | http://localhost:8080 |
| `airflow-scheduler`, `airflow-dag-processor` | Run and parse the DAGs | — |
| `airflow-db` | Airflow's own metadata database | — |
| `dw-db` | Analytical warehouse (PostgreSQL 16) | `localhost:5434` |
| `catalog-api` | Mock product catalog (FastAPI) | http://localhost:8000/docs |
| `adminer` | Web SQL client for the warehouse | http://localhost:8081 |

## Requirements

- Docker with Docker Compose v2 (4 GB of memory for Docker is enough).
- [uv](https://docs.astral.sh/uv/) to run the setup script. It installs Python by itself.
- Optional, to make the first start faster: `docker compose pull`.

## Quick start

```bash
git clone <repo-url>
cd Riwi-PerformanceTest-DataEngineering

# 1. Create .env from .env.example with fresh secrets (only once)
uv run scripts/setup_env.py

# 2. Start everything
docker compose up -d --build
```

The start takes about a minute. When it's done, `docker compose ps -a` shows `airflow-init` as `Exited (0)` and the rest as running. On startup, `airflow-init` creates the admin user, the Connections and the Variables, and `dw-db` creates every table from `sql/ddl/`. No manual step is needed.

Open http://localhost:8080 and log in with `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` from `.env`. You can change any password in `.env` before the first start.

## Check Connections and Variables

In the Airflow UI:

- **Admin → Connections**: `dw_postgres` (warehouse) and `catalog_api` (catalog API).
- **Admin → Variables**:

| Variable | Value | Purpose |
|---|---|---|
| `datamart_data_dir` | `/opt/airflow/data` | Folder with the data inside the containers |
| `datamart_sales_file` | `raw/online_retail_transactions.zip` | Daily sales file |
| `datamart_history_file` | `raw/online_retail.zip` | Historical file |
| `datamart_category_source` | `api` | `api` uses the catalog API; `static` uses keyword rules only |

To test both at once, trigger the `smoke_test` DAG: it reads a Variable and queries the warehouse through `dw_postgres`.

## Run the pipeline

The `datamart_etl` DAG runs every day at 02:00 UTC. To run it now, open it and press **Trigger**. It takes about a minute and a half:

```
extract_sales ──┐
extract_history ├─> transform ─> validate_quality ─> load_warehouse
extract_catalog ┘
```

Running it again leaves exactly the same data (see `docs/decisions.md`).

## Check the data

**Adminer** (http://localhost:8081): System `PostgreSQL`, Server `dw-db`, user and password `DW_USER` / `DW_PASSWORD`, database `datamart_dw`. Open the `dw` schema.

**pgAdmin, DBeaver or any SQL client**: host `localhost`, port `5434`, database `datamart_dw`, same user and password.

Expected row counts after a run:

| Table | Rows |
|---|---|
| `fact_sales` | 522,504 |
| `fact_returns` | 9,992 |
| `fact_daily_product_revenue` | 278,150 |
| `dim_product` | 3,911 |
| `dim_customer` | 4,363 |
| `dim_country` | 3 |
| `rejection_log` | 14,681 |

The SQL for each business question is in `sql/queries/`. Paste a file into Adminer's **SQL command** page (or your SQL client) and run it. Results and conclusions are in [`docs/business_questions.md`](docs/business_questions.md).

To see what was rejected and why:

```sql
SELECT source, reason, COUNT(*) FROM dw.rejection_log GROUP BY source, reason ORDER BY 3 DESC;
```

## Optional: verify from your machine

`scripts/verify_pipeline.py` runs the whole ETL locally against `dw-db`, checks reconciliation and business rules, loads twice and compares a hash of every table to prove idempotency:

```bash
uv sync
uv run scripts/verify_pipeline.py
```

## Project structure

```
├── docker-compose.yml        # All services
├── .env.example              # Settings template (no secrets)
├── airflow/Dockerfile        # Airflow image with the project dependencies
├── config/variables.json     # Airflow Variables loaded on startup
├── dags/
│   ├── datamart_etl.py       # Daily ETL (orchestration only)
│   └── smoke_test.py         # Checks the Connection and Variables
├── src/datamart/             # ETL logic: extract, transform, categories, catalog, quality, load
├── api/                      # Catalog API (its own uv project and container)
├── sql/
│   ├── ddl/                  # Tables, created when dw-db starts
│   └── queries/              # One query per business question
├── data/
│   ├── raw/                  # Kaggle files (zipped)
│   └── seeds/                # Country mapping and category keywords
├── scripts/                  # Setup, exploration, seed builders and verification
└── docs/                     # Decisions, business questions and data model
```

## Documentation

- [`docs/decisions.md`](docs/decisions.md): data model, ambiguous cases, idempotency and other decisions.
- [`docs/business_questions.md`](docs/business_questions.md): results for each question and the recommendation.
- [`docs/data_model.png`](docs/data_model.png): data model diagram (source in `docs/data_model.mmd`).

## Troubleshooting

- **Port already in use**: change `AIRFLOW_PORT`, `DW_PORT`, `CATALOG_API_PORT` or `ADMINER_PORT` in `.env` and run `docker compose up -d` again.
- **Changed something in `sql/ddl/`**: those scripts only run on an empty volume. Use `docker compose down -v` and start again.
- **Start from scratch**: `docker compose down -v` removes containers and data.

## Data sources

- Sales: [carrie1/ecommerce-data](https://www.kaggle.com/datasets/carrie1/ecommerce-data) (`data.csv`).
- History: [thedevastator/online-retail-transaction-data](https://www.kaggle.com/datasets/thedevastator/online-retail-transaction-data). The link in the brief was broken; this one has the same data.
