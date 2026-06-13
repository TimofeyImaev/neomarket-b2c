import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header

from .config import settings
from .errors import ApiError


def create_access_token(buyer_id: str, role: str = "buyer", ttl: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl or settings.access_token_ttl_seconds)
    payload = {
        "sub": str(buyer_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "UNAUTHORIZED", "Token expired")
    except jwt.PyJWTError:
        raise ApiError(401, "UNAUTHORIZED", "Invalid token")


def get_current_buyer(authorization: str | None = Header(default=None)) -> str:
    """Возвращает buyer_id из JWT (claim sub). seller/buyer_id никогда из тела."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError(401, "UNAUTHORIZED", "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    claims = _decode(token)
    if claims.get("role") != "buyer":
        raise ApiError(403, "FORBIDDEN", "Buyer role required")
    return claims["sub"]


class CartOwner:
    """Владелец корзины: авторизованный покупатель (buyer:<id>) или гость (session:<uuid>)."""

    def __init__(self, key: str, buyer_id: str | None, session_id: str | None):
        self.key = key
        self.buyer_id = buyer_id
        self.session_id = session_id


def get_cart_owner(
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
) -> CartOwner:
    """Если есть Authorization -> пользовательская корзина, иначе гостевая по X-Session-Id."""
    if authorization and authorization.lower().startswith("bearer "):
        claims = _decode(authorization.split(" ", 1)[1].strip())
        bid = claims["sub"]
        return CartOwner(key=f"buyer:{bid}", buyer_id=bid, session_id=None)
    if x_session_id:
        return CartOwner(key=f"session:{x_session_id}", buyer_id=None, session_id=x_session_id)
    # Канон B2C-8: нет ни JWT, ни X-Session-Id -> 400 MISSING_CART_IDENTITY
    raise ApiError(400, "MISSING_CART_IDENTITY", "JWT or X-Session-Id header is required")
