from __future__ import annotations

from src.config.settings import Settings
from src.jobs.queue import create_queue, create_redis_connection


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
