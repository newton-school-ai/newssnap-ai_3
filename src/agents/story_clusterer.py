from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_EPS = 0.15
DEFAULT_MIN_SAMPLES = 2
DEFAULT_WINDOW_HOURS = 48
DEFAULT_EXISTING_THRESHOLD = 0.75
MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class ArticleInput:
    article_id: str
    title: str
    content: str
    category_slug: str = "general"
    language: str = "en"
    publish_time: datetime | None = None
    image_url: str | None = None
    quality_score: float = 0.0
    embedding: list[float] = field(default_factory=list)


@dataclass
class StoryCluster:
    primary_article_id: str
    related_article_ids: list[str]


@dataclass
class ClusteringResult:
    stories_created: int
    articles_assigned: int
    noise_count: int


class StoryClusterer:
    def __init__(
        self,
        eps: float = DEFAULT_EPS,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        existing_story_threshold: float = DEFAULT_EXISTING_THRESHOLD,
        model_name: str = MODEL_NAME,
    ):
        self.eps = eps
        self.min_samples = min_samples
        self.window_hours = window_hours
        self.existing_story_threshold = existing_story_threshold
        self._model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, batch_size=32)
        return vecs.tolist()

    def _select_primary(self, members: list[int], articles: list[ArticleInput]) -> int:
        def sort_key(idx: int) -> tuple:
            a = articles[idx]
            ts = a.publish_time.timestamp() if a.publish_time else float("inf")
            return (-a.quality_score, ts)

        return min(members, key=sort_key)

    def cluster(self, articles: list[ArticleInput]) -> list[StoryCluster]:
        from sklearn.cluster import DBSCAN

        if not articles:
            return []

        needs_embedding = [a for a in articles if not a.embedding]
        if needs_embedding:
            texts = [f"{a.title}. {a.content}" for a in needs_embedding]
            embeddings = self.generate_embeddings_batch(texts)
            for article, emb in zip(needs_embedding, embeddings):
                article.embedding = emb

        matrix = np.array([a.embedding for a in articles], dtype=np.float32)
        labels = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric="cosine",
            algorithm="brute",
        ).fit_predict(matrix)

        cluster_map: dict[int, list[int]] = {}
        for i, label in enumerate(labels):
            if label == -1:
                continue
            cluster_map.setdefault(int(label), []).append(i)

        result: list[StoryCluster] = []
        for members in cluster_map.values():
            primary_idx = self._select_primary(members, articles)
            related_ids = [articles[k].article_id for k in members if k != primary_idx]
            result.append(
                StoryCluster(
                    primary_article_id=articles[primary_idx].article_id,
                    related_article_ids=related_ids,
                )
            )

        return result

    def assign_to_existing(
        self,
        embedding: list[float],
        story_centroids: dict[str, list[float]],
    ) -> str | None:
        if not story_centroids or not embedding:
            return None

        va = np.array(embedding, dtype=np.float32)
        norm_a = float(np.linalg.norm(va))
        if norm_a == 0:
            return None
        va = va / norm_a

        best_story_id: str | None = None
        best_sim = self.existing_story_threshold

        for story_id, centroid in story_centroids.items():
            vc = np.array(centroid, dtype=np.float32)
            norm_c = float(np.linalg.norm(vc))
            if norm_c == 0:
                continue
            vc = vc / norm_c
            sim = float(np.dot(va, vc))
            if sim >= best_sim:
                best_sim = sim
                best_story_id = story_id

        return best_story_id

    def run(self, db: Session) -> ClusteringResult:
        from sqlalchemy import select

        from src.models.article import Article
        from src.models.story import Story

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.window_hours)

        rows = db.scalars(
            select(Article)
            .where(Article.publish_time >= cutoff)
            .where(Article.story_id.is_(None))
            .where(Article.duplicate_of_id.is_(None))
            .order_by(Article.publish_time.desc())
        ).all()

        if not rows:
            return ClusteringResult(stories_created=0, articles_assigned=0, noise_count=0)

        articles: list[ArticleInput] = []
        for row in rows:
            stored: list[float] = []
            if row.embedding_vector:
                try:
                    stored = json.loads(row.embedding_vector)
                except Exception:
                    pass
            articles.append(
                ArticleInput(
                    article_id=str(row.id),
                    title=row.title or "",
                    content=row.content or "",
                    category_slug=row.category_slug or "general",
                    language=row.language or "en",
                    publish_time=row.publish_time,
                    image_url=row.image_url,
                    quality_score=row.quality_score or 0.0,
                    embedding=stored,
                )
            )

        # cluster() generates any missing embeddings in-place
        clusters = self.cluster(articles)

        # Persist newly generated embeddings
        id_to_row = {str(r.id): r for r in rows}
        id_to_article = {a.article_id: a for a in articles}
        for row in rows:
            rid = str(row.id)
            art = id_to_article.get(rid)
            if art and art.embedding and not row.embedding_vector:
                row.embedding_vector = json.dumps(art.embedding)

        # Compute centroids for existing stories to assign noise articles
        existing_stories = db.scalars(
            select(Story).where(Story.last_updated_at >= cutoff)
        ).all()

        story_centroids: dict[str, list[float]] = {}
        for story in existing_stories:
            embs = [
                json.loads(a.embedding_vector)
                for a in story.articles
                if a.embedding_vector
            ]
            if embs:
                centroid = np.mean(np.array(embs, dtype=np.float32), axis=0).tolist()
                story_centroids[str(story.id)] = centroid

        clustered_ids: set[str] = set()
        for sc in clusters:
            clustered_ids.add(sc.primary_article_id)
            clustered_ids.update(sc.related_article_ids)

        noise_articles = [a for a in articles if a.article_id not in clustered_ids]

        stories_created = 0
        articles_assigned = 0

        for sc in clusters:
            primary_art = id_to_article[sc.primary_article_id]
            all_members = [id_to_article[aid] for aid in [sc.primary_article_id] + sc.related_article_ids]

            publish_times = [a.publish_time for a in all_members if a.publish_time]
            now = datetime.now(timezone.utc)
            first_seen = min(publish_times) if publish_times else now
            last_updated = max(publish_times) if publish_times else now
            avg_quality = sum(a.quality_score for a in all_members) / len(all_members)

            story = Story(
                id=uuid.uuid4(),
                title=primary_art.title,
                category_slug=primary_art.category_slug,
                language=primary_art.language,
                importance_score=avg_quality,
                article_count=len(all_members),
                first_seen_at=first_seen,
                last_updated_at=last_updated,
                image_url=primary_art.image_url,
            )
            db.add(story)
            db.flush()

            for art in all_members:
                row = id_to_row.get(art.article_id)
                if row is not None:
                    row.story_id = story.id
                    articles_assigned += 1

            stories_created += 1

        noise_assigned = 0
        for art in noise_articles:
            story_id = self.assign_to_existing(art.embedding, story_centroids)
            if story_id is not None:
                row = id_to_row.get(art.article_id)
                if row is not None:
                    row.story_id = story_id
                    articles_assigned += 1
                    noise_assigned += 1

        db.commit()

        logger.info(
            "Clustering: %d stories created, %d assigned, %d noise",
            stories_created,
            articles_assigned,
            len(noise_articles) - noise_assigned,
        )

        return ClusteringResult(
            stories_created=stories_created,
            articles_assigned=articles_assigned,
            noise_count=len(noise_articles) - noise_assigned,
        )
