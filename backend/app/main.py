import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.deadlines import apply_retention_policy, create_due_alerts

logger = logging.getLogger(__name__)


async def lifecycle_worker() -> None:
    while True:
        try:
            with SessionLocal() as db:
                create_due_alerts(db)
                apply_retention_policy(db)
                db.commit()
        except Exception:
            logger.exception("Lifecycle scan failed")
        await asyncio.sleep(settings.lifecycle_scan_interval_seconds)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(lifecycle_worker())
    yield
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "infobridge-api"}
