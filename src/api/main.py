from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api.sources import router as sources_router
from src.api.users import router as users_router
from src.db.session import SessionLocal
from src.scrapers.source_registry import SourceRegistry
from src.scheduler.jobs import ScrapeScheduler
from src.scheduler.scrape_pipeline import ScrapePipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = SourceRegistry()
    pipeline = ScrapePipeline(registry, SessionLocal)
    scheduler = ScrapeScheduler(pipeline, registry)

    app.state.registry = registry
    app.state.scheduler = scheduler

    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="NewsSnap AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sources_router)
app.include_router(users_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
