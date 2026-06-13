import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Address(Base):
    __tablename__ = "addresses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    buyer_id: Mapped[str] = mapped_column(String(36), ForeignKey("buyers.id"), index=True)
    country: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(200))
    street: Mapped[str] = mapped_column(String(200))
    building: Mapped[str] = mapped_column(String(50))
    apartment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    buyer_id: Mapped[str] = mapped_column(String(36), ForeignKey("buyers.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Cart(Base):
    __tablename__ = "carts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.created_at"
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "sku_id", name="uq_cart_sku"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cart_id: Mapped[str] = mapped_column(String(36), ForeignKey("carts.id"), index=True)
    sku_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_at_add: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    cart: Mapped["Cart"] = relationship(back_populates="items")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    number: Mapped[str] = mapped_column(String(40))
    buyer_id: Mapped[str] = mapped_column(String(36), ForeignKey("buyers.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PAID")
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    sku_id: Mapped[str] = mapped_column(String(36))
    product_id: Mapped[str] = mapped_column(String(36))
    product_title: Mapped[str] = mapped_column(String(255))  # снимок на момент покупки
    sku_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)  # зафиксированная цена
    line_total: Mapped[int] = mapped_column(Integer)
    order: Mapped["Order"] = relationship(back_populates="items")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)  # buyer_id + ':' + header
    request_hash: Mapped[str] = mapped_column(String(64))
    order_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
