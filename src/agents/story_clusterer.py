from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.db.session import SessionLocal
from src.models.article import Article
from src.models.story import Story

logger = logging.getLogger(__name__)

# Note: These embedding helpers are temporary and should be replaced with a shared
# import once Issue 9 (dedup agent) is merged.
_model = None

def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def generate_embedding(text: str) -> list[float]:
    model = _get_model()
    # normalize_embeddings=True as per issue instructions
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()

def _embedding_to_json(vector: list[float]) -> str:
    return json.dumps(vector)

def _embedding_from_json(json_str: str) -> list[float]:
    return json.loads(json_str)

def _ensure_embedding(article: Article) -> list[float]:
    if article.embedding_vector is None:
        text_to_embed = f"{article.title} {article.summary or ''} {article.content or ''}".strip()
        vector = generate_embedding(text_to_embed)
        article.embedding_vector = _embedding_to_json(vector)
        return vector
    return _embedding_from_json(article.embedding_vector)


class StoryClusterer:
    def __init__(
        self,
        eps: float = 0.3,
        min_samples: int = 2,
        session_factory: Callable[[], Session] = SessionLocal
    ):
        self.eps = eps
        self.min_samples = min_samples
        self.session_factory = session_factory

    def get_primary_article(self, articles: list[Article]) -> Article:
        """
        Primary-article selection: highest `quality_score`; if null on all candidates,
        fall back to a heuristic combining content length, Source.reliability_score,
        and whether image_url is set.
        """
        if not articles:
            raise ValueError("No articles provided to select primary from.")

        def score_article(a: Article) -> float:
            if a.quality_score is not None:
                return a.quality_score

            score = 0.0
            if a.content:
                score += min(len(a.content) / 1000.0, 5.0)
            if a.image_url:
                score += 2.0
            if a.source and hasattr(a.source, 'reliability_score') and a.source.reliability_score is not None:
                score += a.source.reliability_score
            return score

        return max(articles, key=score_article)

    def cluster_articles(self, articles: list[Article]) -> list[list[Article]]:
        """
        Run sklearn DBSCAN over embeddings. Noise points (label -1) become their own singleton cluster.
        """
        if not articles:
            return []

        embeddings = np.array([_ensure_embedding(a) for a in articles])
        clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="cosine").fit(embeddings)

        clusters_dict: dict[int, list[Article]] = {}
        for idx, label in enumerate(clustering.labels_):
            clusters_dict.setdefault(label, []).append(articles[idx])

        result = []
        for label, group in clusters_dict.items():
            if label == -1:
                for noise_point in group:
                    result.append([noise_point])
            else:
                result.append(group)

        return result

    def match_existing_story(self, article: Article, stories: list[Story], _db: Session) -> Story | None:
        """
        Compare a new article's embedding against the *primary* article's embedding of each candidate story.
        Attach it if within threshold, update article_count and last_updated_at.
        """
        if not stories:
            return None

        article_emb = np.array([_ensure_embedding(article)])

        best_story = None
        best_dist = float('inf')

        for story in stories:
            if not story.articles:
                continue

            primary = self.get_primary_article(story.articles)
            primary_emb = np.array([_ensure_embedding(primary)])

            dist = cosine_distances(article_emb, primary_emb)[0][0]
            if dist <= self.eps and dist < best_dist:
                best_dist = dist
                best_story = story

        if best_story:
            article.story_id = best_story.id
            article.story = best_story
            best_story.article_count += 1
            if article.publish_time:
                if best_story.last_updated_at is None or article.publish_time > best_story.last_updated_at:
                    best_story.last_updated_at = article.publish_time
            return best_story

        return None

    def cluster_recent_articles(self, hours: int = 6) -> list[Story]:
        """
        Pulls unassigned articles published within the window, tries match_existing_story first,
        then DBSCAN-clusters whatever's left into new Story rows.
        """
        db = self.session_factory()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

            unassigned_articles = db.scalars(
                select(Article).where(
                    Article.story_id.is_(None),
                    Article.publish_time >= cutoff
                )
            ).all()

            if not unassigned_articles:
                return []

            recent_stories = db.scalars(
                select(Story)
                .options(joinedload(Story.articles).joinedload(Article.source))
                .where(Story.last_updated_at >= cutoff)
            ).unique().all()

            remaining_articles = []
            for article in unassigned_articles:
                matched = self.match_existing_story(article, recent_stories, db)
                if not matched:
                    remaining_articles.append(article)

            new_stories = []
            if remaining_articles:
                clusters = self.cluster_articles(remaining_articles)
                for cluster in clusters:
                    primary = self.get_primary_article(cluster)

                    publish_times = [a.publish_time for a in cluster if a.publish_time]
                    first_seen = min(publish_times) if publish_times else datetime.now(timezone.utc)
                    last_updated = max(publish_times) if publish_times else datetime.now(timezone.utc)

                    story = Story(
                        title=primary.title,
                        summary=primary.summary,
                        category_slug=primary.category_slug,
                        language=primary.language,
                        image_url=primary.image_url,
                        importance_score=primary.quality_score if primary.quality_score is not None else 0.0,
                        article_count=len(cluster),
                        first_seen_at=first_seen,
                        last_updated_at=last_updated
                    )
                    db.add(story)
                    for a in cluster:
                        a.story = story

                    new_stories.append(story)

            db.commit()
            return new_stories
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
