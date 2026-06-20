"""US-CART-03 — корзина покупателя. DoD-квест us-cart-03: канон-flow b2c-8.
Имена тестов — ТОЧНО из DoD.
"""
import uuid

from tests.conftest import auth_headers, register_buyer


# --- DoD scenarios ---

def test_add_sku_increments_quantity_if_already_in_cart(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=500, available=10)
    h = auth_headers(token)
    r1 = app_client.post("/api/v1/cart/items", headers=h, json={"sku_id": sku, "quantity": 1})
    assert r1.status_code == 201  # новая позиция
    r2 = app_client.post("/api/v1/cart/items", headers=h, json={"sku_id": sku, "quantity": 2})
    assert r2.status_code == 200  # существующая позиция
    body = r2.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 3  # 1 + 2


def test_get_cart_enriched_with_b2b_data(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=700, available=5, name="Кружка")
    h = auth_headers(token)
    app_client.post("/api/v1/cart/items", headers=h, json={"sku_id": sku, "quantity": 2})
    r = app_client.get("/api/v1/cart", headers=h)
    assert r.status_code == 200
    body = r.json()
    item = body["items"][0]
    assert item["unit_price"] == 700        # цена обогащена из B2B
    assert item["line_total"] == 1400
    assert item["is_available"] is True
    assert body["subtotal"] == 1400


def test_unavailable_sku_shown_with_reason(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=700, available=5)
    h = auth_headers(token)
    app_client.post("/api/v1/cart/items", headers=h, json={"sku_id": sku, "quantity": 2})
    # товар закончился после добавления
    fake_b2b.skus[sku]["available_quantity"] = 0
    r = app_client.get("/api/v1/cart", headers=h)
    body = r.json()
    item = body["items"][0]
    assert item["is_available"] is False
    assert item["unavailable_reason"] == "OUT_OF_STOCK"
    assert item["line_total"] == 0                       # не входит в сумму
    assert body["subtotal"] == 0
    assert body["is_valid"] is False


def test_guest_cart_merged_on_login(app_client, fake_b2b):
    # гость кладёт 3 шт по X-Session-Id
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=500, available=10)
    sid = str(uuid.uuid4())
    app_client.post("/api/v1/cart/items", headers={"X-Session-Id": sid},
                    json={"sku_id": sku, "quantity": 3})
    # тот же покупатель уже имел 1 шт в авторизованной корзине
    email = f"{uuid.uuid4().hex[:8]}@test.ru"
    r = app_client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "first_name": "Тим"})
    token = r.json()["access_token"]
    app_client.post("/api/v1/cart/items", headers=auth_headers(token),
                    json={"sku_id": sku, "quantity": 1})
    # логин с X-Session-Id -> merge MAX(3, 1) = 3
    app_client.post("/api/v1/auth/login", headers={"X-Session-Id": sid},
                    json={"email": email, "password": "password123"})
    cart = app_client.get("/api/v1/cart", headers=auth_headers(token)).json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["quantity"] == 3  # MAX(guest=3, auth=1)


# --- доп. edge ---

def test_empty_cart_returns_200_with_summary(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    r = app_client.get("/api/v1/cart", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["subtotal"] == 0


def test_add_over_stock_returns_409(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=500, available=1)
    r = app_client.post("/api/v1/cart/items", headers=auth_headers(token),
                        json={"sku_id": sku, "quantity": 5})
    assert r.status_code == 409


def test_update_and_delete_item_by_id(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=500, available=10)
    h = auth_headers(token)
    add = app_client.post("/api/v1/cart/items", headers=h, json={"sku_id": sku, "quantity": 1})
    item_id = add.json()["items"][0]["id"]
    upd = app_client.patch(f"/api/v1/cart/items/{sku}", headers=h, json={"quantity": 4})
    assert upd.status_code == 200 and upd.json()["items"][0]["quantity"] == 4
    dele = app_client.delete(f"/api/v1/cart/items/{sku}", headers=h)
    assert dele.status_code == 200 and dele.json()["items"] == []


def test_cart_without_identity_returns_400_missing_identity(app_client, fake_b2b):
    r = app_client.get("/api/v1/cart")
    assert r.status_code == 400 and r.json()["code"] == "MISSING_CART_IDENTITY"
