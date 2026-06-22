"""US-ORD-01 — оформление заказа (checkout). DoD-квест: contraction-implement-us-ord-01-checkout.
Канон-flow b2c-9: idempotency check → cart → B2B reserve → Order PAID.
Имена тестов — ТОЧНО из DoD.
"""
import uuid

from tests.conftest import auth_headers, register_buyer, make_address, make_payment


def _add_to_cart(client, token, sku_id, quantity=1):
    r = client.post("/api/v1/cart/items", headers=auth_headers(token),
                    json={"sku_id": sku_id, "quantity": quantity})
    assert r.status_code in (200, 201), r.text


def _checkout(client, token, idem_key=None, address_id=None, payment_method_id=None):
    headers = {**auth_headers(token), "Idempotency-Key": idem_key or str(uuid.uuid4())}
    body = {}
    if address_id:
        body["address_id"] = address_id
    if payment_method_id:
        body["payment_method_id"] = payment_method_id
    return client.post("/api/v1/orders", headers=headers, json=body)


# ---------- DoD scenarios (точные имена) ----------

def test_checkout_creates_paid_order_with_fixed_prices(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=500, available=10)
    _add_to_cart(app_client, token, sku, quantity=2)
    addr = make_address(app_client, token)
    pm = make_payment(app_client, token)

    r = _checkout(app_client, token, address_id=addr, payment_method_id=pm)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PAID"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["unit_price"] == 500   # цена зафиксирована в OrderItem
    assert item["quantity"] == 2
    assert item["line_total"] == 1000


def test_partial_reserve_failure_returns_409(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=300, available=10)
    _add_to_cart(app_client, token, sku, quantity=1)
    fake_b2b.reserve_ok = False
    fake_b2b.failed_items = [{"sku_id": sku, "requested": 1, "available": 0,
                               "reason": "INSUFFICIENT_STOCK"}]

    r = _checkout(app_client, token)

    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "RESERVE_FAILED"
    assert "failed_items" in body


def test_idempotency_returns_existing_order(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=200, available=10)
    _add_to_cart(app_client, token, sku, quantity=1)
    addr = make_address(app_client, token)
    pm = make_payment(app_client, token)
    idem = str(uuid.uuid4())

    r1 = _checkout(app_client, token, idem_key=idem, address_id=addr, payment_method_id=pm)
    r2 = _checkout(app_client, token, idem_key=idem, address_id=addr, payment_method_id=pm)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # повтор возвращает тот же заказ


def test_b2b_unavailable_returns_503(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=100, available=5)
    _add_to_cart(app_client, token, sku, quantity=1)
    fake_b2b.unavailable = True

    r = _checkout(app_client, token)

    assert r.status_code == 503
    assert r.json()["code"] == "B2B_UNAVAILABLE"
