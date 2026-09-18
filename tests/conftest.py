"""Test configuration.

Tests run against a real PostgreSQL instance (the same one as the app),
using a separate ``<POSTGRES_DB>_test`` database. The schema is created
by the actual Alembic migrations, so the migrations are tested as well.
"""

import asyncio
import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

TEST_DB_NAME = f"{os.getenv('POSTGRES_DB', 'wallet')}_test"
os.environ["POSTGRES_DB"] = TEST_DB_NAME

# Imported after the environment is patched on purpose.
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


async def _recreate_test_database() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(
        user=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database="postgres",
    )
    try:
        await conn.execute(
            f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'
        )
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


def pytest_configure(config: pytest.Config) -> None:
    asyncio.run(_recreate_test_database())
    alembic_cfg = Config(
        os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    )
    alembic_cfg.attributes["database_url"] = get_settings().database_url
    command.upgrade(alembic_cfg, "head")
    # Make sure downgrade works too, then bring the schema back.
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE wallet_operations, wallets RESTART IDENTITY")
        )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        yield http_client


@pytest.fixture
async def wallet_id(client: AsyncClient) -> str:
    response = await client.post("/api/v1/wallets")
    assert response.status_code == 201
    return response.json()["wallet_id"]
