"""Daily DataMart ETL: raw Kaggle files -> PostgreSQL star schema.

Every run rebuilds the warehouse from the full source files inside one
transaction, so running it twice with the same data gives the same result.
"""

from datetime import datetime, timedelta

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import Connection, Variable, dag, task

from datamart import pipeline

DW_CONN_ID = "dw_postgres"
CATALOG_CONN_ID = "catalog_api"

default_args = {
    "owner": "datamart",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(minutes=15),
}


@dag(
    dag_id="datamart_etl",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["datamart", "etl"],
)
def datamart_etl():

    @task
    def extract_sales() -> int:
        return pipeline.extract(
            Variable.get("datamart_data_dir"), Variable.get("datamart_sales_file"), "sales"
        )

    @task
    def extract_history() -> int:
        return pipeline.extract(
            Variable.get("datamart_data_dir"), Variable.get("datamart_history_file"), "history"
        )

    @task
    def extract_catalog() -> int:
        if Variable.get("datamart_category_source") != "api":
            print("Category source is 'static'; the catalog API is not called.")
            return 0
        conn = Connection.get(CATALOG_CONN_ID)
        return pipeline.extract_catalog(
            Variable.get("datamart_data_dir"), f"http://{conn.host}:{conn.port}"
        )

    @task
    def transform() -> dict[str, int]:
        return pipeline.transform(
            Variable.get("datamart_data_dir"), Variable.get("datamart_category_source")
        )

    @task
    def validate_quality() -> None:
        pipeline.validate(Variable.get("datamart_data_dir"))

    @task
    def load_warehouse() -> dict[str, int]:
        connection = PostgresHook(postgres_conn_id=DW_CONN_ID).get_conn()
        try:
            return pipeline.load(Variable.get("datamart_data_dir"), connection)
        finally:
            connection.close()

    [extract_sales(), extract_history(), extract_catalog()] >> transform() >> validate_quality() >> load_warehouse()


datamart_etl()
