import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.wallet import MONEY_PRECISION, MONEY_SCALE, OperationType

# A single operation may not exceed 10^16; the balance column itself
# is wider, so a single request can never overflow it on its own.
Amount = Annotated[
    Decimal,
    Field(
        gt=0,
        max_digits=MONEY_PRECISION - 2,
        decimal_places=MONEY_SCALE,
        allow_inf_nan=False,
        examples=[1000],
    ),
]


class OperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_type: OperationType
    amount: Amount


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wallet_id: uuid.UUID
    balance: Decimal = Field(
        description="Balance serialized as a string to keep precision.",
        examples=["1000.00"],
    )


class ErrorResponse(BaseModel):
    detail: str
