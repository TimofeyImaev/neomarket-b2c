"""Заказы B2C по канон-flow b2c-9 (checkout) и b2c-11 (cancel)."""
import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

import json as _json

from ..b2b_client import B2BClient
from ..errors import ApiError
from ..models import Address, IdempotencyKey, Order, OrderItem

CANCELLABLE = {"CREATED", "PAID", "ASSEMBLING", "DELIVERING"}  # b2c/openapi.yaml:699


def _order_number() -> str:
    now = datetime.now(timezone.utc)
    return f"NM-{now:%Y}-{uuid.uuid4().hex[:8].upper()}"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_request(body: dict) -> str:
    import json
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_address(raw: str | None) -> dict | None:
    """Return AddressResponse object stored as JSON snapshot, or None."""
    if not raw:
        return None
    import json
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {"id": raw}  # legacy: raw is plain address_id


def serialize_order(order: Order) -> dict:
    """Ответ по канон-flow b2c-9 (Response 201)."""
    return {
        "id": order.id,
        "number": order.number,
        "buyer_id": order.buyer_id,
        "status": order.status,
        "items": [
            {
                "id": it.id,
                "sku_id": it.sku_id,
                "product_id": it.product_id,
                "name": it.sku_name or it.product_title,
                "product_title": it.product_title,
                "sku_name": it.sku_name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "line_total": it.line_total,
            }
            for it in order.items
        ],
        "subtotal": order.total_amount,
        "total": order.total_amount,
        "address": _parse_address(order.delivery_address),
        "cancel_reason": order.cancel_reason,
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
    }


def checkout(db: Session, b2b: B2BClient, buyer_id: str, body: dict,
             idempotency_key: str | None = None) -> tuple[dict, int]:
    """Канон b2c-9: idempotency check -> cart items -> reserve (all-or-nothing) -> Order PAID."""
    from sqlalchemy import select
    from ..models import Cart

    idem = idempotency_key or body.get("idempotency_key")
    if not idem:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header обязателен")

    # 0. Idempotency: повтор с тем же ключом -> существующий заказ
    key = f"{buyer_id}:{idem}"
    req_hash = _hash_request(body)
    existing = db.get(IdempotencyKey, key)
    if existing is not None:
        if existing.request_hash != req_hash:
            raise ApiError(409, "CONFLICT", "idempotency_key переиспользован с другим телом")
        return serialize_order(db.get(Order, existing.order_id)), 201

    # 1. Читаем items из корзины покупателя (b2c/openapi.yaml:1241-1249)
    cart = db.scalar(select(Cart).where(Cart.owner_key == f"buyer:{buyer_id}"))
    if cart is None or len(cart.items) == 0:
        raise ApiError(400, "INVALID_REQUEST", "Корзина пуста")
    items = [{"sku_id": it.sku_id, "quantity": it.quantity} for it in cart.items]

    # 2-3. Получаем актуальные данные SKU из B2B — бросит 503 B2B_UNAVAILABLE если недоступен
    sku_ids = [i["sku_id"] for i in items]
    sku_info = b2b.get_skus(sku_ids)

    # 4. Reserve в B2B (all-or-nothing).
    order_id = str(uuid.uuid4())
    reserve_items = [{"sku_id": i["sku_id"], "quantity": i["quantity"]} for i in items]
    ok, failed_items = b2b.reserve(order_id, reserve_items)
    if not ok:
        raise ApiError(409, "RESERVE_FAILED", "Не удалось зарезервировать товары",
                       extra={"failed_items": failed_items})

    # 5. Создаём Order со статусом PAID и фиксируем цены в OrderItem
    # Сохраняем снапшот адреса как JSON (b2c/openapi.yaml:1315 AddressResponse)
    address_id = body.get("address_id")
    address_snapshot: str | None = None
    if address_id:
        addr = db.get(Address, address_id)
        if addr:
            address_snapshot = _json.dumps({
                "id": addr.id,
                "created_at": _iso(addr.created_at),
                "country": addr.country, "region": None,
                "city": addr.city, "street": addr.street, "building": addr.building,
                "apartment": addr.apartment, "postal_code": addr.postal_code,
                "recipient_name": addr.recipient_name, "recipient_phone": addr.recipient_phone,
                "is_default": addr.is_default, "comment": addr.comment,
            }, ensure_ascii=False)
        else:
            address_snapshot = _json.dumps({"id": address_id})
    order = Order(id=order_id, number=_order_number(), buyer_id=buyer_id, status="PAID",
                  delivery_address=address_snapshot,
                  paid_at=datetime.now(timezone.utc))
    total = 0
    for i in items:
        sku = sku_info.get(i["sku_id"], {})
        unit_price = sku.get("price", 0)
        line_total = unit_price * i["quantity"]
        total += line_total
        order.items.append(OrderItem(
            sku_id=i["sku_id"], product_id=sku.get("product_id", ""),
            product_title=sku.get("product_title") or sku.get("name", ""),
            sku_name=sku.get("sku_name") or sku.get("name"),
            quantity=i["quantity"], unit_price=unit_price, line_total=line_total,
        ))
    order.total_amount = total
    db.add(order)
    db.add(IdempotencyKey(key=key, request_hash=req_hash, order_id=order.id))
    db.commit()
    db.refresh(order)
    return serialize_order(order), 201


def cancel(db: Session, b2b: B2BClient, buyer_id: str, order_id: str,
           reason: str | None) -> dict:
    """Канон b2c-11: CANCEL_PENDING -> unreserve -> CANCELLED (или остаётся PENDING при фейле)."""
    order = db.get(Order, order_id)
    if order is None or order.buyer_id != buyer_id:
        raise ApiError(404, "NOT_FOUND", "Order not found")
    if order.status not in CANCELLABLE:
        raise ApiError(409, "CANCEL_NOT_ALLOWED",
                       f"Order in status {order.status} cannot be cancelled",
                       extra={"status": order.status})

    order.status = "CANCEL_PENDING"
    order.cancel_reason = reason
    db.flush()
    reserve_items = [{"sku_id": it.sku_id, "quantity": it.quantity} for it in order.items]
    released = b2b.unreserve(order.id, reserve_items)
    order.status = "CANCELLED" if released else "CANCEL_PENDING"
    db.commit()
    db.refresh(order)
    return serialize_order(order)
