from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

QUEUE_STATE_KEY = "queue"
TIMINGS_KEY = "timings"

_INLINE_TASKS: set[asyncio.Task[None]] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_queue_state(
    *,
    state: str = "queued",
    enqueued_at: datetime | None = None,
    started_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    lease_until: datetime | None = None,
    attempts: int = 0,
    worker_id: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "enqueued_at": _serialize_datetime(enqueued_at),
        "started_at": _serialize_datetime(started_at),
        "heartbeat_at": _serialize_datetime(heartbeat_at),
        "lease_until": _serialize_datetime(lease_until),
        "attempts": attempts,
        "worker_id": worker_id,
        "error_message": error_message,
    }


def build_gate_report(
    *,
    queue_state: dict[str, Any] | None = None,
    progress: dict[str, Any] | None = None,
    timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    if queue_state is not None:
        report[QUEUE_STATE_KEY] = queue_state
    if progress is not None:
        report["progress"] = progress
    if timings is not None:
        report[TIMINGS_KEY] = timings
    return report


def extract_queue_state(gate_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(gate_report, dict):
        return None
    queue_state = gate_report.get(QUEUE_STATE_KEY)
    return queue_state if isinstance(queue_state, dict) else None


def extract_timings(gate_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(gate_report, dict):
        return None
    timings = gate_report.get(TIMINGS_KEY)
    return timings if isinstance(timings, dict) else None


def parse_gate_datetime(raw: Any) -> datetime | None:
    return _parse_datetime(raw)


def get_worker_identity() -> str:
    settings = get_settings()
    return f"{settings.worker_identity}-{os.getpid()}"


def is_redis_enabled() -> bool:
    settings = get_settings()
    return bool(settings.redis_url)


async def enqueue_classification_job(job_id: UUID) -> str:
    settings = get_settings()
    if not settings.redis_url:
        _enqueue_inline(job_id)
        return "inline"

    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.rpush(settings.redis_queue_name, str(job_id))
        finally:
            await client.aclose()
        return "redis"
    except Exception:
        logger.exception("Redis enqueue failed for %s; falling back to inline execution", job_id)
        _enqueue_inline(job_id)
        return "inline"


async def dequeue_classification_job(client: Redis, *, timeout: int) -> UUID | None:
    settings = get_settings()
    message = await client.blpop(settings.redis_queue_name, timeout=timeout)
    if not message:
        return None
    _, raw_job_id = message
    try:
        return UUID(str(raw_job_id))
    except ValueError:
        logger.warning("Discarding invalid queued job id: %s", raw_job_id)
        return None


def _enqueue_inline(job_id: UUID) -> None:
    from app.services.classification.job_runner import process_job

    task = asyncio.create_task(process_job(job_id))
    _INLINE_TASKS.add(task)
    task.add_done_callback(_INLINE_TASKS.discard)
