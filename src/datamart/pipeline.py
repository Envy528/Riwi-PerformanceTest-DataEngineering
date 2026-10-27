"""Pipeline steps used by the Airflow DAG.

Each step reads its input from and writes its output to a staging folder, so
the DAG tasks stay small and every step can be retried on its own. The staging
folder is overwritten on every run, which keeps reruns idempotent.
"""

import logging
from pathlib import Path

import pandas as pd

from datamart.categories import load_keyword_patterns
from datamart.extract import read_source
from datamart.load import LOAD_ORDER, load_model
from datamart.quality import run_checks
from datamart.transform import build_model

log = logging.getLogger(__name__)

STAGING_DIR = "processed"
SEEDS_DIR = "seeds"


def extract(data_dir: str, file_name: str, source: str) -> int:
    """Read one raw source and stage it; return the number of rows read."""
    path = Path(data_dir) / file_name
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    df = read_source(path, source)
    if df.empty:
        raise ValueError(f"Source file is empty: {path}")

    staging = Path(data_dir) / STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)
    df.to_pickle(staging / f"{source}.pkl")
    log.info("Extracted %s rows from %s", f"{len(df):,}", path.name)
    return len(df)


def transform(data_dir: str) -> dict[str, int]:
    """Build the dimensional model from the staged sources and stage each table."""
    root = Path(data_dir)
    staging = root / STAGING_DIR
    sales = pd.read_pickle(staging / "sales.pkl")
    history = pd.read_pickle(staging / "history.pkl")

    model, metrics = build_model(
        sales,
        history,
        pd.read_csv(root / SEEDS_DIR / "country_mapping.csv"),
        load_keyword_patterns(root / SEEDS_DIR / "category_keywords.csv"),
    )
    for table, df in model.items():
        df.to_pickle(staging / f"{table}.pkl")

    for name, value in metrics.items():
        log.info("%-28s %s", name, f"{value:,}")
    return metrics


def _read_model(staging: Path) -> dict[str, pd.DataFrame]:
    return {table: pd.read_pickle(staging / f"{table}.pkl") for table in LOAD_ORDER}


def validate(data_dir: str) -> None:
    """Fail the run if any quality check does not pass."""
    staging = Path(data_dir) / STAGING_DIR
    model = _read_model(staging)
    results = run_checks(
        model,
        pd.read_pickle(staging / "sales.pkl"),
        pd.read_pickle(staging / "history.pkl"),
    )
    for name, passed in results:
        log.info("[%s] %s", "OK" if passed else "FAIL", name)

    failed = [name for name, passed in results if not passed]
    if failed:
        raise ValueError(f"Quality checks failed: {failed}")


def load(data_dir: str, connection) -> dict[str, int]:
    """Load every staged table into the warehouse in one transaction."""
    counts = load_model(connection, _read_model(Path(data_dir) / STAGING_DIR))
    for table, rows in counts.items():
        log.info("Loaded %s rows into dw.%s", f"{rows:,}", table)
    return counts
