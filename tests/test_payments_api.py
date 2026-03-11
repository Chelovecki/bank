from decimal import Decimal

from src.api.bank_client import BankPaymentState
from src.db_models import PaymentType


async def test_cash_payment_updates_order_status(api_client, create_order):
    order = await create_order(Decimal("100.00"))

    response = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "40.00", "type": PaymentType.CASH.value},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"

    order_response = await api_client.get(f"/orders/{order.id}")
    assert order_response.status_code == 200
    assert order_response.json()["payment_status"] == "PARTIALLY_PAID"

    response = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "60.00", "type": PaymentType.CASH.value},
    )
    assert response.status_code == 200

    order_response = await api_client.get(f"/orders/{order.id}")
    assert order_response.status_code == 200
    assert order_response.json()["payment_status"] == "PAID"


async def test_cannot_exceed_order_amount(api_client, create_order):
    order = await create_order(Decimal("100.00"))

    first = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "70.00", "type": PaymentType.CASH.value},
    )
    assert first.status_code == 200

    second = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "31.00", "type": PaymentType.CASH.value},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Sum of payments exceeds order amount"


async def test_acquiring_payment_created_in_pending_status(
    api_client,
    create_order,
):
    order = await create_order(Decimal("100.00"))

    response = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "30.00", "type": PaymentType.ACQUIRING.value},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["bank_payment_id"].startswith("bp-")
    assert body["bank_status"] == "PENDING"


async def test_sync_acquiring_payment_marks_order_paid(
    api_client,
    create_order,
    fake_bank_client,
):
    order = await create_order(Decimal("100.00"))
    created = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "100.00", "type": PaymentType.ACQUIRING.value},
    )
    assert created.status_code == 200
    payment = created.json()
    payment_id = payment["id"]
    bank_payment_id = payment["bank_payment_id"]

    fake_bank_client.set_state(
        bank_payment_id=bank_payment_id,
        amount=Decimal("100.00"),
        status=BankPaymentState.PAID,
    )
    sync_response = await api_client.post(f"/payments/{payment_id}/sync")
    assert sync_response.status_code == 200
    assert sync_response.json()["status"] == "COMPLETED"

    order_response = await api_client.get(f"/orders/{order.id}")
    assert order_response.status_code == 200
    assert order_response.json()["payment_status"] == "PAID"


async def test_refund_completed_payment_updates_order_status(api_client, create_order):
    order = await create_order(Decimal("100.00"))
    created = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "100.00", "type": PaymentType.CASH.value},
    )
    assert created.status_code == 200
    payment_id = created.json()["id"]

    refund = await api_client.post(f"/payments/{payment_id}/refund")
    assert refund.status_code == 200
    assert refund.json()["status"] == "REFUNDED"

    order_response = await api_client.get(f"/orders/{order.id}")
    assert order_response.status_code == 200
    assert order_response.json()["payment_status"] == "UNPAID"


async def test_refund_pending_payment_returns_conflict(api_client, create_order):
    order = await create_order(Decimal("100.00"))
    created = await api_client.post(
        f"/orders/{order.id}/payments",
        json={"amount": "50.00", "type": PaymentType.ACQUIRING.value},
    )
    assert created.status_code == 200

    payment_id = created.json()["id"]
    refund = await api_client.post(f"/payments/{payment_id}/refund")
    assert refund.status_code == 409
    assert refund.json()["detail"] == "Only completed payments can be refunded"
