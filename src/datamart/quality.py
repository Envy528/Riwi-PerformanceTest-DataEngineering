"""Data-quality checks run on the transformed model before loading it."""

import pandas as pd

from datamart.transform import RECORD_KEY


def run_checks(
    model: dict[str, pd.DataFrame], sales: pd.DataFrame, history: pd.DataFrame
) -> list[tuple[str, bool]]:
    """Return (check name, passed) for every rule the model must satisfy."""
    fact_sales = model["fact_sales"]
    fact_returns = model["fact_returns"]
    rejections = model["rejection_log"]

    unique_lines = len(pd.concat([sales, history]).drop_duplicates(subset=RECORD_KEY))
    rule_rejections = (rejections["reason"] != "duplicate_in_source").sum()
    accounted = len(fact_sales) + len(fact_returns) + rule_rejections

    return [
        ("every unique line is a sale, a return or a rejection", unique_lines == accounted),
        ("no sale with quantity <= 0", bool((fact_sales["quantity"] > 0).all())),
        ("no sale with unit_price <= 0", bool((fact_sales["unit_price"] > 0).all())),
        ("returns stored as positive quantities", bool((fact_returns["quantity"] >= 0).all())),
        ("only the 3 DataMart countries", len(model["dim_country"]) == 3),
        ("GUEST customer exists", "GUEST" in set(model["dim_customer"]["customer_id"])),
        ("fact tables are not empty", len(fact_sales) > 0 and len(fact_returns) > 0),
    ]
