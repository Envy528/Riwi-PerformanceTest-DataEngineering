"""Build data/seeds/country_mapping.csv from the countries found in the sales source.

Rule: United Kingdom and Australia map to Colombia. The remaining countries,
ordered by number of rows, alternate between Mexico and Peru.

Run once from the project root:
    uv run scripts/build_country_mapping.py
"""

from pathlib import Path

import pandas as pd

SOURCE = Path("data/raw/online_retail_transactions.zip")
OUTPUT = Path("data/seeds/country_mapping.csv")
COLOMBIA_SOURCES = {"United Kingdom", "Australia"}
NAMES = {"CO": "Colombia", "MX": "Mexico", "PE": "Peru"}

sales = pd.read_csv(SOURCE, encoding="ISO-8859-1", dtype=str).drop_duplicates()

rows = []
alternating_index = 0
for country in sales["Country"].value_counts().index:
    if country in COLOMBIA_SOURCES:
        code = "CO"
    else:
        code = "MX" if alternating_index % 2 == 0 else "PE"
        alternating_index += 1
    rows.append((country, code, NAMES[code]))

mapping = pd.DataFrame(rows, columns=["source_country", "country_code", "country_name"])
mapping.to_csv(OUTPUT, index=False, lineterminator="\n")
print(f"{len(mapping)} countries written to {OUTPUT}")
