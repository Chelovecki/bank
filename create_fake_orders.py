import asyncio
import random
from decimal import Decimal

from sqlalchemy import text


from src.settings import PostgresSettings
from src.db_models import OrderModel, OrderPaymentStatus


def random_amount():
    return Decimal(random.randint(100, 5000))

async def truncate_orders():
    async with PostgresSettings.get_session()() as session:
        # Выполняем TRUNCATE команду
        await session.execute(text(f'TRUNCATE TABLE {OrderModel.__tablename__} RESTART IDENTITY CASCADE'))
        await session.commit()
    
    print("Таблица orders успешно очищена")

async def seed_orders(n: int = 20):
    async with PostgresSettings.get_session()() as session:
        orders = []

        for _ in range(n):
            order = OrderModel(
                amount=random_amount(),
                payment_status=OrderPaymentStatus.UNPAID
            )
            orders.append(order)

        session.add_all(orders)
        await session.commit()

    print(f"Inserted {n} random orders")


async def main():
    await truncate_orders()
    await seed_orders(20)


if __name__ == "__main__":
    asyncio.run(main())
