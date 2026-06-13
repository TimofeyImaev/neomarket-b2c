"""Каталог B2C по канон-flow b2c-1. B2C проксирует запросы к B2B."""
from fastapi import APIRouter, Depends, Query, Request

from ..b2b_client import B2BClient, get_b2b_client
from ..errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["Catalog"])

# Сортировки из канон-flow b2c-1
ALLOWED_SORT = ["rating", "popularity", "price_asc", "price_desc", "date_desc", "discount_desc"]


def _parse_filters(request: Request) -> dict:
    """deepObject-стиль канона: ?filters[brand]=Apple&filters[color]=black"""
    out: dict = {}
    for raw_key, value in request.query_params.multi_items():
        if raw_key.startswith("filters[") and raw_key.endswith("]"):
            out[raw_key[len("filters["):-1]] = value
    return out


@router.get("/products")
def list_products(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=255),
    category_id: str | None = Query(default=None),
    sort: str = Query(default="rating"),
    b2b: B2BClient = Depends(get_b2b_client),
):
    if sort not in ALLOWED_SORT:
        raise ApiError(400, "INVALID_REQUEST",
                       "Invalid sort parameter. Allowed: " + ", ".join(ALLOWED_SORT))
    filters = _parse_filters(request)
    if category_id:
        filters.setdefault("category_id", category_id)
    return b2b.list_products(limit=limit, offset=offset, q=search, sort=sort, filter_=filters)


@router.get("/catalog/facets")
def catalog_facets(
    request: Request,
    category_id: str | None = Query(default=None),
    b2b: B2BClient = Depends(get_b2b_client),
):
    filters = _parse_filters(request)
    return b2b.get_facets(category_id=category_id, filters=filters)
