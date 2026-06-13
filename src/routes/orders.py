from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_buyer
from ..b2b_client import B2BClient, get_b2b_client
from ..database import get_db
from ..errors import ApiError
from ..models import Order
from ..schemas import OrderCancelRequest, OrderCreateRequest
from ..services import order_service

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.post("")
def create_order(
    body: OrderCreateRequest,
    response: Response,
    buyer_id: str = Depends(get_current_buyer),
    db: Session = Depends(get_db),
    b2b: B2BClient = Depends(get_b2b_client),
):
    payload, code = order_service.checkout(db, b2b, buyer_id, body.model_dump())
    response.status_code = code
    return payload


@router.get("")
def list_orders(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    buyer_id: str = Depends(get_current_buyer),
    db: Session = Depends(get_db),
):
    stmt = select(Order).where(Order.buyer_id == buyer_id)
    if status:
        stmt = stmt.where(Order.status == status)
    total = len(db.scalars(stmt).all())
    rows = db.scalars(stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)).all()
    return {"items": [order_service.serialize_order(o) for o in rows],
            "total_count": total, "limit": limit, "offset": offset}


@router.get("/{order_id}")
def get_order(order_id: str, buyer_id: str = Depends(get_current_buyer),
              db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None or order.buyer_id != buyer_id:
        raise ApiError(404, "NOT_FOUND", "Order not found")
    return order_service.serialize_order(order)


@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, body: OrderCancelRequest | None = None,
                 buyer_id: str = Depends(get_current_buyer),
                 db: Session = Depends(get_db), b2b: B2BClient = Depends(get_b2b_client)):
    reason = body.reason if body else None
    return order_service.cancel(db, b2b, buyer_id, order_id, reason)
