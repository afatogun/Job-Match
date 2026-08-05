"""JobMatch Local backend."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import AUTO_CLEANUP_ON_START
from .db import init_db
from .maintenance import cleanup_storage
from .routers import applications, jobs, profile, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logging.getLogger(__name__).info("Database ready")
    if AUTO_CLEANUP_ON_START:
        summary = cleanup_storage()
        logging.getLogger(__name__).info("Storage cleanup summary: %s", summary)
    yield


app = FastAPI(title="JobMatch Local", version="0.1.0", lifespan=lifespan)

configured_origins = os.getenv("ALLOWED_ORIGINS", "")
allow_origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
if not allow_origins:
    allow_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings.router)
app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(profile.profiles_router)
app.include_router(applications.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
