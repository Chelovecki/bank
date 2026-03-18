from typing import Sequence

from sqlalchemy import select

from src.db_models import OrderModel, PaymentModel
from src.services import BaseService
from src.settings import settings


class OrderServices(BaseService):
    def __init__(self, session):
        super().__init__(session)

    async def get_order(self, order_id: int) -> OrderModel | None:

        async with self.session_factory() as session:
            return await session.get(OrderModel, order_id)

    async def get_order_payments(self, order_id: int) -> Sequence[PaymentModel] | None:
        async with self.session_factory() as session:
            order = await session.get(OrderModel, order_id)

            if order is None:
                return None
            query = select(PaymentModel).where(PaymentModel.order_id == order_id)
            result = await session.execute(query)

            return result.scalars().all()


order_services = OrderServices(settings.get_db_session())
