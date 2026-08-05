"""JobMatch Local backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
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
    yield


app = FastAPI(title="JobMatch Local", version="0.1.0", lifespan=lifespan)

# Local single-user app: the Vite dev server is the only client.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings.router)
app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(applications.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
