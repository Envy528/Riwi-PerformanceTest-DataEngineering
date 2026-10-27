"""Read the raw sources and normalize their formatting differences."""

from pathlib import Path

import pandas as pd

# Each Kaggle file ships with a different text encoding.
ENCODINGS = {"sales": "ISO-8859-1", "history": "utf-8"}
DATE_FORMAT = "%m/%d/%Y %H:%M"


def read_source(path: Path, source: str) -> pd.DataFrame:
    """Load one raw file as text and return it with normalized columns.

    Values are read as strings first so nothing is silently coerced; invalid
    dates or numbers become NaN/NaT and are rejected later with a reason.
    """
    raw = pd.read_csv(path, encoding=ENCODINGS[source], dtype=str)
    raw = raw.drop(columns=["index"], errors="ignore")

    df = pd.DataFrame(
        {
            "invoice_no": raw["InvoiceNo"].str.strip().str.upper(),
            "stock_code": raw["StockCode"].str.strip().str.upper(),
            "description": raw["Description"]
            .str.strip()
            .str.upper()
            .str.replace(r"\s+", " ", regex=True),
            "quantity": pd.to_numeric(raw["Quantity"], errors="coerce"),
            "invoice_date_raw": raw["InvoiceDate"].str.strip(),
            "unit_price": pd.to_numeric(raw["UnitPrice"], errors="coerce"),
            # "17850.0" and "17850" are the same customer.
            "customer_id": raw["CustomerID"].str.strip().str.replace(r"\.0$", "", regex=True),
            "source_country": raw["Country"].str.strip(),
        }
    )
    df["invoice_ts_local"] = pd.to_datetime(
        df["invoice_date_raw"], format=DATE_FORMAT, errors="coerce"
    )
    df["source"] = source
    return df
