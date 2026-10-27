"""Build api/data/products.csv, the dataset served by the mock catalog API.

DataMart has no real product master, so this stands in for one:
  - name and category come from the same rules the pipeline uses (canonical
    description + keyword categories);
  - status is "discontinued" when a product had no sales in the last 90 days
    of data, otherwise "active";
  - supplier_country is synthetic: a fixed hash of the stock code picks one
    of a few sourcing countries, so it is stable across runs.

Run once from the project root:
    uv run scripts/build_product_catalog.py
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from datamart.categories import load_keyword_patterns  # noqa: E402
from datamart.extract import read_source  # noqa: E402
from datamart.transform import build_products, deduplicate, enrich, validate  # noqa: E402

RAW = Path("data/raw")
SEEDS = Path("data/seeds")
OUTPUT = Path("api/data/products.csv")
SUPPLIER_COUNTRIES = ["China", "India", "Turkey", "United Kingdom", "Vietnam"]
ACTIVE_WINDOW_DAYS = 90


def supplier_country(stock_code: str) -> str:
    digest = int(hashlib.md5(stock_code.encode()).hexdigest(), 16)
    return SUPPLIER_COUNTRIES[digest % len(SUPPLIER_COUNTRIES)]


def main() -> None:
    country_map = pd.read_csv(SEEDS / "country_mapping.csv")
    combined, _, _ = deduplicate(
        read_source(RAW / "online_retail_transactions.zip", "sales"),
        read_source(RAW / "online_retail.zip", "history"),
    )
    valid, _ = validate(combined, country_map)
    lines = enrich(valid, country_map)

    products = build_products(lines, load_keyword_patterns(SEEDS / "category_keywords.csv"))

    sales = lines[lines["line_type"] == "sale"]
    last_sale = sales.groupby("stock_code")["invoice_ts_utc"].max()
    cutoff = lines["invoice_ts_utc"].max() - pd.Timedelta(days=ACTIVE_WINDOW_DAYS)
    is_active = products["stock_code"].map(last_sale).ge(cutoff)

    catalog = pd.DataFrame(
        {
            "stock_code": products["stock_code"],
            "name": products["description"],
            "category": products["category"],
            "supplier_country": products["stock_code"].map(supplier_country),
            "status": is_active.map({True: "active", False: "discontinued"}),
        }
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(OUTPUT, index=False, lineterminator="\n")
    print(f"{len(catalog)} products written to {OUTPUT}")
    print(catalog["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
