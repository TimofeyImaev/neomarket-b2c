"""Корзина B2C (канон b2c-8). Гость (X-Session-Id) и авторизованный (JWT)."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..auth import CartOwner, get_cart_owner
from ..b2b_client import B2BClient, get_b2b_client
from ..database import get_db
from ..errors import ApiError
from ..models import CartItem
from ..schemas import CartItemAddRequest, CartItemQuantityRequest
from ..services import cart_service

router = APIRouter(prefix="/api/v1/cart", tags=["Cart"])


@router.get("")
def get_cart(owner: CartOwner = Depends(get_cart_owner),
             db: Session = Depends(get_db), b2b: B2BClient = Depends(get_b2b_client)):
    cart = cart_service.get_or_create_cart(db, owner.key)
    db.commit()
    return cart_service.serialize_cart(cart, b2b)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(owner: CartOwner = Depends(get_cart_owner), db: Session = Depends(get_db)):
    cart = cart_service.get_or_create_cart(db, owner.key)
    for it in list(cart.items):
        db.delete(it)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items")
def add_item(body: CartItemAddRequest, response: Response,
             owner: CartOwner = Depends(get_cart_owner),
             db: Session = Depends(get_db), b2b: B2BClient = Depends(get_b2b_client)):
    sku = b2b.get_skus([body.sku_id]).get(body.sku_id)
    if sku is None:
        raise ApiError(404, "NOT_FOUND", "SKU not found or product unavailable")

    cart = cart_service.get_or_create_cart(db, owner.key)
    existing = cart_service.find_item_by_sku(cart, body.sku_id)
    desired = (existing.quantity if existing else 0) + body.quantity
    if desired > sku.get("available_quantity", 0):
        raise ApiError(409, "CONFLICT", "Not enough stock for requested quantity")

    if existing:
        existing.quantity = desired  # повторное добавление -> увеличиваем quantity
        code = status.HTTP_200_OK
    else:
        cart.items.append(CartItem(sku_id=body.sku_id, quantity=body.quantity,
                                   unit_price_at_add=sku.get("price")))
        code = status.HTTP_201_CREATED
    db.commit()
    db.refresh(cart)
    response.status_code = code
    return cart_service.serialize_cart(cart, b2b)


@router.put("/items/{item_id}")
def update_item(item_id: str, body: CartItemQuantityRequest,
                owner: CartOwner = Depends(get_cart_owner),
                db: Session = Depends(get_db), b2b: B2BClient = Depends(get_b2b_client)):
    cart = cart_service.get_or_create_cart(db, owner.key)
    item = cart_service.find_item_by_id(cart, item_id)  # IDOR: чужой item -> 404
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Item not found in cart")
    sku = b2b.get_skus([item.sku_id]).get(item.sku_id)
    if body.quantity > (sku.get("available_quantity", 0) if sku else 0):
        raise ApiError(409, "CONFLICT", "Not enough stock for requested quantity")
    item.quantity = body.quantity
    db.commit()
    db.refresh(cart)
    return cart_service.serialize_cart(cart, b2b)


@router.delete("/items/{item_id}")
def delete_item(item_id: str, owner: CartOwner = Depends(get_cart_owner),
                db: Session = Depends(get_db), b2b: B2BClient = Depends(get_b2b_client)):
    cart = cart_service.get_or_create_cart(db, owner.key)
    item = cart_service.find_item_by_id(cart, item_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Item not found in cart")
    db.delete(item)
    db.commit()
    db.refresh(cart)
    return cart_service.serialize_cart(cart, b2b)
