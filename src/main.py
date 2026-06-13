from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, engine
from .errors import register_error_handlers
from .routes import addresses, auth, payment_methods, catalog, cart, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="NeoMarket B2C API", version="1.0.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(addresses.router)
    app.include_router(payment_methods.router)
    app.include_router(catalog.router)
    app.include_router(cart.router)
    app.include_router(orders.router)

    @app.get("/health", tags=["infra"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
