

from fastapi import APIRouter
from src.schemas import PaymentSchema
from src.api.payment.services import payment_services

payments_router = APIRouter(prefix='/payments',tags=['Payments'])


@payments_router.get('/{payment_id}')
async def get_payment(payment_id: int) -> PaymentSchema | None:
    payment = await payment_services.get_payment(payment_id)
    return PaymentSchema.model_validate(payment)


@payments_router.post('/{payment_id}/refund')
async def refund_payment(payment_id: int) -> PaymentSchema | None:
    payment = await payment_services.refund_payment(payment_id)
    return PaymentSchema.model_validate(payment)
