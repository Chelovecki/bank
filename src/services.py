from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.db_models import OrderModel, PaymentModel


class BaseService:
    def __init__(self, session):
        self.session_factory: async_sessionmaker[AsyncSession] = session

    async def get_n_rows(
        self, type_model, size: int | None, offset: int | None = None
    ) -> list[OrderModel | PaymentModel]:
        def get_prepared_statement(
            type_model, size: int | None, offset: int | None = None
        ):
            if size is None:
                size = 100
            if offset is None:
                offset = 0

            statement = (
                select(type_model)
                .
                limit(size)
                .offset(offset)
            )

            if type_model == OrderModel:
                statement = statement.options(
                    selectinload(OrderModel.payments))

            return statement

        statement = get_prepared_statement(type_model, size, offset)

        statement = statement.order_by(type_model.id)
        async with self.session_factory() as session:
            res = await session.execute(statement)
            return res.scalars().all()  # type: ignore
