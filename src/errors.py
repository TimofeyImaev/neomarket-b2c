from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    """Доменная ошибка с плоским телом {code, message, **extra} (type-unification #7).

    extra — доп. поля канона, напр. failed_items для RESERVE_FAILED.
    """

    def __init__(self, status_code: int, code: str, message: str, extra: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


class CartInvalidError(Exception):
    """422 с телом CartValidationResponse (протокол POST /orders, /cart/validate)."""

    def __init__(self, payload: dict):
        self.payload = payload


def _body(code: str, message: str, extra: dict | None = None) -> dict:
    out = {"code": code, "message": message}
    if extra:
        out.update(extra)
    return out


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code,
                            content=_body(exc.code, exc.message, exc.extra))

    @app.exception_handler(CartInvalidError)
    async def _cart_invalid(_: Request, exc: CartInvalidError):
        return JSONResponse(status_code=422, content=exc.payload)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        # Канон: ошибки валидации -> 400 INVALID_REQUEST (плоский формат)
        try:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
            msg = f"{loc}: {first.get('msg')}" if loc else first.get("msg", "Invalid request")
        except Exception:
            msg = "Invalid request"
        return JSONResponse(status_code=400, content=_body("INVALID_REQUEST", msg))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        mapping = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT"}
        code = mapping.get(exc.status_code, "ERROR")
        message = exc.detail if isinstance(exc.detail, str) else code
        return JSONResponse(status_code=exc.status_code, content=_body(code, message))
