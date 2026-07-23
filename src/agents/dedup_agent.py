from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_WINDOW_HOURS = 48
MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class ArticleRecord:
    article_id: str
    title: str
    content: str
    source_priority: int = 1
    embedding: list[float] = field(default_factory=list)


@dataclass
class DedupGroup:
    primary_id: str
    duplicate_ids: list[str]


@dataclass
class DeduplicationResult:
    processed: int
    unique_count: int
    duplicate_groups: list[DedupGroup]

    @property
    def duplicate_count(self) -> int:
        return sum(len(g.duplicate_ids) for g in self.duplicate_groups)


class DedupAgent:
    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        window_hours: int = DEFAULT_WINDOW_HOURS,
        model_name: str = MODEL_NAME,
    ):
        self.threshold = similarity_threshold
        self.window_hours = window_hours
        self._model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def generate_embedding(self, text: str) -> list[float]:
        vec = self.model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, batch_size=32)
        return vecs.tolist()

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(va, vb) / (norm_a * norm_b))

    def is_duplicate(self, a: list[float], b: list[float]) -> bool:
        return self.cosine_similarity(a, b) >= self.threshold

    def deduplicate(self, articles: list[ArticleRecord]) -> DeduplicationResult:
        if not articles:
            return DeduplicationResult(processed=0, unique_count=0, duplicate_groups=[])

        needs_embedding = [a for a in articles if not a.embedding]
        if needs_embedding:
            texts = [f"{a.title}. {a.content}" for a in needs_embedding]
            embeddings = self.generate_embeddings_batch(texts)
            for article, emb in zip(needs_embedding, embeddings):
                article.embedding = emb

        n = len(articles)
        matrix = np.array([a.embedding for a in articles], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        normalized = matrix / norms
        sim_matrix = normalized @ normalized.T

        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        pairs = np.argwhere(np.triu(sim_matrix, k=1) >= self.threshold)
        for i, j in pairs:
            union(int(i), int(j))

        clusters: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)

        groups: list[DedupGroup] = []
        for members in clusters.values():
            if len(members) < 2:
                continue
            primary_idx = max(members, key=lambda idx: articles[idx].source_priority)
            duplicate_ids = [articles[k].article_id for k in members if k != primary_idx]
            groups.append(DedupGroup(
                primary_id=articles[primary_idx].article_id,
                duplicate_ids=duplicate_ids,
            ))

        unique_count = n - sum(len(g.duplicate_ids) for g in groups)
        return DeduplicationResult(
            processed=n,
            unique_count=unique_count,
            duplicate_groups=groups,
        )

    def run(self, db: Session, registry=None) -> DeduplicationResult:
        from sqlalchemy import or_, select

        from src.models.article import Article

        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.window_hours)
        rows = db.scalars(
            select(Article)
            .where(
                or_(
                    Article.publish_time >= cutoff,
                    (Article.publish_time.is_(None) & (Article.created_at >= cutoff)),
                )
            )
            .where(Article.duplicate_of_id.is_(None))
            .order_by(Article.publish_time.desc().nulls_last())
        ).all()

        source_priority: dict[str, int] = {}
        if registry is not None:
            for cfg in registry.get_all_sources():
                source_priority[cfg.name.lower()] = cfg.priority

        records: list[ArticleRecord] = []
        for row in rows:
            priority = 1
            if row.source is not None:
                priority = source_priority.get(row.source.name.lower(), 1)

            stored_embedding: list[float] = []
            if row.embedding_vector:
                try:
                    stored_embedding = json.loads(row.embedding_vector)
                except Exception:
                    pass

            records.append(ArticleRecord(
                article_id=str(row.id),
                title=row.title or "",
                content=row.content or "",
                source_priority=priority,
                embedding=stored_embedding,
            ))

        result = self.deduplicate(records)

        id_to_record = {r.article_id: r for r in records}
        id_to_row = {str(r.id): r for r in rows}

        for row in rows:
            rid = str(row.id)
            record = id_to_record.get(rid)
            if record and record.embedding and not row.embedding_vector:
                row.embedding_vector = json.dumps(record.embedding)

        for group in result.duplicate_groups:
            for dup_id in group.duplicate_ids:
                row = id_to_row.get(dup_id)
                if row is not None:
                    row.duplicate_of_id = group.primary_id

        db.commit()
        logger.info(
            "Dedup run complete: %d processed, %d unique, %d duplicate groups",
            result.processed,
            result.unique_count,
            len(result.duplicate_groups),
        )
        return result
