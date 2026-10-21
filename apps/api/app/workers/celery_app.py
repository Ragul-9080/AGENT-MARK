from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "agentic_marketing",
    broker=settings.redis_url or "memory://",
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
    task_always_eager=settings.celery_task_always_eager,
    task_routes={
        "app.workers.tasks.promote_scheduled_campaigns": {"queue": "default"},
    },
    beat_schedule={
        "promote-scheduled-campaigns": {
            "task": "app.workers.tasks.promote_scheduled_campaigns",
            "schedule": 60.0,
        }
    },
)

if settings.redis_url:
    celery_app.conf.result_backend = settings.redis_url
