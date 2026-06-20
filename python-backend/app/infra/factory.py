from functools import lru_cache

from app.core.config import settings
from app.infra.idempotency import IdempotencyStore, InMemoryIdempotencyStore, RedisIdempotencyStore
from app.infra.task_queue import InMemoryTaskQueue, RedisStreamTaskQueue, RocketMQTaskQueue, TaskQueue
from app.infra.thread_pool import WorkerThreadPool


@lru_cache
def get_task_queue() -> TaskQueue:
    backend = settings.rag_task_queue_backend.lower()
    if backend == "redis":
        return RedisStreamTaskQueue(
            redis_url=settings.redis_url,
            key_prefix=settings.rag_task_queue_key_prefix,
        )
    if backend == "rocketmq":
        return RocketMQTaskQueue(
            name_server=settings.rocketmq_name_server,
            producer_group=settings.rocketmq_producer_group,
            consumer_group=settings.rocketmq_consumer_group,
            topic=settings.rocketmq_topic,
            dlq_topic=settings.rocketmq_dlq_topic,
            max_attempts=settings.rocketmq_max_consume_attempts,
        )
    return InMemoryTaskQueue()


@lru_cache
def get_idempotency_store() -> IdempotencyStore:
    if settings.rag_task_queue_backend.lower() in {"redis", "rocketmq"}:
        return RedisIdempotencyStore(
            redis_url=settings.redis_url,
            key_prefix=f"{settings.rag_task_queue_key_prefix}:idempotency",
        )
    return InMemoryIdempotencyStore()


@lru_cache
def get_worker_thread_pool() -> WorkerThreadPool:
    return WorkerThreadPool(max_workers=settings.rag_worker_thread_pool_size)
