"""US-ORD-03 — отмена заказа. DoD-квест us-ord-03: канон-flow b2c-11.
POST /api/v1/orders/{id}/cancel. Имена тестов — ТОЧНО из DoD.
"""
import uuid

from src.models import Order
from tests.conftest import auth_headers, register_buyer


def _place_order(app_client, fake_b2b, token):
    sku = fake_b2b.add_sku(str(uuid.uuid4()), str(uuid.uuid4()), price=1000, available=10)
    r = app_client.post("/api/v1/orders",
                        headers={**auth_headers(token), "Idempotency-Key": str(uuid.uuid4())},
                        json={"items": [{"sku_id": sku, "quantity": 1}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _set_status(app_client, order_id, new_status):
    with app_client.sessionmaker() as db:
        order = db.get(Order, order_id)
        order.status = new_status
        db.commit()


# --- DoD scenarios ---

def test_cancel_paid_order_transitions_to_cancelled(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    oid = _place_order(app_client, fake_b2b, token)  # статус PAID
    r = app_client.post(f"/api/v1/orders/{oid}/cancel", headers=auth_headers(token),
                        json={"reason": "Передумал"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "CANCELLED"
    assert oid in fake_b2b.unreserved  # резерв освобождён


def test_unreserve_failure_transitions_to_cancel_pending(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    oid = _place_order(app_client, fake_b2b, token)
    fake_b2b.unreserve_ok = False  # B2B unreserve упал
    r = app_client.post(f"/api/v1/orders/{oid}/cancel", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["status"] == "CANCEL_PENDING"  # намерение принято, retry асинхронно


def test_cancel_assembling_order_returns_409(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    oid = _place_order(app_client, fake_b2b, token)
    _set_status(app_client, oid, "ASSEMBLING")  # ушёл в сборку
    r = app_client.post(f"/api/v1/orders/{oid}/cancel", headers=auth_headers(token))
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "CANCEL_NOT_ALLOWED"
    assert body["status"] == "ASSEMBLING"  # возвращается текущий статус


def test_other_user_order_returns_404(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    other, _ = register_buyer(app_client)
    oid = _place_order(app_client, fake_b2b, other)  # чужой заказ
    r = app_client.post(f"/api/v1/orders/{oid}/cancel", headers=auth_headers(token))
    assert r.status_code == 404  # IDOR -> 404, не 403


# --- доп. edge ---

def test_cancel_unknown_order_returns_404(app_client, fake_b2b):
    token, _ = register_buyer(app_client)
    r = app_client.post(f"/api/v1/orders/{uuid.uuid4()}/cancel", headers=auth_headers(token))
    assert r.status_code == 404


def test_cancel_requires_auth_401(app_client, fake_b2b):
    r = app_client.post(f"/api/v1/orders/{uuid.uuid4()}/cancel")
    assert r.status_code == 401
