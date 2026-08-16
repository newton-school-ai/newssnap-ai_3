from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.models.article import Article
from src.models.story import Story

router = APIRouter(prefix="/api/stories", tags=["stories"])


class ArticleSummary(BaseModel):
    id: UUID
    title: str
    url: str
    image_url: Optional[str] = None
    publish_time: Optional[datetime] = None
    quality_score: Optional[float] = None

    model_config = {"from_attributes": True}


class StoryResponse(BaseModel):
    id: UUID
    title: str
    summary: Optional[str] = None
    category_slug: str
    language: str
    importance_score: float
    article_count: int
    first_seen_at: datetime
    last_updated_at: datetime
    image_url: Optional[str] = None
    primary_article: Optional[ArticleSummary] = None
    related_articles: list[ArticleSummary] = []

    model_config = {"from_attributes": True}


def _sort_key(article: Article) -> tuple:
    ts = article.publish_time.timestamp() if article.publish_time else 0.0
    return (-(article.quality_score or 0.0), -ts)


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(story_id: UUID, db: Session = Depends(get_db)) -> StoryResponse:
    story = db.scalars(select(Story).where(Story.id == story_id)).first()
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    sorted_articles = sorted(story.articles, key=_sort_key)

    primary: Optional[ArticleSummary] = None
    related: list[ArticleSummary] = []

    if sorted_articles:
        primary = ArticleSummary.model_validate(sorted_articles[0])
        related = [ArticleSummary.model_validate(a) for a in sorted_articles[1:]]

    return StoryResponse(
        id=story.id,
        title=story.title,
        summary=story.summary,
        category_slug=story.category_slug,
        language=story.language,
        importance_score=story.importance_score,
        article_count=story.article_count,
        first_seen_at=story.first_seen_at,
        last_updated_at=story.last_updated_at,
        image_url=story.image_url,
        primary_article=primary,
        related_articles=related,
    )
