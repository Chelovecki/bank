from fastapi import APIRouter, HTTPException, Path

from src.api.bank_client import BankApiError, BankPaymentNotFoundError
from src.api.payment.services import (
    BankDataMismatchError,
    InvalidPaymentStateError,
    InvalidPaymentTypeError,
    PaymentNotFoundError,
    payment_services,
)
from src.schemas import PaymentSchema

payments_router = APIRouter(prefix="/payments", tags=["Payments"])


@payments_router.get("/{payment_id}")
async def get_payment(payment_id: int = Path(..., ge=1)) -> PaymentSchema:
    payment = await payment_services.get_payment(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentSchema.model_validate(payment)


@payments_router.post("/{payment_id}/refund")
async def refund_payment(payment_id: int = Path(..., ge=1)) -> PaymentSchema:
    try:
        payment = await payment_services.refund_payment(payment_id)
        return PaymentSchema.model_validate(payment)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc
    except InvalidPaymentStateError as exc:
        raise HTTPException(
            status_code=409,
            detail="Only completed payments can be refunded",
        ) from exc


@payments_router.post("/{payment_id}/sync")
async def sync_payment(payment_id: int = Path(..., ge=1)) -> PaymentSchema:
    try:
        payment = await payment_services.sync_payment_with_bank(payment_id)
        return PaymentSchema.model_validate(payment)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc
    except InvalidPaymentTypeError as exc:
        raise HTTPException(
            status_code=409,
            detail="Only acquiring payments can be synchronized",
        ) from exc
    except InvalidPaymentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BankDataMismatchError as exc:
        raise HTTPException(
            status_code=409,
            detail="Bank payment data mismatch",
        ) from exc
    except (BankApiError, BankPaymentNotFoundError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Cannot synchronize with bank API",
        ) from exc
