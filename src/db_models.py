import enum
from decimal import Decimal
from datetime import datetime
from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Numeric, String, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class OrderPaymentStatus(enum.Enum):
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"


class PaymentType(enum.Enum):
    CASH = "CASH"
    ACQUIRING = "ACQUIRING"


class PaymentStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    payment_status: Mapped[OrderPaymentStatus] = mapped_column(
        Enum(OrderPaymentStatus, native_enum=False),
        default=OrderPaymentStatus.UNPAID,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    payments: Mapped[list['PaymentModel']] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"
    )


class PaymentModel(Base):
    __tablename__ = 'payments'

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        CheckConstraint('amount > 0'),
        nullable=False
    )

    type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, native_enum=False),
        nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True
    )
    bank_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey('orders.id', ondelete='CASCADE'),
        index=True
    )
    order: Mapped['OrderModel'] = relationship(
        back_populates='payments')
