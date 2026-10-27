FROM apache/airflow:3.3.2
COPY pyproject.toml /tmp/pyproject.toml
RUN uv pip install --no-cache "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/pyproject.toml