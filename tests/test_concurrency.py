"""Concurrent requests to the same wallet must not lose or corrupt data."""

import asyncio
import random
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.db.session import session_factory
from app.models import WalletOperation
from tests.helpers import make_operation

REQUESTS = 200


async def get_balance(client: AsyncClient, wallet_id: str) -> Decimal:
    response = await client.get(f"/api/v1/wallets/{wallet_id}")
    return Decimal(response.json()["balance"])


async def count_operations() -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(WalletOperation)
        )


async def test_concurrent_deposits_are_not_lost(
    client: AsyncClient, wallet_id: str
) -> None:
    responses = await asyncio.gather(
        *(
            make_operation(client, wallet_id, "DEPOSIT", 10)
            for _ in range(REQUESTS)
        )
    )

    assert all(r.status_code == 200 for r in responses)
    assert await get_balance(client, wallet_id) == Decimal(10 * REQUESTS)
    assert await count_operations() == REQUESTS


async def test_concurrent_withdrawals_never_overdraw(
    client: AsyncClient, wallet_id: str
) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", 1000)

    # 200 withdrawals of 10 against a balance of 1000:
    # exactly 100 must succeed, the rest must be rejected.
    responses = await asyncio.gather(
        *(
            make_operation(client, wallet_id, "WITHDRAW", 10)
            for _ in range(REQUESTS)
        )
    )
    codes = [r.status_code for r in responses]

    assert codes.count(200) == 100
    assert codes.count(409) == REQUESTS - 100
    assert await get_balance(client, wallet_id) == 0
    assert await count_operations() == 1 + 100


async def test_concurrent_mixed_operations(
    client: AsyncClient, wallet_id: str
) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", 500)
    rng = random.Random(42)
    operations = [
        (rng.choice(["DEPOSIT", "WITHDRAW"]), rng.randint(1, 100))
        for _ in range(REQUESTS)
    ]

    responses = await asyncio.gather(
        *(
            make_operation(client, wallet_id, op_type, amount)
            for op_type, amount in operations
        )
    )

    expected = Decimal(500)
    for (op_type, amount), response in zip(operations, responses, strict=True):
        assert response.status_code in (200, 409)
        if response.status_code == 200:
            expected += amount if op_type == "DEPOSIT" else -amount
        else:
            assert op_type == "WITHDRAW"

    balance = await get_balance(client, wallet_id)
    assert balance == expected
    assert balance >= 0


async def test_concurrent_operations_on_different_wallets(
    client: AsyncClient,
) -> None:
    wallet_ids = [
        (await client.post("/api/v1/wallets")).json()["wallet_id"]
        for _ in range(5)
    ]

    await asyncio.gather(
        *(
            make_operation(client, wallet_id, "DEPOSIT", 1)
            for wallet_id in wallet_ids
            for _ in range(40)
        )
    )

    for wallet_id in wallet_ids:
        assert await get_balance(client, wallet_id) == Decimal(40)
