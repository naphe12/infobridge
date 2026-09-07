import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.productivity import router as productivity_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.lifecycle import run_lifecycle_scan
from app.services.platform_settings import get_platform_setting

logger = logging.getLogger(__name__)


async def lifecycle_worker() -> None:
    while True:
        try:
            result = await asyncio.to_thread(run_lifecycle_scan)
            logger.info("Lifecycle scan completed: %s", result)
        except Exception:
            logger.exception("Lifecycle scan failed")
        try:
            with SessionLocal() as db:
                interval_seconds = int(get_platform_setting(db, "lifecycle_interval_seconds"))
        except Exception:
            interval_seconds = settings.lifecycle_scan_interval_seconds
        await asyncio.sleep(max(60, interval_seconds))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(lifecycle_worker()) if settings.lifecycle_worker_enabled else None
    yield
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

app = FastAPI(title="InfoBridge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(productivity_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "infobridge-api"}
