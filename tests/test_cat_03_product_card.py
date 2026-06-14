"""US-CAT-03 — карточка товара покупателя. DoD-квест us-cat-03: канон-flow b2c-3.
GET /api/v1/products/{id}. Имена тестов — ТОЧНО из DoD.
"""
import uuid


def _moderated_product(pid, sku_extra=None):
    sku = {"id": str(uuid.uuid4()), "name": "256GB Black", "price": 12999000,
           "discount": 0, "active_quantity": 10, "characteristics": [],
           # запрещённые покупателю поля — сервис обязан их вырезать:
           "cost_price": 8000000, "reserved_quantity": 3}
    if sku_extra:
        sku.update(sku_extra)
    return {"id": pid, "slug": "iphone-15", "title": "iPhone 15", "description": "Флагман",
            "status": "MODERATED", "deleted": False, "images": [{"url": "/a.jpg", "ordering": 0}],
            "characteristics": [{"name": "Бренд", "value": "Apple"}], "skus": [sku]}


def test_product_card_returns_full_data_with_skus(app_client, fake_b2b):
    pid = str(uuid.uuid4())
    fake_b2b.products[pid] = _moderated_product(pid)
    r = app_client.get(f"/api/v1/catalog/products/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == pid
    assert body["title"] and body["description"]
    assert len(body["skus"]) == 1
    assert body["skus"][0]["price"] == 12999000
    assert body["skus"][0]["in_stock"] is True


def test_cost_price_absent_in_response(app_client, fake_b2b):
    pid = str(uuid.uuid4())
    fake_b2b.products[pid] = _moderated_product(pid)
    r = app_client.get(f"/api/v1/catalog/products/{pid}")
    assert r.status_code == 200
    sku0 = r.json()["skus"][0]
    assert "cost_price" not in sku0           # утечка закупочной цены недопустима
    assert "reserved_quantity" not in sku0    # утечка резерва недопустима


def test_blocked_product_returns_404(app_client, fake_b2b):
    pid = str(uuid.uuid4())
    prod = _moderated_product(pid)
    prod["status"] = "BLOCKED"
    fake_b2b.products[pid] = prod
    assert app_client.get(f"/api/v1/catalog/products/{pid}").status_code == 404


def test_sku_without_stock_is_shown_as_unavailable(app_client, fake_b2b):
    pid = str(uuid.uuid4())
    fake_b2b.products[pid] = _moderated_product(pid, sku_extra={"active_quantity": 0})
    r = app_client.get(f"/api/v1/catalog/products/{pid}")
    assert r.status_code == 200
    sku0 = r.json()["skus"][0]
    assert sku0["active_quantity"] == 0 and sku0["in_stock"] is False
