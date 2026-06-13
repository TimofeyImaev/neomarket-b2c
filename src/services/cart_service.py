"""Корзина B2C по канон-flow b2c-8. B2C хранит только sku_id+quantity, цены обогащаются из B2B."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..b2b_client import B2BClient
from ..models import Cart, CartItem


def get_or_create_cart(db: Session, owner_key: str) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.owner_key == owner_key))
    if cart is None:
        cart = Cart(owner_key=owner_key)
        db.add(cart)
        db.flush()
    return cart


def find_item_by_id(cart: Cart, item_id: str) -> CartItem | None:
    for item in cart.items:
        if item.id == item_id:
            return item
    return None


def find_item_by_sku(cart: Cart, sku_id: str) -> CartItem | None:
    for item in cart.items:
        if item.sku_id == sku_id:
            return item
    return None


def _availability(sku: dict | None) -> tuple[bool, str | None]:
    """Возвращает (available, unavailable_reason) по канон-таблице причин."""
    if sku is None:
        return False, "PRODUCT_DELETED"
    if not sku.get("is_available", True):
        return False, "PRODUCT_BLOCKED"
    if sku.get("available_quantity", 0) <= 0:
        return False, "OUT_OF_STOCK"
    return True, None


def serialize_cart(cart: Cart, b2b: B2BClient) -> dict:
    """Ответ GET /cart: items + summary + checkout_payload (канон b2c-8)."""
    sku_ids = [i.sku_id for i in cart.items]
    info = b2b.get_skus(sku_ids) if sku_ids else {}

    items_out = []
    total_amount = 0
    total_items = 0
    unavailable_count = 0
    checkout_items = []

    for item in cart.items:
        sku = info.get(item.sku_id)
        available, reason = _availability(sku)
        unit_price = (sku or {}).get("price", item.unit_price_at_add or 0)
        line_total = unit_price * item.quantity if available else 0  # недоступные не входят в сумму
        total_items += item.quantity
        if available:
            total_amount += line_total
            checkout_items.append({"sku_id": item.sku_id, "quantity": item.quantity})
        else:
            unavailable_count += 1
        items_out.append({
            "id": item.id,
            "sku_id": item.sku_id,
            "product_id": (sku or {}).get("product_id"),
            "title": (sku or {}).get("product_title") or (sku or {}).get("name"),
            "name": (sku or {}).get("name"),
            "quantity": item.quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "available": available,
            "unavailable_reason": reason,
            "available_quantity": (sku or {}).get("available_quantity", 0),
            "image": (sku or {}).get("image"),
        })

    return {
        "id": cart.id,
        "items": items_out,
        "summary": {
            "total_amount": total_amount,
            "total_items": total_items,
            "unavailable_count": unavailable_count,
            "checkout_ready": unavailable_count == 0 and len(items_out) > 0,
        },
        "checkout_payload": {"items": checkout_items},
    }


def merge_session_into_buyer(db: Session, session_id: str, buyer_id: str) -> None:
    """Merge гостевой корзины в пользовательскую при логине: quantity = MAX(guest, auth)."""
    guest = db.scalar(select(Cart).where(Cart.owner_key == f"session:{session_id}"))
    if guest is None:
        return
    buyer_cart = get_or_create_cart(db, f"buyer:{buyer_id}")
    for g_item in list(guest.items):
        existing = find_item_by_sku(buyer_cart, g_item.sku_id)
        if existing is not None:
            existing.quantity = max(existing.quantity, g_item.quantity)
            db.delete(g_item)
        else:
            g_item.cart_id = buyer_cart.id
    db.delete(guest)
    db.commit()
