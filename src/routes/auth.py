import hashlib

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_access_token
from ..config import settings
from ..database import get_db
from ..errors import ApiError
from ..models import Buyer
from ..schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _tokens(buyer: Buyer) -> TokenResponse:
    access = create_access_token(buyer.id, role="buyer")
    return TokenResponse(
        access_token=access,
        refresh_token=create_access_token(buyer.id, role="buyer", ttl=settings.access_token_ttl_seconds * 24),
        expires_in=settings.access_token_ttl_seconds,
        user_id=buyer.id,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(Buyer).where(Buyer.email == body.email)):
        raise ApiError(409, "CONFLICT", "Email already registered")
    buyer = Buyer(
        email=body.email, password_hash=_hash_pw(body.password),
        first_name=body.first_name, last_name=body.last_name, phone=body.phone,
    )
    db.add(buyer)
    db.commit()
    db.refresh(buyer)
    return _tokens(buyer)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    buyer = db.scalar(select(Buyer).where(Buyer.email == body.email))
    if buyer is None or buyer.password_hash != _hash_pw(body.password):
        raise ApiError(401, "UNAUTHORIZED", "Invalid email or password")
    return _tokens(buyer)
