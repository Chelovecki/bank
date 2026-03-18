from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.bank_client import (
    BankApiError,
    BankClient,
    BankClientProtocol,
    BankPaymentNotFoundError,
    BankPaymentState,
)
from src.db_models import (
    OrderModel,
    OrderPaymentStatus,
    PaymentModel,
    PaymentStatus,
    PaymentType,
)
from src.services import BaseService
from src.settings import settings


class PaymentError(Exception):
    pass


class OrderNotFoundError(PaymentError):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class AmountExceedsOrderError(PaymentError):
    pass


class InvalidPaymentStateError(PaymentError):
    pass


class InvalidPaymentTypeError(PaymentError):
    pass


class BankDataMismatchError(PaymentError):
    pass


class PaymentServices(BaseService):
    def __init__(self, session, bank_client: BankClientProtocol):
        super().__init__(session)
        self.bank_client: BankClientProtocol = bank_client

    @staticmethod
    def _calculate_order_status(
        order_amount: Decimal, payments: list[PaymentModel]
    ) -> OrderPaymentStatus:
        paid_amount = sum(
            payment.amount
            for payment in payments
            if payment.status == PaymentStatus.COMPLETED
        )
        if paid_amount <= 0:
            return OrderPaymentStatus.UNPAID
        if paid_amount >= order_amount:
            return OrderPaymentStatus.PAID
        return OrderPaymentStatus.PARTIALLY_PAID

    @staticmethod
    def _reserved_amount(payments: list[PaymentModel]) -> Decimal:
        return sum(
            payment.amount
            for payment in payments
            if payment.status in {PaymentStatus.PENDING, PaymentStatus.COMPLETED}
        )  # type: ignore

    async def _update_order_status(self, session, order: OrderModel) -> None:
        order.payment_status = self._calculate_order_status(
            order.amount,
            order.payments,
        )
        session.add(order)

    async def create_payment(
        self, order_id: int, amount: Decimal, payment_type: PaymentType
    ) -> PaymentModel:
        async with self.session_factory() as session:
            statement = (
                select(OrderModel)
                .where(OrderModel.id == order_id)
                .options(selectinload(OrderModel.payments))
                .with_for_update()
            )
            result = await session.execute(statement)
            order = result.scalar_one_or_none()

            if order is None:
                raise OrderNotFoundError

            if amount <= 0:
                raise ValueError("payment amount must be greater than zero")

            reserved = self._reserved_amount(order.payments)
            if reserved + amount > order.amount:
                raise AmountExceedsOrderError

            payment = PaymentModel(
                order=order,
                amount=amount,
                type=payment_type,
                status=PaymentStatus.PENDING,
            )

            if payment_type == PaymentType.CASH:
                payment.status = PaymentStatus.COMPLETED
                session.add(payment)
                await self._update_order_status(session, order)
                await session.commit()
                await session.refresh(payment)
                return payment

            if payment_type != PaymentType.ACQUIRING:
                raise InvalidPaymentTypeError

            payment.bank_status = BankPaymentState.PENDING.value
            payment.bank_checked_at = datetime.now(timezone.utc)

            session.add(payment)
            await session.commit()
            await session.refresh(payment)
            payment_id = payment.id

        bank_payment_id = await self.bank_client.acquiring_start(
            order_id,
            amount,
        )

        async with self.session_factory() as session:
            payment = await session.get(PaymentModel, payment_id)
            order = await session.get(
                OrderModel, order_id, options=(selectinload(OrderModel.payments),)
            )
            if payment is None or order is None:
                raise PaymentNotFoundError

            payment.bank_payment_id = bank_payment_id
            session.add(payment)
            await self._update_order_status(session, order)
            await session.commit()
            await session.refresh(payment)
            return payment

    async def get_payment(self, payment_id: int) -> PaymentModel | None:
        async with self.session_factory() as session:
            return await session.get(PaymentModel, payment_id)

    async def refund_payment(self, payment_id: int) -> PaymentModel:
        async with self.session_factory() as session:
            statement = (
                select(PaymentModel)
                .where(PaymentModel.id == payment_id)
                .options(
                    selectinload(PaymentModel.order).selectinload(OrderModel.payments)
                )
            )
            result = await session.execute(statement)
            payment = result.scalar_one_or_none()
            if payment is None:
                raise PaymentNotFoundError
            if payment.status != PaymentStatus.COMPLETED:
                raise InvalidPaymentStateError(
                    "only completed payments can be refunded"
                )

            payment.status = PaymentStatus.REFUNDED
            payment.bank_status = "REFUNDED"
            payment.bank_checked_at = datetime.now(timezone.utc)
            session.add(payment)

            if payment.order is None:
                raise OrderNotFoundError

            await self._update_order_status(session, payment.order)
            await session.commit()
            await session.refresh(payment)
            return payment

    async def sync_payment_with_bank(self, payment_id: int) -> PaymentModel:
        async with self.session_factory() as session:
            statement = (
                select(PaymentModel)
                .where(PaymentModel.id == payment_id)
                .options(
                    selectinload(PaymentModel.order).selectinload(OrderModel.payments)
                )
            )
            result = await session.execute(statement)
            payment = result.scalar_one_or_none()
            if payment is None:
                raise PaymentNotFoundError
            if payment.type != PaymentType.ACQUIRING:
                raise InvalidPaymentTypeError(
                    "sync is available only for acquiring payments"
                )
            if not payment.bank_payment_id:
                raise InvalidPaymentStateError(
                    "acquiring payment has no bank payment id"
                )

            bank_state = await self.bank_client.acquiring_check(payment.bank_payment_id)
            if bank_state.amount != payment.amount:
                raise BankDataMismatchError

            payment.bank_status = bank_state.status.value
            payment.bank_checked_at = datetime.now(timezone.utc)
            payment.bank_paid_at = bank_state.paid_at

            if bank_state.status == BankPaymentState.PAID:
                payment.status = PaymentStatus.COMPLETED
            elif bank_state.status == BankPaymentState.FAILED:
                if payment.status == PaymentStatus.COMPLETED:
                    raise BankDataMismatchError
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PENDING

            session.add(payment)

            if payment.order is None:
                raise OrderNotFoundError
            await self._update_order_status(session, payment.order)
            await session.commit()
            await session.refresh(payment)
            return payment

    async def sync_order_acquiring_payments(self, order_id: int) -> list[PaymentModel]:
        async with self.session_factory() as session:
            statement = (
                select(OrderModel)
                .where(OrderModel.id == order_id)
                .options(selectinload(OrderModel.payments))
            )
            result = await session.execute(statement)
            order = result.scalar_one_or_none()
            if order is None:
                raise OrderNotFoundError

            acquiring_payments = [
                payment
                for payment in order.payments
                if payment.type == PaymentType.ACQUIRING
                and payment.status in {PaymentStatus.PENDING, PaymentStatus.COMPLETED}
            ]

        synced_payments: list[PaymentModel] = []
        for payment in acquiring_payments:
            try:
                synced = await self.sync_payment_with_bank(payment.id)
                synced_payments.append(synced)
            except (BankPaymentNotFoundError, BankApiError):
                continue

        return synced_payments


bank_client = BankClient(
    base_url=settings.BANK_API_BASE_URL,
    timeout_seconds=settings.BANK_API_TIMEOUT_SECONDS,
    retries=settings.BANK_API_RETRIES,
)
payment_services = PaymentServices(
    settings.get_db_session(),
    bank_client=bank_client,
)
