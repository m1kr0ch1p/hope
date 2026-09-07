from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, DB_PATH, ensure_directories
from app.database import initialize_database
from app.routers import cases, reports, sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("cnpd_osint")


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    initialize_database()
    logger.info("Banco SQLite: %s", DB_PATH.resolve())
    yield


app = FastAPI(title="CNPD-OSINT", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
app.include_router(cases.router)
app.include_router(sync.router)
app.include_router(reports.router)
