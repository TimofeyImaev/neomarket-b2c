from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ----- Auth -----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{10,15}$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str


# ----- Address -----
class AddressCreateRequest(BaseModel):
    country: str = Field(max_length=100)
    region: str | None = Field(default=None, max_length=200)
    city: str = Field(max_length=200)
    street: str = Field(max_length=200)
    building: str = Field(max_length=50)
    apartment: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{10,15}$")
    is_default: bool = False
    comment: str | None = Field(default=None, max_length=500)


class AddressResponse(AddressCreateRequest):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: str


# ----- Payment method -----
class PaymentMethodCreateRequest(BaseModel):
    type: str = Field(pattern=r"^(CARD|SBP|WALLET)$")
    card_last4: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    card_brand: str | None = Field(default=None, pattern=r"^(VISA|MASTERCARD|MIR)$")
    is_default: bool = False


class PaymentMethodResponse(PaymentMethodCreateRequest):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: str


# ----- Cart -----
class CartItemAddRequest(BaseModel):
    sku_id: str
    quantity: int = Field(ge=1)


class CartItemQuantityRequest(BaseModel):
    quantity: int = Field(ge=1)


# ----- Orders (канон b2c-9 checkout) -----
class OrderItemRequest(BaseModel):
    sku_id: str
    quantity: int = Field(ge=1)


class OrderCreateRequest(BaseModel):
    items: list[OrderItemRequest] = Field(min_length=1)
    delivery_address: str | None = Field(default=None, max_length=500)


class OrderCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
