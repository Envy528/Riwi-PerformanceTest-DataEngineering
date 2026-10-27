from airflow.sdk import dag, task, Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook


@dag(schedule=None, catchup=False, tags=["smoke"])
def smoke_test():

    @task
    def check_variables():
        data_dir = Variable.get("datamart_data_dir")
        print(f"data_dir = {data_dir}")

    @task
    def check_dw_connection():
        hook = PostgresHook(postgres_conn_id="dw_postgres")
        schemas = hook.get_records(
            "SELECT schema_name FROM information_schema.schemata"
        )
        print(schemas)

    check_variables() >> check_dw_connection()


smoke_test()