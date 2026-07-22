"""
Celery Application Configuration.
"""

import os
from celery import Celery
from core.config import settings

# Initialize Celery app
celery_app = Celery(
    "aca_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Restart worker process if it consumes too much memory (leak prevention)
    worker_max_memory_per_child=500000,  # 500MB
    # Prevent long-running tasks from blocking everything
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,
)
