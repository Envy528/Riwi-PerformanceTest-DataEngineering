"""Run the ETL locally against the dw-db container (DW_PORT, default 5434) and verify its results.

Checks:
  1. Reconciliation: every unique source line ends up as a sale, a return or a rejection.
  2. Business rules: no sale with quantity/price <= 0, returns stored as positives.
  3. Idempotency: loading twice produces exactly the same tables.

Run from the project root while Docker is up:
    uv run scripts/verify_pipeline.py
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd
import psycopg2

sys.path.insert(0, "src")
from datamart.categories import load_keyword_patterns  # noqa: E402
from datamart.extract import read_source  # noqa: E402
from datamart.load import LOAD_ORDER, load_model  # noqa: E402
from datamart.transform import RECORD_KEY, build_model  # noqa: E402

RAW = Path("data/raw")
SEEDS = Path("data/seeds")


def read_env(path: Path = Path(".env")) -> dict[str, str]:
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def check(label: str, ok: bool) -> bool:
    print(f"  [{'OK' if ok else 'FAIL'}] {label}")
    return ok


def table_signature(cursor) -> str:
    parts = []
    for table in LOAD_ORDER:
        cursor.execute(f"SELECT md5(string_agg(t::text, '|' ORDER BY t::text)) FROM dw.{table} t")
        parts.append(cursor.fetchone()[0] or "")
    return hashlib.md5("".join(parts).encode()).hexdigest()


def main() -> int:
    sales = read_source(RAW / "online_retail_transactions.zip", "sales")
    history = read_source(RAW / "online_retail.zip", "history")
    model = build_model(
        sales,
        history,
        pd.read_csv(SEEDS / "country_mapping.csv"),
        load_keyword_patterns(SEEDS / "category_keywords.csv"),
    )
    rejections = model["rejection_log"]
    results = []

    print("\nRow counts")
    for table, df in model.items():
        print(f"  {table:<28} {len(df):>9,}")

    print("\nRejections by source and reason")
    print(rejections.groupby(["source", "reason"]).size().to_string())

    print("\n1. Reconciliation")
    unique_lines = len(pd.concat([sales, history]).drop_duplicates(subset=RECORD_KEY))
    rule_rejections = (~rejections["reason"].str.startswith("duplicate")).sum()
    accounted = len(model["fact_sales"]) + len(model["fact_returns"]) + rule_rejections
    print(f"  unique lines: {unique_lines:,} | sales + returns + rule rejections: {accounted:,}")
    results.append(check("every unique line is accounted for", unique_lines == accounted))

    print("\n2. Business rules")
    fact_sales, fact_returns = model["fact_sales"], model["fact_returns"]
    results.append(check("no sale with quantity <= 0", (fact_sales["quantity"] > 0).all()))
    results.append(check("no sale with unit_price <= 0", (fact_sales["unit_price"] > 0).all()))
    results.append(check("returns stored as positive quantities", (fact_returns["quantity"] >= 0).all()))
    results.append(check("only 3 DataMart countries", len(model["dim_country"]) == 3))
    results.append(check("GUEST customer exists", "GUEST" in set(model["dim_customer"]["customer_id"])))

    print("\n3. Idempotency (loading twice into dw-db)")
    env = read_env()
    connection = psycopg2.connect(
        host="localhost",
        port=int(env.get("DW_PORT", "5434")),
        dbname=env["DW_DB"],
        user=env["DW_USER"],
        password=env["DW_PASSWORD"],
    )
    signatures = []
    for run in (1, 2):
        load_model(connection, model)
        with connection.cursor() as cursor:
            signatures.append(table_signature(cursor))
        print(f"  run {run} signature: {signatures[-1]}")
    connection.close()
    results.append(check("both runs produce identical tables", signatures[0] == signatures[1]))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
