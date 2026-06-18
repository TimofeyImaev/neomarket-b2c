"""Каталог B2C по канон-flow b2c-1/b2c-3. B2C проксирует запросы к B2B."""
from fastapi import APIRouter, Depends, Query, Request

from ..b2b_client import B2BClient, get_b2b_client
from ..errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["Catalog"])

# b2c/openapi.yaml:314 — допустимые значения sort
ALLOWED_SORT = ["price_asc", "price_desc", "popularity", "new"]


def _parse_filters(request: Request) -> dict:
    """deepObject-стиль: ?filter[brand]=Apple&filter[color]=black"""
    out: dict = {}
    for raw_key, value in request.query_params.multi_items():
        if raw_key.startswith("filter[") and raw_key.endswith("]"):
            out[raw_key[len("filter["):-1]] = value
    return out


@router.get("/catalog/products")
def list_products(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=255),
    category_id: str | None = Query(default=None),
    sort: str = Query(default="popularity"),
    b2b: B2BClient = Depends(get_b2b_client),
):
    if sort not in ALLOWED_SORT:
        raise ApiError(400, "INVALID_REQUEST",
                       "Invalid sort parameter. Allowed: " + ", ".join(ALLOWED_SORT))
    filters = _parse_filters(request)
    if category_id:
        filters.setdefault("category_id", category_id)
    return b2b.list_products(limit=limit, offset=offset, q=search, sort=sort, filter_=filters)


# Поля SKU, разрешённые покупателю (канон b2c-3). cost_price и reserved_quantity ИСКЛЮЧЕНЫ.
def _serialize_sku(sku: dict) -> dict:
    active = sku.get("active_quantity", 0)
    return {
        "id": sku.get("id"),
        "name": sku.get("name"),
        "price": sku.get("price"),
        "discount": sku.get("discount", 0),
        "image": sku.get("image"),
        "active_quantity": active,
        "in_stock": active > 0,
        "characteristics": sku.get("characteristics", []),
    }


def _serialize_card(product: dict) -> dict:
    """Whitelist полей карточки для покупателя — защита от утечки данных продавца."""
    return {
        "id": product.get("id"),
        "slug": product.get("slug"),
        "title": product.get("title"),
        "description": product.get("description"),
        "images": product.get("images", []),
        "status": product.get("status"),
        "characteristics": product.get("characteristics", []),
        "skus": [_serialize_sku(s) for s in product.get("skus", [])],
    }


@router.get("/catalog/products/{product_id}")
def get_product(product_id: str, b2b: B2BClient = Depends(get_b2b_client)):
    product = b2b.get_product(product_id)
    if product is None or product.get("status") not in (None, "MODERATED") or product.get("deleted"):
        raise ApiError(404, "NOT_FOUND", "Product not found")
    return _serialize_card(product)


@router.get("/catalog/facets")
def catalog_facets(
    request: Request,
    category_id: str | None = Query(default=None),
    b2b: B2BClient = Depends(get_b2b_client),
):
    filters = _parse_filters(request)
    return b2b.get_facets(category_id=category_id, filters=filters)
