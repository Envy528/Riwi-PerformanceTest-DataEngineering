"""Load the dimensional model into PostgreSQL in a single transaction."""

import io

import pandas as pd

# Insert order respects foreign keys: dimensions before facts.
LOAD_ORDER = [
    "dim_country",
    "dim_customer",
    "dim_product",
    "fact_sales",
    "fact_returns",
    "fact_daily_product_revenue",
    "rejection_log",
]


def _copy(cursor, table: str, df: pd.DataFrame) -> None:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False, na_rep="\\N")
    columns = ", ".join(df.columns)
    sql = f"COPY dw.{table} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"

    # Airflow's Postgres hook returns a psycopg 3 connection; local scripts use psycopg2.
    if hasattr(cursor, "copy_expert"):
        buffer.seek(0)
        cursor.copy_expert(sql, buffer)
    else:
        with cursor.copy(sql) as copy:
            copy.write(buffer.getvalue())


def load_model(connection, model: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace the content of every model table; all or nothing.

    TRUNCATE + COPY inside one transaction makes the load idempotent: running
    it twice with the same input leaves exactly the same rows and keys.
    dim_date is a static calendar and is never truncated.
    """
    tables = ", ".join(f"dw.{name}" for name in reversed(LOAD_ORDER))
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE {tables} RESTART IDENTITY")
            for table in LOAD_ORDER:
                _copy(cursor, table, model[table])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {table: len(model[table]) for table in LOAD_ORDER}
