from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_buyer
from ..database import get_db
from ..errors import ApiError
from ..models import Address
from ..schemas import AddressCreateRequest, AddressResponse

router = APIRouter(prefix="/api/v1/buyers/me/addresses", tags=["Addresses"])


def _ser(a: Address) -> dict:
    return {
        "id": a.id, "country": a.country, "region": None, "city": a.city,
        "street": a.street, "building": a.building, "apartment": a.apartment,
        "postal_code": a.postal_code, "recipient_name": a.recipient_name,
        "recipient_phone": a.recipient_phone, "is_default": a.is_default,
        "comment": a.comment, "created_at": a.created_at.isoformat(),
    }


@router.get("", response_model=list[AddressResponse])
def list_addresses(buyer_id: str = Depends(get_current_buyer), db: Session = Depends(get_db)):
    rows = db.scalars(select(Address).where(Address.buyer_id == buyer_id)).all()
    return [_ser(a) for a in rows]


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
def add_address(body: AddressCreateRequest, buyer_id: str = Depends(get_current_buyer),
                db: Session = Depends(get_db)):
    a = Address(
        buyer_id=buyer_id, country=body.country, city=body.city, street=body.street,
        building=body.building, apartment=body.apartment, postal_code=body.postal_code,
        recipient_name=body.recipient_name, recipient_phone=body.recipient_phone,
        is_default=body.is_default, comment=body.comment,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _ser(a)
