from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.wallets import router as wallets_router
from app.core.config import get_settings
from app.db.session import engine
from app.services.exceptions import (
    BalanceLimitExceededError,
    InsufficientFundsError,
    WalletNotFoundError,
    WalletServiceError,
)

ERROR_STATUS_CODES: dict[type[WalletServiceError], int] = {
    WalletNotFoundError: status.HTTP_404_NOT_FOUND,
    InsufficientFundsError: status.HTTP_409_CONFLICT,
    BalanceLimitExceededError: status.HTTP_409_CONFLICT,
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=get_settings().app_name,
        version="1.0.0",
        description=(
            "REST API for user wallets: create a wallet, deposit or "
            "withdraw funds and get the current balance. Balance changes "
            "are atomic and safe under concurrent requests."
        ),
        lifespan=lifespan,
    )
    app.include_router(wallets_router, prefix="/api/v1")

    @app.exception_handler(WalletServiceError)
    async def handle_service_error(
        _: Request, exc: WalletServiceError
    ) -> JSONResponse:
        status_code = ERROR_STATUS_CODES.get(
            type(exc), status.HTTP_400_BAD_REQUEST
        )
        return JSONResponse(
            status_code=status_code, content={"detail": str(exc)}
        )

    @app.get("/health", tags=["service"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
