"""Create wallets and wallet_operations tables.

Revision ID: 0001
Revises:
Create Date: 2026-09-18 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

operation_type = postgresql.ENUM(
    "DEPOSIT", "WITHDRAW", name="operation_type", create_type=False
)


def upgrade() -> None:
    operation_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "wallets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "balance",
            sa.Numeric(precision=20, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "balance >= 0", name=op.f("ck_wallets_balance_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallets")),
    )

    op.create_table(
        "wallet_operations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column("operation_type", operation_type, nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column(
            "balance_after",
            sa.Numeric(precision=20, scale=2),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_wallet_operations_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name=op.f("fk_wallet_operations_wallet_id_wallets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_operations")),
    )
    op.create_index(
        op.f("ix_wallet_operations_wallet_id"),
        "wallet_operations",
        ["wallet_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_wallet_operations_wallet_id"),
        table_name="wallet_operations",
    )
    op.drop_table("wallet_operations")
    op.drop_table("wallets")
    operation_type.drop(op.get_bind(), checkfirst=True)
