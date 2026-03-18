from fastapi import APIRouter, HTTPException, Path, status

from src.api.bank_client_exceptions import BankApiError
from src.api.orders.services import order_services
from src.api.payment.services import (
    AmountExceedsOrderError,
    OrderNotFoundError,
    payment_services,
)
from src.db_models import OrderModel
from src.schemas import (
    OrderSchema,
    OrderWithPaymentsSchema,
    PaymentCreateSchema,
    PaymentSchema,
)

orders_router = APIRouter(prefix="/orders", tags=["Orders"])


@orders_router.get("/{order_id}")
async def get_order(order_id: int) -> OrderSchema | None:
    order = await order_services.get_order(order_id)
    if order:
        return OrderSchema.model_validate(order)
    raise HTTPException(status_code=404, detail="Order not found")


@orders_router.get("/{order_id}/payments")
async def get_order_payments(order_id: int) -> OrderWithPaymentsSchema | None:
    order = await order_services.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order_payments = await order_services.get_order_payments(order_id)

    if order_payments is not None:
        return OrderWithPaymentsSchema(
            id=order.id,
            amount=order.amount,
            payment_status=order.payment_status,
            created_at=order.created_at,
            payments=[
                PaymentSchema.model_validate(payment) for payment in order_payments
            ],
        )
    return None


@orders_router.post("/{order_id}/payments", status_code=status.HTTP_201_CREATED)
async def create_order_payment(
    form_data: PaymentCreateSchema,
    order_id: int = Path(..., ge=1),
) -> PaymentSchema:
    order = await order_services.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        payment = await payment_services.create_payment(
            order_id=order_id,
            amount=form_data.amount,
            payment_type=form_data.type,
        )
        return PaymentSchema.model_validate(payment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AmountExceedsOrderError as exc:
        raise HTTPException(
            status_code=409,
            detail="Sum of payments exceeds order amount",
        ) from exc
    except BankApiError as exc:
        raise HTTPException(
            status_code=502,
            detail="Bank API is unavailable",
        ) from exc


@orders_router.get("/")
async def get_orders(
    limit: int | None = None, offset: int | None = None
) -> list[OrderSchema]:
    orders = await order_services.get_n_rows(OrderModel, limit, offset)
    return [OrderSchema.model_validate(order) for order in orders]


@orders_router.post("/{order_id}/payments/sync")
async def sync_order_payments(
    order_id: int = Path(..., ge=1),
) -> list[PaymentSchema]:
    try:
        payments = await payment_services.sync_order_acquiring_payments(order_id)
        return [PaymentSchema.model_validate(payment) for payment in payments]
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc
