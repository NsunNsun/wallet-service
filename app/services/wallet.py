"""Business logic for wallet balance operations.

Concurrency model
-----------------
A balance change is a single atomic ``UPDATE ... RETURNING`` statement:

    UPDATE wallets
       SET balance = balance - :amount
     WHERE id = :id AND balance >= :amount
    RETURNING balance

PostgreSQL takes a row-level lock for the UPDATE, so concurrent changes of
the same wallet are serialized by the database. Under READ COMMITTED a
waiting transaction re-evaluates the ``WHERE`` clause against the freshly
committed row version, so a withdrawal can never push the balance below
zero and no update is lost. There is no read-modify-write cycle in the
application, which means correctness holds for any number of app workers
or containers. The ``balance >= 0`` CHECK constraint is an extra safety
net at the schema level.
"""

import uuid
from decimal import Decimal

from sqlalchemy import exists, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationType, Wallet, WalletOperation
from app.services.exceptions import (
    BalanceLimitExceededError,
    InsufficientFundsError,
    WalletNotFoundError,
)

NUMERIC_VALUE_OUT_OF_RANGE = "22003"


async def create_wallet(session: AsyncSession) -> Wallet:
    wallet = Wallet(id=uuid.uuid4(), balance=Decimal("0"))
    async with session.begin():
        session.add(wallet)
    return wallet


async def get_balance(session: AsyncSession, wallet_id: uuid.UUID) -> Decimal:
    balance = await session.scalar(
        select(Wallet.balance).where(Wallet.id == wallet_id)
    )
    if balance is None:
        raise WalletNotFoundError(wallet_id)
    return balance


async def apply_operation(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    operation_type: OperationType,
    amount: Decimal,
) -> Decimal:
    """Atomically apply an operation and return the new balance."""
    stmt = update(Wallet).where(Wallet.id == wallet_id)
    if operation_type is OperationType.DEPOSIT:
        stmt = stmt.values(balance=Wallet.balance + amount)
    else:
        stmt = stmt.where(Wallet.balance >= amount).values(
            balance=Wallet.balance - amount
        )
    stmt = stmt.returning(Wallet.balance)

    try:
        async with session.begin():
            new_balance = await session.scalar(stmt)
            if new_balance is None:
                await _raise_for_missing_row(
                    session, wallet_id, operation_type
                )
            await session.execute(
                insert(WalletOperation).values(
                    wallet_id=wallet_id,
                    operation_type=operation_type,
                    amount=amount,
                    balance_after=new_balance,
                )
            )
    except DBAPIError as exc:
        if _sqlstate(exc) == NUMERIC_VALUE_OUT_OF_RANGE:
            raise BalanceLimitExceededError(wallet_id) from exc
        raise
    return new_balance


async def _raise_for_missing_row(
    session: AsyncSession,
    wallet_id: uuid.UUID,
    operation_type: OperationType,
) -> None:
    """Explain why the UPDATE matched no rows."""
    wallet_exists = await session.scalar(
        select(exists().where(Wallet.id == wallet_id))
    )
    if not wallet_exists:
        raise WalletNotFoundError(wallet_id)
    if operation_type is OperationType.WITHDRAW:
        raise InsufficientFundsError(wallet_id)
    raise RuntimeError("Unexpected empty result of a deposit update")


def _sqlstate(exc: DBAPIError) -> str | None:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
