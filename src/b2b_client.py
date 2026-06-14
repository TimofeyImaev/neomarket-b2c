"""Клиент к B2B-сервису. B2C не хранит товары — каталог, остатки и резерв идут в B2B.

В тестах подменяется через app.dependency_overrides[get_b2b_client].
"""
from __future__ import annotations

from typing import Protocol

import httpx

from .config import settings
from .errors import ApiError


class B2BClient(Protocol):
    def list_products(self, *, limit: int, offset: int, q: str | None,
                      sort: str | None, filter_: dict) -> dict: ...

    def get_product(self, product_id: str) -> dict | None: ...

    def get_skus(self, sku_ids: list[str]) -> dict[str, dict]: ...

    def get_facets(self, *, category_id: str | None, filters: dict) -> dict: ...

    def reserve(self, order_id: str, items: list[dict]) -> tuple[bool, list[dict]]: ...

    def unreserve(self, order_id: str, items: list[dict] | None = None) -> bool: ...


class HttpB2BClient:
    """Реальная HTTP-реализация (server-to-server, заголовок X-Service-Key)."""

    def __init__(self, base_url: str | None = None, service_key: str | None = None):
        self._base = (base_url or settings.b2b_base_url).rstrip("/")
        self._headers = {"X-Service-Key": service_key or settings.b2b_service_key}

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base, headers=self._headers, timeout=5.0)

    def _unavailable(self) -> ApiError:
        # Канон: единый код для недоступности B2B
        return ApiError(503, "B2B_UNAVAILABLE", "Сервис товаров временно недоступен, попробуйте позже")

    def list_products(self, *, limit, offset, q, sort, filter_):
        params: dict = {"limit": limit, "offset": offset}
        if q:
            params["q"] = q
        if sort:
            params["sort"] = sort
        for k, v in (filter_ or {}).items():
            params[f"filter[{k}]"] = v
        try:
            with self._client() as c:
                r = c.get("/api/v1/public/products", params=params)
        except httpx.HTTPError:
            raise self._unavailable()
        if r.status_code >= 500:
            raise self._unavailable()
        return r.json()

    def get_product(self, product_id):
        try:
            with self._client() as c:
                r = c.post("/api/v1/public/products/batch",
                           json={"product_ids": [product_id]})
        except httpx.HTTPError:
            raise self._unavailable()
        if r.status_code == 404:
            return None
        if r.status_code >= 500:
            raise self._unavailable()
        items = r.json().get("items", [])
        return items[0] if items else None

    def get_skus(self, sku_ids):
        if not sku_ids:
            return {}
        try:
            with self._client() as c:
                r = c.post("/api/v1/skus/batch", json={"sku_ids": sku_ids})
        except httpx.HTTPError:
            raise self._unavailable()
        if r.status_code >= 500:
            raise self._unavailable()
        return {item["sku_id"]: item for item in r.json().get("items", [])}

    def get_facets(self, *, category_id, filters):
        params: dict = {}
        if category_id:
            params["category_id"] = category_id
        for k, v in (filters or {}).items():
            params[f"filters[{k}]"] = v
        try:
            with self._client() as c:
                r = c.get("/api/v1/catalog/facets", params=params)
        except httpx.HTTPError:
            raise self._unavailable()
        if r.status_code >= 500:
            raise self._unavailable()
        return r.json()

    def reserve(self, order_id, items):
        """Возвращает (ok, failed_items). failed_items проксируется из B2B без трансформации."""
        try:
            with self._client() as c:
                r = c.post("/api/v1/inventory/reserve",
                           json={"order_id": order_id, "items": items})
        except httpx.HTTPError:
            raise self._unavailable()
        if r.status_code == 200:
            return True, []
        if r.status_code == 409:
            return False, r.json().get("failed_items", [])
        raise self._unavailable()

    def unreserve(self, order_id, items=None):
        try:
            with self._client() as c:
                r = c.post("/api/v1/inventory/unreserve",
                           json={"order_id": order_id, "items": items or []})
        except httpx.HTTPError:
            return False
        return r.status_code == 200


_default_client: B2BClient = HttpB2BClient()


def get_b2b_client() -> B2BClient:
    return _default_client
