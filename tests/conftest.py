from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.bank_client import BankCheckResult, BankPaymentState
from src.api.orders.services import order_services
from src.api.payment.services import payment_services
from src.db_models import Base, OrderModel, OrderPaymentStatus, PaymentType
from src.main import app
from src.settings import settings


class FakeBankClient:
    def __init__(self) -> None:
        self._sequence = 0
        self._states: dict[str, BankCheckResult] = {}

    async def acquiring_start(self, order_id: int, amount: Decimal) -> str:
        self._sequence += 1
        bank_payment_id = f"bp-{order_id}-{self._sequence}"
        self._states[bank_payment_id] = BankCheckResult(
            bank_payment_id=bank_payment_id,
            amount=amount,
            status=BankPaymentState.PENDING,
            paid_at=None,
        )
        return bank_payment_id

    async def acquiring_check(self, bank_payment_id: str) -> BankCheckResult:
        return self._states[bank_payment_id]

    def set_state(
        self,
        bank_payment_id: str,
        amount: Decimal,
        status: BankPaymentState,
    ) -> None:
        paid_at = (
            datetime.now(timezone.utc) if status == BankPaymentState.PAID else None
        )
        self._states[bank_payment_id] = BankCheckResult(
            bank_payment_id=bank_payment_id,
            amount=amount,
            status=status,
            paid_at=paid_at,
        )


@pytest_asyncio.fixture()
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(settings.ASYNC_URL, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture()
async def fake_bank_client() -> AsyncGenerator[FakeBankClient, None]:
    old_bank_client = payment_services.bank_client
    fake = FakeBankClient()
    payment_services.bank_client = fake
    try:
        yield fake
    finally:
        payment_services.bank_client = old_bank_client


@pytest_asyncio.fixture()
async def patch_services(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    old_order_factory = order_services.session_factory
    old_payment_factory = payment_services.session_factory
    order_services.session_factory = session_factory
    payment_services.session_factory = session_factory
    try:
        yield
    finally:
        order_services.session_factory = old_order_factory
        payment_services.session_factory = old_payment_factory


@pytest_asyncio.fixture()
async def api_client(
    patch_services: None, fake_bank_client: FakeBankClient
) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture()
async def create_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator:
    async def _create(amount: Decimal) -> OrderModel:
        async with session_factory() as session:
            order = OrderModel(amount=amount, payment_status=OrderPaymentStatus.UNPAID)
            session.add(order)
            await session.commit()
            await session.refresh(order)
            return order

    yield _create


def payload_for(amount: Decimal, payment_type: PaymentType) -> dict:
    return {"amount": str(amount), "type": payment_type.value}
