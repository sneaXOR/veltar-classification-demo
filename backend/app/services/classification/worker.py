from __future__ import annotations

import asyncio
import logging
import time

from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.classification.job_runner import process_job, recover_incomplete_jobs
from app.services.classification.queue import dequeue_classification_job, get_worker_identity

logger = logging.getLogger(__name__)


async def _run_single_job(job_id, *, worker_id: str, semaphore: asyncio.Semaphore) -> None:
    try:
        await process_job(job_id, worker_id=worker_id)
    except Exception:  # pragma: no cover
        logger.exception("Worker job failed for %s", job_id)
    finally:
        semaphore.release()


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL must be configured to run the dedicated worker.")

    stop_event = stop_event or asyncio.Event()
    worker_id = get_worker_identity()
    concurrency = max(1, int(settings.worker_job_concurrency))
    poll_timeout = max(1, int(settings.worker_poll_timeout_seconds))
    recovery_interval = max(5, int(settings.recovery_poll_interval_seconds))
    semaphore = asyncio.Semaphore(concurrency)
    tasks: set[asyncio.Task[None]] = set()
    last_recovery_started = 0.0

    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        try:
            recovered_jobs = await recover_incomplete_jobs(requeue_queued=True)
            if recovered_jobs:
                logger.info("Worker queued %s recoverable classification job(s) on startup", recovered_jobs)
        except Exception:  # pragma: no cover
            logger.exception("Worker startup recovery pass failed")

        last_recovery_started = time.monotonic()
        while not stop_event.is_set():
            now = time.monotonic()
            if now - last_recovery_started >= recovery_interval:
                last_recovery_started = now
                try:
                    recovered_jobs = await recover_incomplete_jobs(requeue_queued=False)
                    if recovered_jobs:
                        logger.info("Worker recovered %s stale classification job(s)", recovered_jobs)
                except Exception:  # pragma: no cover
                    logger.exception("Worker recovery pass failed")

            await semaphore.acquire()
            try:
                job_id = await dequeue_classification_job(client, timeout=poll_timeout)
            except Exception:  # pragma: no cover
                semaphore.release()
                logger.exception("Worker dequeue failed")
                await asyncio.sleep(2)
                continue

            if job_id is None:
                semaphore.release()
                continue

            task = asyncio.create_task(_run_single_job(job_id, worker_id=worker_id, semaphore=semaphore))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await client.aclose()
