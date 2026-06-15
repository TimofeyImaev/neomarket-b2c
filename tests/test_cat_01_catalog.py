"""US-CAT-01 — каталог с фильтрами и фасетами.

DoD-квест us-cat-01-catalog-filters: канон-flow b2c-1.
Эндпоинты: GET /api/v1/products, GET /api/v1/catalog/facets.
Имена тестов — ТОЧНО из DoD квеста.
"""
import uuid


def _seed_catalog(fake_b2b, n=3):
    items = []
    for i in range(n):
        pid = str(uuid.uuid4())
        item = {"id": pid, "title": f"Товар {i}", "image": None,
                "price": 1000000 + i, "in_stock": True, "is_in_cart": False}
        fake_b2b.products[pid] = item
        items.append(item)
    fake_b2b.list_result = {"items": items, "total_count": n, "limit": 20, "offset": 0}


# --- DoD scenarios ---

def test_catalog_returns_filtered_sorted_products(app_client, fake_b2b):
    _seed_catalog(fake_b2b, 3)
    captured = {}
    orig = fake_b2b.list_products

    def spy(*, limit, offset, q, sort, filter_):
        captured.update({"sort": sort, "filter": dict(filter_)})
        return orig(limit=limit, offset=offset, q=q, sort=sort, filter_=filter_)

    fake_b2b.list_products = spy
    r = app_client.get("/api/v1/catalog/products?category_id=cat-1&filter[brand]=Apple&sort=price_asc&limit=20&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert set(["items", "total_count", "limit", "offset"]).issubset(body)
    assert body["total_count"] == 3
    # фильтр и сортировка доехали до B2B
    assert captured["sort"] == "price_asc"
    assert captured["filter"].get("brand") == "Apple"
    assert captured["filter"].get("category_id") == "cat-1"


def test_facets_return_counts_per_filter_value(app_client, fake_b2b):
    fake_b2b.facets_result = {
        "category_id": "cat-1",
        "facets": [
            {"name": "brand", "values": [
                {"value": "Apple", "count": 124},
                {"value": "Samsung", "count": 98},
            ]},
        ],
    }
    r = app_client.get("/api/v1/catalog/facets?category_id=cat-1&filter[brand]=Apple")
    assert r.status_code == 200
    body = r.json()
    assert body["facets"][0]["name"] == "brand"
    assert body["facets"][0]["values"][0]["count"] == 124


def test_invalid_sort_returns_400(app_client, fake_b2b):
    r = app_client.get("/api/v1/catalog/products?sort=cheapest")
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "INVALID_REQUEST"
    # в сообщении перечисленые допустимые значения
    assert "price_asc" in body["message"] and "new" in body["message"]


def test_b2b_unavailable_returns_502(app_client, fake_b2b):
    fake_b2b.unavailable = True
    r = app_client.get("/api/v1/catalog/products")
    assert r.status_code in (502, 503)
    assert r.json()["code"] == "B2B_UNAVAILABLE"


# --- доп. happy/edge ---

def test_catalog_is_public_no_auth_required(app_client, fake_b2b):
    _seed_catalog(fake_b2b, 1)
    assert app_client.get("/api/v1/catalog/products").status_code == 200


def test_catalog_empty_returns_empty_items(app_client, fake_b2b):
    fake_b2b.list_result = {"items": [], "total_count": 0, "limit": 20, "offset": 0}
    r = app_client.get("/api/v1/catalog/products")
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total_count"] == 0


def test_catalog_limit_over_max_returns_400(app_client, fake_b2b):
    r = app_client.get("/api/v1/catalog/products?limit=500")
    assert r.status_code == 400 and r.json()["code"] == "INVALID_REQUEST"
