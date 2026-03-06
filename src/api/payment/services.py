from decimal import Decimal
from sqlalchemy import select

from sqlalchemy.orm import selectinload

from src.db_models import OrderModel, OrderPaymentStatus, PaymentModel, PaymentStatus
from src.services import BaseService
from src.settings import PostgresSettings


class PaymentServices(BaseService):
    def __init__(self, session):
        super().__init__(session)

    def _calculate_order_status(self, order_amount: Decimal, payments: list[PaymentModel]) -> OrderPaymentStatus:
        """Вычисляет статус заказа на основе всех платежей"""
        net_paid = sum(
            p.amount for p in payments
            if p.status == PaymentStatus.COMPLETED
        ) - sum(
            p.amount for p in payments
            if p.status == PaymentStatus.REFUNDED
        )

        if net_paid <= 0:
            return OrderPaymentStatus.UNPAID
        elif net_paid >= order_amount:
            return OrderPaymentStatus.PAID
        else:
            return OrderPaymentStatus.PARTIALLY_PAID

    async def update_status(self, payment: PaymentModel, order_id: int):
        async with self.session_factory() as session:
            # Загружаем заказ с платежами
            query = (
                select(OrderModel)
                .where(OrderModel.id == order_id)
                .options(selectinload(OrderModel.payments))
            )
            result = await session.execute(query)
            order = result.scalar_one_or_none()

            if not order:
                return False

            # Обновляем статус на основе всех платежей
            order.payment_status = self._calculate_order_status(
                order.amount, order.payments)

            session.add(order)
            await session.commit()

            return True

    async def create_payment(self, order_id: int, amount: Decimal, type: str) -> PaymentModel:
        payment = PaymentModel(
            order_id=order_id,
            amount=amount,
            type=type
        )
        if payment.type == "CASH":
            payment.status = PaymentStatus.COMPLETED

        async with self.session_factory() as session:
            session.add(payment)
            await session.commit()
            await session.refresh(payment)
            await self.update_status(payment, order_id)
            return payment

    async def get_payment(self, payment_id: int) -> PaymentModel | None:
        async with self.session_factory() as session:
            query = select(PaymentModel).where(PaymentModel.id == payment_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def refund_payment(self, payment_id: int) -> PaymentModel | None:
        async with self.session_factory() as session:
            payment = await session.get(PaymentModel, payment_id)

            if not payment or payment.status != PaymentStatus.COMPLETED:
                return None

            payment.status = PaymentStatus.REFUNDED
            session.add(payment)
            await session.commit()
            await session.refresh(payment)

            await self.update_status(payment, payment.order_id)

            return payment


payment_services = PaymentServices(PostgresSettings.get_session())
