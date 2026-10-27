"""Mock of DataMart's legacy product catalog, exposed as a small REST API."""

import csv
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

CATALOG_FILE = Path(__file__).resolve().parents[2] / "data" / "products.csv"
MAX_PAGE_SIZE = 1000


class Product(BaseModel):
    stock_code: str
    name: str
    category: str
    supplier_country: str
    status: str


class ProductPage(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[Product]


def load_catalog(path: Path) -> dict[str, Product]:
    with path.open(encoding="utf-8", newline="") as file:
        return {row["stock_code"]: Product(**row) for row in csv.DictReader(file)}


CATALOG = load_catalog(CATALOG_FILE)
CODES = sorted(CATALOG)

app = FastAPI(title="DataMart Catalog API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "products": len(CATALOG)}


@app.get("/products", response_model=ProductPage)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=MAX_PAGE_SIZE),
) -> ProductPage:
    """Return the catalog ordered by stock code, one page at a time."""
    total_pages = max(1, math.ceil(len(CODES) / page_size))
    if page > total_pages:
        raise HTTPException(status_code=404, detail=f"Page {page} does not exist")

    start = (page - 1) * page_size
    items = [CATALOG[code] for code in CODES[start : start + page_size]]
    return ProductPage(
        page=page,
        page_size=page_size,
        total_items=len(CODES),
        total_pages=total_pages,
        items=items,
    )


@app.get("/products/{stock_code}", response_model=Product)
def get_product(stock_code: str) -> Product:
    """Return one product; codes are matched in upper case without spaces."""
    product = CATALOG.get(stock_code.strip().upper())
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {stock_code} not found")
    return product
