from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.middleware import CurrentUser, require_admin
from src.db.session import get_db
from src.models.article import Article
from src.scrapers.source_registry import SourceRegistry

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_registry(request: Request) -> SourceRegistry:
    registry = getattr(request.app.state, "registry", None)
    if registry is None:
        registry = SourceRegistry()
    return registry


@router.get("/scrape-health")
def get_scrape_health(
    request: Request,
    user: CurrentUser = Depends(require_admin),
) -> dict:
    registry = _get_registry(request)
    health_map = registry.get_all_health()
    return {
        "sources": {
            name: {
                "is_healthy": h.is_healthy,
                "success_count": h.success_count,
                "error_count": h.error_count,
                "consecutive_failures": h.consecutive_failures,
                "success_rate": round(h.success_rate, 4),
                "last_scrape_time": h.last_scrape_time.isoformat() if h.last_scrape_time else None,
                "last_error": h.last_error,
            }
            for name, h in health_map.items()
        }
    }


@router.post("/trigger-scrape")
async def trigger_scrape(
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(require_admin),
) -> dict:
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        return {"status": "scheduler_not_running"}
    background_tasks.add_task(scheduler._run_all_sources)
    return {"status": "triggered"}


@router.get("/rejected-articles")
def get_rejected_articles(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    articles = db.scalars(
        select(Article)
        .where(Article.is_rejected.is_(True))
        .order_by(Article.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    total = db.scalar(
        select(func.count()).select_from(Article).where(Article.is_rejected.is_(True))
    ) or 0

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "articles": [
            {
                "id": str(a.id),
                "title": a.title,
                "url": a.url,
                "category_slug": a.category_slug,
                "quality_score": a.quality_score,
                "rejection_reason": a.rejection_reason,
                "source_id": str(a.source_id) if a.source_id else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in articles
        ],
    }
