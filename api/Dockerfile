FROM python:3.13-slim

RUN pip install --no-cache-dir uv==0.13.6

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data ./data

EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "catalog_api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
