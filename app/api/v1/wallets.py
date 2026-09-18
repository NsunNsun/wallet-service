import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas import ErrorResponse, OperationRequest, WalletResponse
from app.services import wallet as wallet_service

router = APIRouter(prefix="/wallets", tags=["wallets"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Wallet not found",
    },
}


@router.post(
    "",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new wallet with zero balance",
)
async def create_wallet(session: SessionDep) -> WalletResponse:
    wallet = await wallet_service.create_wallet(session)
    return WalletResponse(wallet_id=wallet.id, balance=wallet.balance)


@router.get(
    "/{wallet_id}",
    response_model=WalletResponse,
    responses=NOT_FOUND,
    summary="Get current wallet balance",
)
async def get_wallet(
    wallet_id: uuid.UUID, session: SessionDep
) -> WalletResponse:
    balance = await wallet_service.get_balance(session, wallet_id)
    return WalletResponse(wallet_id=wallet_id, balance=balance)


@router.post(
    "/{wallet_id}/operation",
    response_model=WalletResponse,
    responses={
        **NOT_FOUND,
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Insufficient funds or balance limit exceeded",
        },
    },
    summary="Deposit to or withdraw from a wallet",
)
async def wallet_operation(
    wallet_id: uuid.UUID,
    payload: OperationRequest,
    session: SessionDep,
) -> WalletResponse:
    balance = await wallet_service.apply_operation(
        session, wallet_id, payload.operation_type, payload.amount
    )
    return WalletResponse(wallet_id=wallet_id, balance=balance)
