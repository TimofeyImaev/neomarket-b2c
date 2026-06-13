from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_buyer
from ..database import get_db
from ..models import PaymentMethod
from ..schemas import PaymentMethodCreateRequest, PaymentMethodResponse

router = APIRouter(prefix="/api/v1/buyers/me/payment-methods", tags=["PaymentMethods"])


def _ser(p: PaymentMethod) -> dict:
    return {
        "id": p.id, "type": p.type, "card_last4": p.card_last4,
        "card_brand": p.card_brand, "is_default": p.is_default,
        "created_at": p.created_at.isoformat(),
    }


@router.get("", response_model=list[PaymentMethodResponse])
def list_methods(buyer_id: str = Depends(get_current_buyer), db: Session = Depends(get_db)):
    rows = db.scalars(select(PaymentMethod).where(PaymentMethod.buyer_id == buyer_id)).all()
    return [_ser(p) for p in rows]


@router.post("", response_model=PaymentMethodResponse, status_code=status.HTTP_201_CREATED)
def add_method(body: PaymentMethodCreateRequest, buyer_id: str = Depends(get_current_buyer),
               db: Session = Depends(get_db)):
    p = PaymentMethod(
        buyer_id=buyer_id, type=body.type, card_last4=body.card_last4,
        card_brand=body.card_brand, is_default=body.is_default,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _ser(p)
