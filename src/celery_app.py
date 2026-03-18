from celery import Celery

from src.settings import settings

celery_app = Celery(
    "bank",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    timezone="Europe/Moscow",
    beat_schedule={
        "poll-pending-payments": {
            "task": "src.tasks.poll_pending_payments",
            "schedule": settings.CELERY_POLL_PENDING_PAYMENTS_INTERVAL_SECONDS,
        }
    },
)

celery_app.autodiscover_tasks(["src"])
