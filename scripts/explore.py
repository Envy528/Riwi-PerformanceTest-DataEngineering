"""Profile both raw sources to support the data-quality decisions.

Run from the project root:
    uv run scripts/explore.py
"""

from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
# Each source ships with a different text encoding.
SOURCES = {
    "sales": (RAW / "online_retail_transactions.zip", "ISO-8859-1"),
    "history": (RAW / "online_retail.zip", "utf-8"),
}
PRODUCT_CODE_PATTERN = r"^\d{5}[A-Za-z]{0,2}$"
DATE_FORMAT = "%m/%d/%Y %H:%M"


def load_source(path: Path, encoding: str) -> pd.DataFrame:
    """Load a raw file as text so no value is silently coerced."""
    df = pd.read_csv(path, encoding=encoding, dtype=str)
    return df.drop(columns=["index"], errors="ignore")


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def profile(name: str, df: pd.DataFrame) -> None:
    print(f"\n{'=' * 20} {name.upper()} {'=' * 20}")
    print(f"rows: {len(df):,} | columns: {list(df.columns)}")

    section("nulls per column")
    print(df.isna().sum().to_string())

    quantity = pd.to_numeric(df["Quantity"], errors="coerce")
    price = pd.to_numeric(df["UnitPrice"], errors="coerce")
    dates = pd.to_datetime(df["InvoiceDate"], format=DATE_FORMAT, errors="coerce")

    section("ranges")
    print(f"dates:    {dates.min()} -> {dates.max()} (unparseable: {dates.isna().sum():,})")
    print(f"quantity: {quantity.min():,.0f} -> {quantity.max():,.0f}")
    print(f"price:    {price.min():,.2f} -> {price.max():,.2f}")

    section("quantity and price rules")
    cancelled = df["InvoiceNo"].str.startswith("C")
    print(f"quantity <= 0:                  {(quantity <= 0).sum():,}")
    print(f"invoices starting with 'C':     {cancelled.sum():,}")
    print(f"'C' invoices with quantity > 0: {(cancelled & (quantity > 0)).sum():,}")
    print(f"quantity <= 0 without 'C':      {(~cancelled & (quantity <= 0)).sum():,}")
    print(f"price <= 0:                     {(price <= 0).sum():,}")
    print(f"price <= 0 with quantity > 0:   {((price <= 0) & (quantity > 0)).sum():,}")
    other_prefix = df["InvoiceNo"].str.match(r"^[A-Za-z]") & ~cancelled
    print(f"invoices with another letter:   {other_prefix.sum():,}")
    print(df.loc[other_prefix, ["InvoiceNo", "StockCode", "Description", "UnitPrice"]].to_string(index=False))

    section("stock codes outside the product pattern")
    non_product = ~df["StockCode"].str.match(PRODUCT_CODE_PATTERN)
    print(f"rows: {non_product.sum():,}")
    print(df.loc[non_product, "StockCode"].str.upper().value_counts().head(20).to_string())

    section("customers")
    print(f"rows without CustomerID: {df['CustomerID'].isna().sum():,} "
          f"({df['CustomerID'].isna().mean():.1%})")
    print(f"distinct customers:      {df['CustomerID'].nunique():,}")

    section("duplicates")
    print(f"exact duplicate rows: {df.duplicated().sum():,}")

    section("products")
    codes = df["StockCode"].str.strip().str.upper()
    print(f"distinct stock codes: {codes.nunique():,}")
    descriptions = df.assign(code=codes).groupby("code")["Description"].nunique()
    inconsistent = descriptions[descriptions > 1]
    print(f"codes with more than one description: {len(inconsistent):,}")
    sample = inconsistent.sort_values(ascending=False).head(3).index
    for code in sample:
        variants = df.loc[codes == code, "Description"].value_counts().head(5)
        print(f"  {code}: {variants.to_dict()}")
    case_only = (
        df.assign(code=codes, desc=df["Description"].str.strip().str.upper())
        .groupby("code")["desc"].nunique()
    )
    print(f"codes still inconsistent after upper/strip: {(case_only > 1).sum():,}")

    section("countries (share of rows)")
    print(df["Country"].value_counts(normalize=True).head(10).map("{:.2%}".format).to_string())
    print(f"distinct countries: {df['Country'].nunique()}")


def align(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the formatting differences between sources before comparing."""
    out = df.copy()
    out["CustomerID"] = out["CustomerID"].str.replace(r"\.0$", "", regex=True)
    # "18" and "18.0" are the same price written differently.
    out["UnitPrice"] = pd.to_numeric(out["UnitPrice"]).astype(str)
    return out


def compare_sources(sales: pd.DataFrame, history: pd.DataFrame) -> None:
    print(f"\n{'=' * 20} OVERLAP {'=' * 20}")
    left = align(sales).drop_duplicates()
    right = align(history).drop_duplicates()
    merged = left.merge(right, how="outer", indicator=True)
    print(merged["_merge"].value_counts().to_string())


if __name__ == "__main__":
    frames = {name: load_source(*spec) for name, spec in SOURCES.items()}
    for name, df in frames.items():
        profile(name, df)
    compare_sources(frames["sales"], frames["history"])
