"""NewsSnap AI - Stories API module."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.db.session import get_db
from src.models.story import Story

router = APIRouter(prefix="/api/stories", tags=["stories"])


class ArticleResponse(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    source_id: uuid.UUID | None = None
    image_url: str | None = None
    publish_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class StoryResponse(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None = None
    category_slug: str
    language: str
    importance_score: float
    article_count: int
    first_seen_at: datetime
    last_updated_at: datetime
    image_url: str | None = None

    primary_article: ArticleResponse
    related_articles: list[ArticleResponse]

    model_config = ConfigDict(from_attributes=True)


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(story_id: uuid.UUID, db: Session = Depends(get_db)):
    story = db.execute(
        select(Story)
        .options(joinedload(Story.articles))
        .where(Story.id == story_id)
    ).unique().scalar_one_or_none()

    if not story or not story.articles:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    scored = [a for a in story.articles if a.quality_score is not None]
    if scored:
        primary_article = max(scored, key=lambda a: float(a.quality_score))
    else:
        primary_article = max(story.articles, key=lambda a: len(a.content or ""))

    related_articles = [a for a in story.articles if a.id != primary_article.id]

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
        primary_article=primary_article,
        related_articles=related_articles,
    )
