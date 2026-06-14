import os
import uuid

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class FakeB2BClient:
    """Подменяет B2B в тестах: каталог, остатки, reserve/unreserve — в памяти."""

    def __init__(self):
        self.products: dict[str, dict] = {}
        self.skus: dict[str, dict] = {}
        self.list_result: dict | None = None
        self.facets_result: dict = {"category_id": None, "facets": []}
        self.unavailable = False  # если True -> методы каталога бросают 503
        self.reserve_ok = True
        self.failed_items = [{"sku_id": "x", "requested": 1, "available": 0, "reason": "INSUFFICIENT_STOCK"}]
        self.unreserve_ok = True
        self.reserved: list[tuple[str, list]] = []
        self.unreserved: list[str] = []

    # --- catalog ---
    def list_products(self, *, limit, offset, q, sort, filter_):
        if self.unavailable:
            from src.errors import ApiError
            raise ApiError(503, "B2B_UNAVAILABLE", "B2B недоступен")
        if self.list_result is not None:
            return self.list_result
        items = list(self.products.values())
        return {"items": items[offset:offset + limit], "total_count": len(items),
                "limit": limit, "offset": offset}

    def get_product(self, product_id):
        if self.unavailable:
            from src.errors import ApiError
            raise ApiError(503, "B2B_UNAVAILABLE", "B2B недоступен")
        return self.products.get(product_id)

    def get_skus(self, sku_ids):
        if self.unavailable:
            from src.errors import ApiError
            raise ApiError(503, "B2B_UNAVAILABLE", "B2B недоступен")
        return {sid: self.skus[sid] for sid in sku_ids if sid in self.skus}

    def get_facets(self, *, category_id, filters):
        if self.unavailable:
            from src.errors import ApiError
            raise ApiError(503, "B2B_UNAVAILABLE", "B2B недоступен")
        return self.facets_result

    # --- reserve ---
    def reserve(self, order_id, items):
        if self.reserve_ok:
            self.reserved.append((order_id, items))
            return True, []
        return False, self.failed_items

    def unreserve(self, order_id, items=None):
        self.unreserved.append(order_id)
        return self.unreserve_ok

    # --- test helpers ---
    def add_sku(self, sku_id, product_id, price, available, name="SKU", is_available=True):
        self.skus[sku_id] = {
            "sku_id": sku_id, "product_id": product_id, "name": name,
            "product_title": f"Product {product_id[:4]}", "sku_name": name,
            "sku_code": f"CODE-{sku_id[:4]}", "price": price,
            "available_quantity": available, "is_available": is_available, "image": None,
        }
        return sku_id


@pytest.fixture
def fake_b2b():
    return FakeB2BClient()


@pytest.fixture
def app_client(fake_b2b):
    from src import database
    from src.database import Base, get_db
    from src.b2b_client import get_b2b_client
    from src.main import create_app

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_b2b_client] = lambda: fake_b2b
    with TestClient(app) as client:
        client.sessionmaker = TestingSessionLocal  # доступ к БД из тестов
        yield client


# ---- shared helpers ----
def register_buyer(client, email=None):
    email = email or f"{uuid.uuid4().hex[:8]}@test.ru"
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "first_name": "Тим",
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["user_id"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_address(client, token):
    r = client.post("/api/v1/buyers/me/addresses", headers=auth_headers(token), json={
        "country": "Россия", "city": "Екатеринбург", "street": "Мира", "building": "19",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def make_payment(client, token):
    r = client.post("/api/v1/buyers/me/payment-methods", headers=auth_headers(token), json={
        "type": "CARD", "card_last4": "4242", "card_brand": "VISA",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]
