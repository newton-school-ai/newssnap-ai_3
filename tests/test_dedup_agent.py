"""Tests for the DeduplicationAgent.

Uses the REAL SentenceTransformer(all-MiniLM-L6-v2) model and real SQLAlchemy
sessions connected to the test database – no mocking.

Runs against:
    docker compose run --rm -e DATABASE_URL=postgresql://newssnap:newssnap@db:5432/newssnap \\
        backend pytest tests/test_dedup_agent.py -v
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.agents.dedup_agent import (
    SIMILARITY_THRESHOLD,
    DeduplicationAgent,
    _article_text,
    _embedding_from_json,
    generate_embeddings,
)
from src.models.article import Article
from src.models.source import Source

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://newssnap:newssnap@localhost:5432/newssnap",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def tables(engine):
    """Ensure schema exists (migration 001 + 002 should already have run)."""
    # We don't recreate tables here – they come from the alembic migrations.
    yield


@pytest.fixture()
def db(engine, tables):
    """Provide a session that's rolled back after each test for isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def _make_source(db: Session, name: str = "Test Source", priority: int = 1) -> Source:
    src = Source(
        id=uuid.uuid4(),
        name=name,
        url=f"https://{name.lower().replace(' ', '-')}.example.com",
        scrape_type="rss",
        language="en",
        category_slug="national",
        priority=priority,
    )
    db.add(src)
    db.flush()
    return src


def _make_article(
    db: Session,
    title: str,
    content: str = "",
    source: Source | None = None,
    publish_time: datetime | None = None,
    embedding: np.ndarray | None = None,
) -> Article:
    art = Article(
        id=uuid.uuid4(),
        url=f"https://example.com/{uuid.uuid4()}",
        title=title,
        content=content,
        language="en",
        category_slug="national",
        publish_time=publish_time or datetime.now(timezone.utc),
        source_id=source.id if source else None,
        embedding_vector=json.dumps(embedding.tolist()) if embedding is not None else None,
    )
    db.add(art)
    db.flush()
    return art


# ---------------------------------------------------------------------------
# Unit-level tests (no DB writes, just embedding logic)
# ---------------------------------------------------------------------------


class TestEmbeddingGeneration:
    def test_generate_embeddings_returns_correct_shape(self):
        texts = ["India wins cricket match", "Scientists discover new planet"]
        vecs = generate_embeddings(texts)
        assert vecs.shape == (2, 384)

    def test_embeddings_are_normalised(self):
        texts = ["This is a test sentence for normalisation."]
        vecs = generate_embeddings(texts)
        norm = float(np.linalg.norm(vecs[0]))
        assert abs(norm - 1.0) < 1e-4, f"Expected unit norm, got {norm}"

    def test_paraphrased_sentences_high_similarity(self):
        """Near-duplicate news headlines (wire-service rewrites) must score > SIMILARITY_THRESHOLD."""
        # These mimic how different outlets reprint the same PTI wire story with minor word swaps
        a = "India GDP grew 8 percent in the second quarter of fiscal year 2025"
        b = "India GDP grew 8% in second quarter of FY 2025"
        vecs = generate_embeddings([a, b])
        sim = float(np.dot(vecs[0], vecs[1]))
        assert sim >= SIMILARITY_THRESHOLD, (
            f"Expected similarity >= {SIMILARITY_THRESHOLD}, got {sim:.4f}"
        )

    def test_unrelated_sentences_low_similarity(self):
        """Completely different topics must score well below the threshold."""
        a = "The government announced new education reforms in rural schools."
        b = "Real Madrid won the UEFA Champions League final in Wembley."
        vecs = generate_embeddings([a, b])
        sim = float(np.dot(vecs[0], vecs[1]))
        assert sim < SIMILARITY_THRESHOLD, (
            f"Expected similarity < {SIMILARITY_THRESHOLD}, got {sim:.4f}"
        )

    def test_article_text_helper_uses_title_and_content(self):
        art = Article(title="Breaking News", content="Full article body here.")
        text = _article_text(art)
        assert "Breaking News" in text
        assert "Full article body here." in text

    def test_batch_100_articles_under_5_seconds(self):
        """Embedding generation for 100 articles must complete in < 5 seconds."""
        texts = [
            f"News headline number {i}: something important happened in the world today."
            for i in range(100)
        ]
        t0 = time.monotonic()
        vecs = generate_embeddings(texts)
        elapsed = time.monotonic() - t0
        assert vecs.shape[0] == 100
        assert elapsed < 5.0, f"Expected < 5s for 100 articles, got {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# DeduplicationAgent integration tests (using real DB session)
# ---------------------------------------------------------------------------


class TestDeduplicationAgentBatch:
    def test_unique_articles_pass_through(self, db: Session):
        """Articles about totally different topics should NOT be linked."""
        agent = DeduplicationAgent()

        art1 = _make_article(db, "India launches new space mission to explore lunar poles")
        art2 = _make_article(db, "IPL 2025 final: Chennai Super Kings defeat Mumbai Indians")
        art3 = _make_article(db, "Budget 2025: Finance minister presents record infrastructure spend")

        result = agent.deduplicate_batch([art1, art2, art3], db)

        assert art1.parent_id is None
        assert art2.parent_id is None
        assert art3.parent_id is None
        assert result.duplicates_found == 0
        assert result.total == 3

    def test_paraphrased_duplicate_is_detected(self, db: Session):
        """Two near-duplicate articles (wire-service style rewrites) from different sources must be clustered."""
        src1 = _make_source(db, "High Priority Source", priority=1)
        src2 = _make_source(db, "Low Priority Source", priority=2)
        agent = DeduplicationAgent()

        # Near-identical headlines — same sentence, minor word swaps only
        title1 = "India GDP grew 8 percent in the second quarter of fiscal year 2025"
        title2 = "India GDP grew 8% in second quarter of FY 2025"

        art1 = _make_article(db, title1, source=src1)
        art2 = _make_article(db, title2, source=src2)

        result = agent.deduplicate_batch([art1, art2], db)

        assert result.duplicates_found == 1, f"Expected 1 duplicate, got {result.duplicates_found}"
        # One should be marked as a child of the other
        assert (art1.parent_id is not None) or (art2.parent_id is not None)

    def test_primary_article_from_highest_priority_source(self, db: Session):
        """The canonical article must come from the source with the lowest priority number."""
        src_low_num = _make_source(db, "Priority 1 Source", priority=1)   # BETTER source
        src_high_num = _make_source(db, "Priority 2 Source", priority=2)  # WORSE source
        agent = DeduplicationAgent()

        # Near-identical headlines — same sentence, minor word swap only
        title1 = "PM Modi inaugurates Dwarka Expressway in Delhi on Wednesday"
        title2 = "PM Modi opens Dwarka Expressway in Delhi on Wednesday"

        # Add art from worse source first so we test ordering independence
        art_worse = _make_article(db, title2, source=src_high_num)
        art_better = _make_article(db, title1, source=src_low_num)

        agent.deduplicate_batch([art_worse, art_better], db)

        # The article from priority=1 source must be the parent (no parent_id set)
        assert art_better.parent_id is None, "Priority-1 source article should be the parent"
        assert art_worse.parent_id == art_better.id, (
            "Priority-2 source article should point to the priority-1 article"
        )

    def test_identical_articles_detected(self, db: Session):
        """Exact same text must be detected as a duplicate."""
        agent = DeduplicationAgent()
        title = "Breaking: Earthquake of magnitude 6.2 strikes Gujarat"
        art1 = _make_article(db, title, content="Full details pending.")
        art2 = _make_article(db, title, content="Full details pending.")

        result = agent.deduplicate_batch([art1, art2], db)
        assert result.duplicates_found >= 1

    def test_batch_100_articles_under_5_seconds(self, db: Session):
        """End-to-end dedup of 100 articles must complete in < 5 seconds."""
        agent = DeduplicationAgent()
        articles = [
            _make_article(
                db,
                f"Unique story headline number {i} about a completely different event",
                content=f"Body content for article {i} with distinct information.",
            )
            for i in range(100)
        ]

        t0 = time.monotonic()
        result = agent.deduplicate_batch(articles, db)
        elapsed = time.monotonic() - t0

        assert result.total == 100
        assert elapsed < 5.0, f"Expected < 5s for 100 articles, got {elapsed:.2f}s"


class TestComparisonWindow:
    def test_articles_outside_window_not_compared(self, db: Session):
        """Articles published more than window_hours apart must NOT be linked."""
        agent = DeduplicationAgent(window_hours=48)

        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=72)  # 72 hours ago, outside 48h window

        title1 = "India's GDP grows by 8% in the second quarter of fiscal year"
        title2 = "Indian economy expands 8 percent in Q2, beating analyst estimates"

        art_old = _make_article(db, title1, publish_time=old_time)
        art_new = _make_article(db, title2, publish_time=now)

        result = agent.deduplicate_batch([art_old, art_new], db)

        # Should NOT be marked as duplicates because they're outside the window
        assert art_old.parent_id is None
        assert art_new.parent_id is None
        assert result.duplicates_found == 0

    def test_articles_inside_window_are_compared(self, db: Session):
        """Near-duplicate articles within the window must be linked."""
        agent = DeduplicationAgent(window_hours=48)

        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=24)  # 24 hours ago, inside 48h window

        # Near-identical headlines (same sentence, minor word swaps)
        title1 = "India GDP grew 8 percent in the second quarter of fiscal year 2025"
        title2 = "India GDP grew 8% in second quarter of FY 2025"

        art_old = _make_article(db, title1, publish_time=recent)
        art_new = _make_article(db, title2, publish_time=now)

        result = agent.deduplicate_batch([art_old, art_new], db)

        assert result.duplicates_found >= 1

    def test_custom_window_hours_respected(self, db: Session):
        """A custom 6-hour window should reject articles 12 hours apart."""
        agent = DeduplicationAgent(window_hours=6)

        now = datetime.now(timezone.utc)
        twelve_hours_ago = now - timedelta(hours=12)

        # Near-identical headlines — same pair used in other window tests
        title1 = "India GDP grew 8 percent in the second quarter of fiscal year 2025"
        title2 = "India GDP grew 8% in second quarter of FY 2025"

        art_old = _make_article(db, title1, publish_time=twelve_hours_ago)
        art_new = _make_article(db, title2, publish_time=now)

        result = agent.deduplicate_batch([art_old, art_new], db)

        assert result.duplicates_found == 0, (
            "Articles 12 hours apart should not be compared with a 6-hour window"
        )


class TestEmbeddingPersistence:
    def test_embeddings_stored_on_articles(self, db: Session):
        """After dedup, embedding_vector must be populated on all articles."""
        agent = DeduplicationAgent()
        art = _make_article(db, "New policy announced for Indian railways expansion")

        assert art.embedding_vector is None  # should be empty initially

        agent.deduplicate_batch([art], db)

        assert art.embedding_vector is not None
        vec = _embedding_from_json(art.embedding_vector)
        assert vec.shape == (384,)

    def test_stored_embeddings_reused(self, db: Session):
        """Pre-stored embeddings must not trigger a model re-compute (fast path)."""
        agent = DeduplicationAgent()
        # Pre-compute and store an embedding
        text = "Budget 2025: FM presents major tax relief for middle class"
        vec = generate_embeddings([text])[0]
        art = _make_article(db, text, embedding=vec)

        t0 = time.monotonic()
        agent.deduplicate_batch([art], db)
        elapsed = time.monotonic() - t0

        # Reusing stored embeddings should be very fast (no model call overhead)
        assert elapsed < 1.0, f"Reusing stored embedding took too long: {elapsed:.2f}s"
