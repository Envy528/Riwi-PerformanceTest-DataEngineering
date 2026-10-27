"""Client for the product catalog API."""

import json
import logging
from urllib.request import urlopen

import pandas as pd

log = logging.getLogger(__name__)

PAGE_SIZE = 1000
TIMEOUT_SECONDS = 30


def fetch_catalog(base_url: str) -> pd.DataFrame:
    """Download every page of /products and return them as one DataFrame."""
    items, page, total_pages = [], 1, 1
    while page <= total_pages:
        url = f"{base_url.rstrip('/')}/products?page={page}&page_size={PAGE_SIZE}"
        with urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            body = json.load(response)
        items.extend(body["items"])
        total_pages = body["total_pages"]
        page += 1

    log.info("Fetched %s products in %s pages from %s", f"{len(items):,}", total_pages, base_url)
    return pd.DataFrame(items, columns=["stock_code", "name", "category", "supplier_country", "status"])
