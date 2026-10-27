"""Daily DataMart ETL: raw Kaggle files -> PostgreSQL star schema.

Every run rebuilds the warehouse from the full source files inside one
transaction, so running it twice with the same data gives the same result.
"""

from datetime import datetime, timedelta

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import Variable, dag, task

from datamart import pipeline

DW_CONN_ID = "dw_postgres"

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
    def transform() -> dict[str, int]:
        return pipeline.transform(Variable.get("datamart_data_dir"))

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

    [extract_sales(), extract_history()] >> transform() >> validate_quality() >> load_warehouse()


datamart_etl()
