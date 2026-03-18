import asyncio

from src.api.payment.services import payment_services
from src.celery_app import celery_app


@celery_app.task(name="src.tasks.poll_pending_payments")
def poll_pending_payments() -> int:
    return asyncio.run(payment_services.sync_pending_acquiring_payments())
