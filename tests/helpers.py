from httpx import AsyncClient, Response


async def make_operation(
    client: AsyncClient,
    wallet_id: str,
    operation_type: str,
    amount: object,
) -> Response:
    return await client.post(
        f"/api/v1/wallets/{wallet_id}/operation",
        json={"operation_type": operation_type, "amount": amount},
    )
