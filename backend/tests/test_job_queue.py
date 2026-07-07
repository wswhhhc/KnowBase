from __future__ import annotations

import fakeredis
from rq import SimpleWorker, Worker

from src.config.settings import Settings
from src.jobs.queue import create_queue, create_redis_connection
from src.jobs import worker as worker_module


def test_job_queue_settings_defaults_to_local_redis():
    cfg = Settings(_env_file=None)

    assert cfg.job_queue.redis_url == "redis://localhost:6379/0"
    assert cfg.job_queue.queue_name == "knowbase"


def test_create_redis_connection_uses_configured_url_without_connecting():
    connection = create_redis_connection("redis://localhost:6380/5")

    kwargs = connection.connection_pool.connection_kwargs
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 6380
    assert kwargs["db"] == 5


def test_create_queue_uses_given_name_and_connection():
    connection = create_redis_connection("redis://localhost:6380/5")
    queue = create_queue(name="imports", connection=connection)

    assert queue.name == "imports"
    assert queue.connection is connection


def test_worker_class_uses_simple_worker_on_windows():
    assert worker_module._worker_class_for_platform("nt") is SimpleWorker


def test_worker_class_uses_forking_worker_on_posix():
    assert worker_module._worker_class_for_platform("posix") is Worker


def test_create_worker_uses_platform_worker_with_given_queue():
    connection = fakeredis.FakeRedis()

    worker = worker_module.create_worker(queue_names=["imports"], connection=connection)

    assert isinstance(worker, worker_module._worker_class_for_platform(worker_module.os.name))
    assert worker.queue_names() == ["imports"]
