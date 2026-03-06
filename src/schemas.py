from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from src.db_models import OrderPaymentStatus, PaymentStatus, PaymentType


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra='forbid'
    )


class PaymentSchema(BaseSchema):
    id: int
    amount: Decimal
    type: PaymentType
    status: PaymentStatus
    bank_payment_id: str | None
    created_at: datetime
    order_id: int


class PaymentCreateSchema(BaseSchema):
    amount: Decimal
    type: PaymentType


class OrderSchema(BaseSchema):
    id: int
    amount: Decimal
    payment_status: OrderPaymentStatus
    created_at: datetime


class OrderWithPaymentsSchema(OrderSchema):
    payments: list[PaymentSchema]
