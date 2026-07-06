from __future__ import annotations

import logging
import sys
from pathlib import Path

from rq import SimpleWorker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.config.settings import settings
from src.jobs.queue import create_redis_connection


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    connection = create_redis_connection()
    worker = SimpleWorker([settings.job_queue.queue_name], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
