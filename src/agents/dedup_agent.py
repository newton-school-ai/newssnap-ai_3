"""NewsSnap AI - Deduplication Agent.

Uses sentence-transformers (all-MiniLM-L6-v2) to compute embeddings for articles
and identifies near-duplicate articles via cosine similarity. When a duplicate
cluster is found, the article from the highest-priority source (lowest priority
number) is kept as the canonical "parent"; the others are linked via parent_id
and annotated as "also reported by".

Acceptance criteria:
  - Paraphrased duplicates identified at cosine similarity > 0.85
  - Unique articles pass through untouched
  - Primary article chosen from highest-priority source
  - Comparison window configurable (default 48 hours)
  - Batch-processes 100+ articles in < 5 seconds
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.article import Article
from src.models.source import Source

logger = logging.getLogger(__name__)

# Singleton model – loaded once per process so repeated calls are fast
_MODEL: Optional[SentenceTransformer] = None
MODEL_NAME = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.85


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        logger.info("Loading SentenceTransformer model: %s", MODEL_NAME)
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def _article_text(article: Article) -> str:
    """Concatenate title and content for embedding."""
    parts = [article.title or ""]
    if article.content:
        # Use only the first 512 characters of body to stay within model context
        parts.append(article.content[:512])
    elif article.summary:
        parts.append(article.summary[:512])
    return " ".join(parts).strip()


def generate_embeddings(texts: list[str]) -> np.ndarray:
    """Generate L2-normalised embeddings for a list of texts in one batch call.

    Returns shape (N, 384) float32 array.
    """
    model = _get_model()
    embeddings = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    return embeddings  # already normalised → dot product == cosine similarity


def _embedding_to_json(vec: np.ndarray) -> str:
    return json.dumps(vec.tolist())


def _embedding_from_json(s: str) -> np.ndarray:
    return np.array(json.loads(s), dtype=np.float32)


def _source_priority(article: Article, db: Session) -> int:
    """Return the priority of the article's source (lower = better). Defaults to 999 if unknown."""
    if article.source_id is None:
        return 999
    source = db.get(Source, article.source_id)
    if source is None:
        return 999
    return source.priority


# ---------------------------------------------------------------------------
# Core deduplication logic
# ---------------------------------------------------------------------------

class DeduplicationResult:
    """Summarises what happened in a dedup run."""

    def __init__(self) -> None:
        self.total: int = 0
        self.unique: int = 0
        self.duplicates_found: int = 0
        self.elapsed_seconds: float = 0.0

    def __repr__(self) -> str:
        return (
            f"DeduplicationResult(total={self.total}, unique={self.unique}, "
            f"duplicates={self.duplicates_found}, elapsed={self.elapsed_seconds:.2f}s)"
        )


class DeduplicationAgent:
    """Identifies and links duplicate articles using semantic embeddings."""

    def __init__(
        self,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        window_hours: int = 48,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.window_hours = window_hours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deduplicate_batch(self, articles: list[Article], db: Session) -> DeduplicationResult:
        """Deduplicate a list of in-memory Article objects.

        For each article, its embedding is computed (or reused from
        ``embedding_vector``). Articles within ``window_hours`` that exceed
        ``similarity_threshold`` are grouped; the article from the
        highest-priority source becomes the canonical parent, and the others
        are marked as duplicates via ``parent_id``.

        Changes are written to the session but NOT committed – caller is
        responsible for committing.
        """
        t_start = time.monotonic()
        result = DeduplicationResult()
        result.total = len(articles)

        if not articles:
            result.elapsed_seconds = time.monotonic() - t_start
            return result

        # --- Compute / reuse embeddings ---
        texts = [_article_text(a) for a in articles]
        vecs = self._load_or_compute_embeddings(articles, texts)

        # Persist embeddings back onto the articles
        for article, vec in zip(articles, vecs):
            if article.embedding_vector is None:
                article.embedding_vector = _embedding_to_json(vec)

        # --- Build similarity matrix and cluster duplicates ---
        # vecs is already L2-normalised, so dot product == cosine similarity
        sim_matrix = np.dot(vecs, vecs.T)

        n = len(articles)
        assigned: list[Optional[int]] = [None] * n  # assigned[i] = cluster representative index

        for i in range(n):
            if assigned[i] is not None:
                continue
            # Start a new cluster with i as tentative representative
            assigned[i] = i
            for j in range(i + 1, n):
                if assigned[j] is not None:
                    continue
                if not self._within_window(articles[i], articles[j]):
                    continue
                if sim_matrix[i, j] >= self.similarity_threshold:
                    # j is a duplicate of i's cluster
                    assigned[j] = i

        # --- Resolve clusters: pick the best source as parent ---
        clusters: dict[int, list[int]] = {}
        for idx, rep in enumerate(assigned):
            if rep is None:
                continue  # shouldn't happen
            clusters.setdefault(rep, []).append(idx)

        for rep_idx, member_idxs in clusters.items():
            if len(member_idxs) == 1:
                result.unique += 1
                continue

            # Choose the article with the lowest priority number (= highest quality source)
            best_idx = min(member_idxs, key=lambda idx: _source_priority(articles[idx], db))
            parent_article = articles[best_idx]

            for idx in member_idxs:
                if idx == best_idx:
                    continue
                dup_article = articles[idx]
                dup_article.parent_id = parent_article.id
                result.duplicates_found += 1

            # Update the parent's duplicate_count
            parent_article.duplicate_count = len(member_idxs) - 1

        result.elapsed_seconds = time.monotonic() - t_start
        logger.info(
            "Dedup batch: %d articles, %d unique, %d duplicates in %.2fs",
            result.total,
            result.unique,
            result.duplicates_found,
            result.elapsed_seconds,
        )
        return result

    def deduplicate_new_article(self, article: Article, db: Session) -> Optional[Article]:
        """Check a single new article against recent articles in the database.

        Returns the parent Article if a duplicate is found, otherwise None.
        The ``article`` is modified in-place (parent_id set) if it is a duplicate.
        Changes are NOT committed.
        """
        window_start = datetime.now(timezone.utc) - timedelta(hours=self.window_hours)

        # Fetch recent candidate articles from the DB
        stmt = (
            select(Article)
            .where(Article.created_at >= window_start)
            .where(Article.id != article.id)
            .where(Article.parent_id.is_(None))  # only compare against canonical articles
        )
        candidates = list(db.execute(stmt).scalars().all())

        if not candidates:
            return None

        # Compute embedding for the new article
        new_text = _article_text(article)
        new_vec = generate_embeddings([new_text])[0]
        article.embedding_vector = _embedding_to_json(new_vec)

        # Load or compute candidate embeddings
        cand_texts = [_article_text(c) for c in candidates]
        cand_vecs = self._load_or_compute_embeddings(candidates, cand_texts)

        sims = np.dot(cand_vecs, new_vec)  # (N,)
        best_match_idx = int(np.argmax(sims))
        best_sim = float(sims[best_match_idx])

        if best_sim < self.similarity_threshold:
            return None

        # Determine which is the parent based on source priority
        candidate = candidates[best_match_idx]
        new_priority = _source_priority(article, db)
        cand_priority = _source_priority(candidate, db)

        if new_priority <= cand_priority:
            # New article is higher (or equal) priority → it becomes the parent
            # Re-parent the existing candidate onto the new article
            candidate.parent_id = article.id
            candidate.duplicate_count = 0
            article.duplicate_count = (article.duplicate_count or 0) + 1
            return None  # new article is NOT marked as a duplicate
        else:
            # Existing candidate is higher priority → mark new article as duplicate
            article.parent_id = candidate.id
            candidate.duplicate_count = (candidate.duplicate_count or 0) + 1
            return candidate

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_or_compute_embeddings(
        self, articles: list[Article], texts: list[str]
    ) -> np.ndarray:
        """Return embedding matrix; reuse stored embeddings where available."""
        vecs: list[Optional[np.ndarray]] = [None] * len(articles)
        to_compute_idxs: list[int] = []
        to_compute_texts: list[str] = []

        for i, article in enumerate(articles):
            if article.embedding_vector:
                try:
                    vecs[i] = _embedding_from_json(article.embedding_vector)
                    continue
                except Exception:
                    pass
            to_compute_idxs.append(i)
            to_compute_texts.append(texts[i])

        if to_compute_texts:
            computed = generate_embeddings(to_compute_texts)
            for list_pos, article_idx in enumerate(to_compute_idxs):
                vecs[article_idx] = computed[list_pos]

        return np.vstack(vecs)  # type: ignore[arg-type]

    def _within_window(self, a: Article, b: Article) -> bool:
        """Return True if both articles fall within the comparison window."""
        ta = a.publish_time or a.created_at
        tb = b.publish_time or b.created_at
        if ta is None or tb is None:
            return True  # be conservative: assume within window if no timestamps
        # Ensure timezone-aware
        if ta.tzinfo is None:
            ta = ta.replace(tzinfo=timezone.utc)
        if tb.tzinfo is None:
            tb = tb.replace(tzinfo=timezone.utc)
        return abs((ta - tb).total_seconds()) <= self.window_hours * 3600
