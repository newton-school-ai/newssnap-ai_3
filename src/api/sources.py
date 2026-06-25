from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.scrapers.source_registry import SourceRegistry

router = APIRouter(prefix="/api/sources", tags=["sources"])

registry = SourceRegistry()


class SourceResponse(BaseModel):
    name: str
    base_url: str
    scrape_type: str
    language: str
    category_slug: str
    is_active: bool
    priority: int


class SourceHealthResponse(BaseModel):
    name: str
    last_scrape_time: Optional[str] = None
    success_count: int
    error_count: int
    success_rate: float
    is_healthy: bool
    last_error: Optional[str] = None


class SourceWithHealthResponse(BaseModel):
    source: SourceResponse
    health: SourceHealthResponse


@router.get("", response_model=list[SourceWithHealthResponse])
def list_sources(
    language: Optional[str] = Query(None, description="Filter by language code"),
    scrape_type: Optional[str] = Query(None, description="Filter by scrape type"),
    active_only: bool = Query(False, description="Only return active sources"),
):
    if active_only:
        sources = registry.get_active_sources()
    elif language:
        sources = registry.get_sources_by_language(language)
    elif scrape_type:
        sources = registry.get_sources_by_type(scrape_type)
    else:
        sources = registry.get_all_sources()

    results = []
    for src in sources:
        health = registry.get_health(src.name)
        results.append(
            SourceWithHealthResponse(
                source=SourceResponse(
                    name=src.name,
                    base_url=src.base_url,
                    scrape_type=src.scrape_type,
                    language=src.language,
                    category_slug=src.category_slug,
                    is_active=src.is_active,
                    priority=src.priority,
                ),
                health=SourceHealthResponse(
                    name=src.name,
                    last_scrape_time=health.last_scrape_time.isoformat() if health and health.last_scrape_time else None,
                    success_count=health.success_count if health else 0,
                    error_count=health.error_count if health else 0,
                    success_rate=health.success_rate if health else 1.0,
                    is_healthy=health.is_healthy if health else True,
                    last_error=health.last_error if health else None,
                ),
            )
        )
    return results


@router.get("/health", response_model=list[SourceHealthResponse])
def list_source_health():
    all_health = registry.get_all_health()
    results = []
    for name, health in all_health.items():
        results.append(
            SourceHealthResponse(
                name=name,
                last_scrape_time=health.last_scrape_time.isoformat() if health.last_scrape_time else None,
                success_count=health.success_count,
                error_count=health.error_count,
                success_rate=health.success_rate,
                is_healthy=health.is_healthy,
                last_error=health.last_error,
            )
        )
    return results
