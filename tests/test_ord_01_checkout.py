"""US-ORD-01 — checkout. DoD-квест us-ord-01-checkout: канон-flow b2c-9.
POST /api/v1/orders, заголовок Idempotency-Key, тело {items, delivery_address?}.
Имена тестов — ТОЧНО из DoD квеста.
"""
import uuid

from tests.conftest import auth_headers, register_buyer


def _order_body(sku_id, qty=2):
    return {"items": [{"sku_id": sku_id, "quantity": qty}],
            "delivery_address": "г. Екатеринбург, ул. Мира 19"}


def _idem_header(key=None):
    return {"Idempotency-Key": key or str(uuid.uuid4())}


# --- DoD scenarios ---

def test_checkout_creates_paid_order_with_fixed_prices(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=12999000, available=10)
    r = app_client.post("/api/v1/orders",
                        headers={**auth_headers(token), **_idem_header()},
                        json=_order_body(sku, qty=2))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PAID"
    assert body["total_amount"] == 12999000 * 2
    item = body["items"][0]
    assert item["unit_price"] == 12999000  # цена зафиксирована в OrderItem
    assert item["line_total"] == 12999000 * 2
    assert item["product_title"] and "sku_name" in item
    assert fake_b2b.reserved, "reserve должен быть вызван (all-or-nothing)"

    # цена в B2B изменилась после оформления — в заказе остаётся прежняя
    fake_b2b.skus[sku]["price"] = 99999999
    got = app_client.get(f"/api/v1/orders/{body['id']}", headers=auth_headers(token)).json()
    assert got["items"][0]["unit_price"] == 12999000


def test_partial_reserve_failure_returns_409(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=1000, available=10)
    fake_b2b.reserve_ok = False  # хотя бы один SKU не зарезервирован
    r = app_client.post("/api/v1/orders",
                        headers={**auth_headers(token), **_idem_header()},
                        json=_order_body(sku))
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "RESERVE_FAILED"
    assert "failed_items" in body and isinstance(body["failed_items"], list)


def test_idempotency_returns_existing_order(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=1000, available=10)
    key = str(uuid.uuid4())
    idem = _idem_header(key)
    body = _order_body(sku, qty=1)
    r1 = app_client.post("/api/v1/orders", headers={**auth_headers(token), **idem}, json=body)
    r2 = app_client.post("/api/v1/orders", headers={**auth_headers(token), **idem}, json=body)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # тот же заказ, не дубль
    # повтор не создаёт второй резерв
    assert len(fake_b2b.reserved) == 1


def test_b2b_unavailable_returns_503(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=1000, available=10)
    fake_b2b.unavailable = True
    r = app_client.post("/api/v1/orders",
                        headers={**auth_headers(token), **_idem_header()},
                        json=_order_body(sku))
    assert r.status_code == 503
    assert r.json()["code"] == "B2B_UNAVAILABLE"


# --- доп. edge ---

def test_checkout_empty_items_returns_400(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    r = app_client.post("/api/v1/orders",
                        headers={**auth_headers(token), **_idem_header()},
                        json={"items": []})
    assert r.status_code == 400


def test_checkout_requires_auth_401(app_client, fake_b2b):
    r = app_client.post("/api/v1/orders",
                        headers=_idem_header(),
                        json=_order_body(str(uuid.uuid4())))
    assert r.status_code == 401


def test_idempotency_same_key_different_body_returns_409(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=1000, available=10)
    key = str(uuid.uuid4())
    idem = _idem_header(key)
    app_client.post("/api/v1/orders", headers={**auth_headers(token), **idem},
                    json=_order_body(sku, qty=1))
    r = app_client.post("/api/v1/orders", headers={**auth_headers(token), **idem},
                        json=_order_body(sku, qty=2))
    assert r.status_code == 409
