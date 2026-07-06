"""Redis/RQ queue factory helpers."""

from __future__ import annotations

from redis import Redis
from rq import Queue

from src.config.settings import settings


def create_redis_connection(redis_url: str | None = None) -> Redis:
    return Redis.from_url(redis_url or settings.job_queue.redis_url)


def create_queue(*, name: str | None = None, connection: Redis | None = None) -> Queue:
    return Queue(
        name or settings.job_queue.queue_name,
        connection=connection or create_redis_connection(),
    )
