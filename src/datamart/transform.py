"""Apply DataMart's business rules and build the dimensional model."""

import re

import pandas as pd

from datamart.categories import classify

SOURCE_TIMEZONE = "America/Bogota"
PRODUCT_CODE_PATTERN = r"^\d{5}[A-Z]{0,2}$"
GUEST_CUSTOMER = "GUEST"
UNKNOWN_DESCRIPTION = "UNKNOWN"

# Columns that identify one transaction line, regardless of the source file.
RECORD_KEY = [
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date_raw",
    "unit_price",
    "customer_id",
    "source_country",
]


def _rejections(df: pd.DataFrame, reason: str) -> pd.DataFrame:
    return df[["source", "invoice_no", "stock_code"]].assign(reason=reason)


def deduplicate(sales: pd.DataFrame, history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop exact duplicates within each source, then rows already present in sales.

    When the same line exists in both files, the sales copy is kept.
    """
    rejected = []
    unique_by_source = []
    for df in (sales, history):
        is_dup = df.duplicated(subset=RECORD_KEY, keep="first")
        rejected.append(_rejections(df[is_dup], "duplicate_in_source"))
        unique_by_source.append(df[~is_dup])

    unique_sales, unique_history = unique_by_source
    in_sales = unique_history.merge(
        unique_sales[RECORD_KEY], on=RECORD_KEY, how="left", indicator=True
    )["_merge"].eq("both").to_numpy()
    rejected.append(_rejections(unique_history[in_sales], "duplicate_across_sources"))

    combined = pd.concat([unique_sales, unique_history[~in_sales]], ignore_index=True)
    return combined, pd.concat(rejected, ignore_index=True)


def validate(df: pd.DataFrame, country_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reject records that break a business rule; each record gets its first failing reason."""
    is_sale = df["quantity"] > 0
    rules = [
        ("invalid_date", df["invoice_ts_local"].isna()),
        ("invalid_number", df["quantity"].isna() | df["unit_price"].isna()),
        ("missing_stock_code", df["stock_code"].isna() | df["stock_code"].eq("")),
        ("non_product_code", ~df["stock_code"].fillna("").str.match(PRODUCT_CODE_PATTERN)),
        ("non_positive_price", is_sale & (df["unit_price"] <= 0)),
        ("unmapped_country", ~df["source_country"].isin(country_map["source_country"])),
    ]

    remaining = pd.Series(True, index=df.index)
    rejected = []
    for reason, failed in rules:
        hit = remaining & failed
        rejected.append(_rejections(df[hit], reason))
        remaining &= ~hit
    return df[remaining].copy(), pd.concat(rejected, ignore_index=True)


def enrich(df: pd.DataFrame, country_map: pd.DataFrame) -> pd.DataFrame:
    """Add UTC timestamps, DataMart country, customer flag and transaction type."""
    out = df.merge(country_map, on="source_country", how="left")
    out["invoice_ts_utc"] = (
        out["invoice_ts_local"].dt.tz_localize(SOURCE_TIMEZONE).dt.tz_convert("UTC")
    )
    out["date_key"] = out["invoice_ts_utc"].dt.strftime("%Y%m%d").astype(int)
    out["is_identified"] = out["customer_id"].notna()
    out["customer_id"] = out["customer_id"].fillna(GUEST_CUSTOMER)

    # Business rule: quantity <= 0 is a return or adjustment, never a sale.
    out["line_type"] = "sale"
    is_return = out["quantity"] <= 0
    out.loc[is_return & out["invoice_no"].str.startswith("C"), "line_type"] = "cancellation"
    out.loc[is_return & ~out["invoice_no"].str.startswith("C"), "line_type"] = "adjustment"
    return out


def build_products(df: pd.DataFrame, patterns: dict[str, re.Pattern]) -> pd.DataFrame:
    """One row per stock code with its canonical name, category and name variants.

    Canonical name: the most frequent description among sales lines (falling
    back to all lines for products that were never sold); ties go to the most
    recent description.
    """
    named = df.dropna(subset=["description"])
    sales_named = named[named["line_type"] == "sale"]
    pool = pd.concat(
        [sales_named, named[~named["stock_code"].isin(sales_named["stock_code"])]]
    )
    ranked = (
        pool.groupby(["stock_code", "description"])
        .agg(lines=("description", "size"), last_seen=("invoice_ts_utc", "max"))
        .reset_index()
        .sort_values(
            ["stock_code", "lines", "last_seen", "description"],
            ascending=[True, False, False, True],
        )
        .drop_duplicates("stock_code")
    )

    products = pd.DataFrame({"stock_code": sorted(df["stock_code"].unique())})
    products = products.merge(ranked[["stock_code", "description"]], on="stock_code", how="left")
    products["description"] = products["description"].fillna(UNKNOWN_DESCRIPTION)
    products["category"] = products["description"].map(lambda d: classify(d, patterns))

    variants = named.groupby("stock_code")["description"].nunique()
    products["description_variants"] = (
        products["stock_code"].map(variants).fillna(0).astype(int)
    )
    products.insert(0, "product_key", range(1, len(products) + 1))
    return products


def build_model(
    sales: pd.DataFrame,
    history: pd.DataFrame,
    country_map: pd.DataFrame,
    patterns: dict[str, re.Pattern],
) -> dict[str, pd.DataFrame]:
    """Run the full transformation and return one DataFrame per destination table."""
    combined, dup_rejections = deduplicate(sales, history)
    valid, rule_rejections = validate(combined, country_map)
    lines = enrich(valid, country_map)

    countries = (
        country_map[["country_code", "country_name"]]
        .drop_duplicates()
        .sort_values("country_code")
        .reset_index(drop=True)
    )
    countries.insert(0, "country_key", range(1, len(countries) + 1))

    customers = (
        lines[["customer_id", "is_identified"]]
        .drop_duplicates("customer_id")
        .sort_values("customer_id")
        .reset_index(drop=True)
    )
    customers.insert(0, "customer_key", range(1, len(customers) + 1))

    products = build_products(lines, patterns)

    lines = (
        lines.merge(countries[["country_key", "country_code"]], on="country_code")
        .merge(customers[["customer_key", "customer_id"]], on="customer_id")
        .merge(products[["product_key", "stock_code"]], on="stock_code")
        .sort_values(["invoice_ts_utc", "invoice_no", "stock_code", "quantity", "unit_price"])
        .reset_index(drop=True)
    )
    fact_keys = ["invoice_no", "date_key", "product_key", "customer_key", "country_key", "invoice_ts_utc"]

    sales_lines = lines[lines["line_type"] == "sale"]
    fact_sales = sales_lines[fact_keys + ["quantity", "unit_price"]].copy()
    fact_sales["gross_revenue"] = (fact_sales["quantity"] * fact_sales["unit_price"]).round(2)
    fact_sales.insert(0, "sales_key", range(1, len(fact_sales) + 1))

    return_lines = lines[lines["line_type"] != "sale"]
    fact_returns = return_lines[fact_keys + ["line_type", "quantity", "unit_price"]].copy()
    fact_returns = fact_returns.rename(columns={"line_type": "return_type"})
    # Stored as positive values so net revenue = gross - returns.
    fact_returns["quantity"] = fact_returns["quantity"].abs()
    fact_returns["return_amount"] = (fact_returns["quantity"] * fact_returns["unit_price"]).round(2)
    fact_returns.insert(0, "return_key", range(1, len(fact_returns) + 1))

    gross = fact_sales.groupby(["date_key", "product_key"])["gross_revenue"].sum()
    returned = fact_returns.groupby(["date_key", "product_key"])["return_amount"].sum()
    daily = (
        pd.concat([gross, returned], axis=1)
        .fillna(0)
        .reset_index()
        .sort_values(["date_key", "product_key"])
    )
    daily["net_revenue"] = daily["gross_revenue"] - daily["return_amount"]
    daily[["gross_revenue", "return_amount", "net_revenue"]] = daily[
        ["gross_revenue", "return_amount", "net_revenue"]
    ].round(2)

    rejections = (
        pd.concat([dup_rejections, rule_rejections], ignore_index=True)
        .sort_values(["source", "reason", "invoice_no", "stock_code"], na_position="last")
        .reset_index(drop=True)
    )
    rejections.insert(0, "rejection_key", range(1, len(rejections) + 1))

    return {
        "dim_country": countries,
        "dim_customer": customers,
        "dim_product": products,
        "fact_sales": fact_sales,
        "fact_returns": fact_returns,
        "fact_daily_product_revenue": daily,
        "rejection_log": rejections,
    }
