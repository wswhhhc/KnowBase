"""RQ worker entry point for KnowBase background jobs."""

from __future__ import annotations

import logging
import os

from redis import Redis
from rq import SimpleWorker, Worker

from src.config.settings import settings
from src.jobs.queue import create_redis_connection


logger = logging.getLogger(__name__)


def _worker_class_for_platform(os_name: str) -> type[Worker] | type[SimpleWorker]:
    return SimpleWorker if os_name == "nt" else Worker


def create_worker(*, queue_names: list[str] | None = None, connection: Redis | None = None) -> Worker | SimpleWorker:
    redis_connection = connection or create_redis_connection()
    worker_class = _worker_class_for_platform(os.name)
    return worker_class(queue_names or [settings.job_queue.queue_name], connection=redis_connection)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = create_worker()
    logger.info("Starting KnowBase RQ worker for queues: %s", ", ".join(worker.queue_names()))
    worker.work()


if __name__ == "__main__":
    main()
