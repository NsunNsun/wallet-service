import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.session import session_factory
from app.models import OperationType, Wallet, WalletOperation
from tests.helpers import make_operation


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_wallet(client: AsyncClient) -> None:
    response = await client.post("/api/v1/wallets")

    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["wallet_id"])
    assert Decimal(body["balance"]) == 0


async def test_get_wallet_balance(client: AsyncClient, wallet_id: str) -> None:
    response = await client.get(f"/api/v1/wallets/{wallet_id}")

    assert response.status_code == 200
    assert response.json() == {"wallet_id": wallet_id, "balance": "0.00"}


async def test_get_unknown_wallet_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/wallets/{uuid.uuid4()}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


async def test_get_wallet_with_invalid_uuid_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/wallets/not-a-uuid")

    assert response.status_code == 422


async def test_deposit(client: AsyncClient, wallet_id: str) -> None:
    response = await make_operation(client, wallet_id, "DEPOSIT", 1000)

    assert response.status_code == 200
    assert response.json() == {"wallet_id": wallet_id, "balance": "1000.00"}

    response = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(response.json()["balance"]) == Decimal("1000")


async def test_deposit_with_fractional_amount(
    client: AsyncClient, wallet_id: str
) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", "10.25")
    response = await make_operation(client, wallet_id, "DEPOSIT", 0.1)

    assert response.status_code == 200
    assert Decimal(response.json()["balance"]) == Decimal("10.35")


async def test_withdraw(client: AsyncClient, wallet_id: str) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", 1000)

    response = await make_operation(client, wallet_id, "WITHDRAW", 400)

    assert response.status_code == 200
    assert Decimal(response.json()["balance"]) == Decimal("600")


async def test_withdraw_whole_balance(
    client: AsyncClient, wallet_id: str
) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", 500)

    response = await make_operation(client, wallet_id, "WITHDRAW", 500)

    assert response.status_code == 200
    assert Decimal(response.json()["balance"]) == 0


async def test_withdraw_insufficient_funds_returns_409(
    client: AsyncClient, wallet_id: str
) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", 100)

    response = await make_operation(client, wallet_id, "WITHDRAW", 100.01)

    assert response.status_code == 409
    assert "Insufficient funds" in response.json()["detail"]
    balance = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(balance.json()["balance"]) == Decimal("100")


@pytest.mark.parametrize("operation_type", ["DEPOSIT", "WITHDRAW"])
async def test_operation_on_unknown_wallet_returns_404(
    client: AsyncClient, operation_type: str
) -> None:
    response = await make_operation(
        client, str(uuid.uuid4()), operation_type, 10
    )

    assert response.status_code == 404


async def test_deposit_over_balance_limit_returns_409(
    client: AsyncClient, wallet_id: str
) -> None:
    max_balance = Decimal("999999999999999999.99")  # NUMERIC(20, 2)
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Wallet)
            .where(Wallet.id == uuid.UUID(wallet_id))
            .values(balance=max_balance)
        )

    response = await make_operation(client, wallet_id, "DEPOSIT", "0.01")

    assert response.status_code == 409
    assert "limit" in response.json()["detail"]
    balance = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(balance.json()["balance"]) == max_balance


@pytest.mark.parametrize(
    "payload",
    [
        {"operation_type": "DEPOSIT", "amount": 0},
        {"operation_type": "DEPOSIT", "amount": -10},
        {"operation_type": "DEPOSIT", "amount": "0.001"},
        {"operation_type": "DEPOSIT", "amount": "abc"},
        {"operation_type": "DEPOSIT", "amount": None},
        {"operation_type": "DEPOSIT", "amount": "NaN"},
        {"operation_type": "DEPOSIT", "amount": "Infinity"},
        {"operation_type": "DEPOSIT", "amount": "100000000000000000"},
        {"operation_type": "TRANSFER", "amount": 10},
        {"operation_type": "deposit", "amount": 10},
        {"operation_type": "DEPOSIT"},
        {"amount": 10},
        {"operation_type": "DEPOSIT", "amount": 10, "extra": 1},
        {},
    ],
)
async def test_invalid_operation_payload_returns_422(
    client: AsyncClient, wallet_id: str, payload: dict
) -> None:
    response = await client.post(
        f"/api/v1/wallets/{wallet_id}/operation", json=payload
    )

    assert response.status_code == 422
    balance = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert Decimal(balance.json()["balance"]) == 0


async def test_operation_with_invalid_uuid_returns_422(
    client: AsyncClient,
) -> None:
    response = await make_operation(client, "not-a-uuid", "DEPOSIT", 10)

    assert response.status_code == 422


async def test_operations_are_recorded(
    client: AsyncClient, wallet_id: str
) -> None:
    await make_operation(client, wallet_id, "DEPOSIT", 1000)
    await make_operation(client, wallet_id, "WITHDRAW", 300)
    await make_operation(client, wallet_id, "WITHDRAW", 5000)  # rejected

    async with session_factory() as session:
        operations = (
            await session.scalars(
                select(WalletOperation)
                .where(WalletOperation.wallet_id == uuid.UUID(wallet_id))
                .order_by(WalletOperation.id)
            )
        ).all()

    assert [
        (op.operation_type, op.amount, op.balance_after) for op in operations
    ] == [
        (OperationType.DEPOSIT, Decimal("1000"), Decimal("1000")),
        (OperationType.WITHDRAW, Decimal("300"), Decimal("700")),
    ]
