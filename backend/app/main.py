from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.artifacts import router as artifacts_router
from app.api.clients import router as clients_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import batch_router, router as documents_router
from app.api.exports import router as exports_router
from app.api.integrations import router as integrations_router
from app.api.jobs import router as jobs_router
from app.api.reviews import router as reviews_router
from app.api.settings import router as settings_router
from app.core.config import get_settings
from app.db.session import init_db
from app.services.classification.job_runner import recover_incomplete_jobs


settings = get_settings()
logger = logging.getLogger(__name__)


async def _recovery_loop(stop_event: asyncio.Event) -> None:
    interval_seconds = max(5, int(settings.recovery_poll_interval_seconds))
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            try:
                recovered_jobs = await recover_incomplete_jobs(requeue_queued=False)
                if recovered_jobs:
                    logger.info("Recovered %s stale classification job(s)", recovered_jobs)
            except Exception:  # pragma: no cover
                logger.exception("Background recovery pass failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    stop_event = asyncio.Event()
    recovery_task = None
    if not settings.redis_url:
        await recover_incomplete_jobs(requeue_queued=True)
        recovery_task = asyncio.create_task(_recovery_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        if recovery_task is not None:
            recovery_task.cancel()
            with suppress(asyncio.CancelledError):
                await recovery_task


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Standalone export control classifier.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artifacts_router, prefix=settings.api_prefix)
app.include_router(clients_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(batch_router, prefix=settings.api_prefix)
app.include_router(jobs_router, prefix=settings.api_prefix)
app.include_router(reviews_router, prefix=settings.api_prefix)
app.include_router(settings_router, prefix=settings.api_prefix)
app.include_router(exports_router, prefix=settings.api_prefix)
app.include_router(integrations_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.app_name, "api_prefix": settings.api_prefix}


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
