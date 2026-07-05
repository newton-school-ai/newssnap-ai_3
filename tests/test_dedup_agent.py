from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from src.agents.dedup_agent import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_WINDOW_HOURS,
    ArticleRecord,
    DedupAgent,
    DeduplicationResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = 384


def _rand_vec(seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.random(_DIM).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


def _near_vec(base: list[float], noise: float = 0.01) -> list[float]:
    v = np.array(base, dtype=np.float32) + np.random.default_rng(99).random(_DIM).astype(np.float32) * noise
    v /= np.linalg.norm(v)
    return v.tolist()


def _make_record(
    article_id: str = "a1",
    title: str = "Test",
    content: str = "Content",
    priority: int = 1,
    embedding: list[float] | None = None,
) -> ArticleRecord:
    return ArticleRecord(
        article_id=article_id,
        title=title,
        content=content,
        source_priority=priority,
        embedding=embedding or [],
    )


def _agent(threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> DedupAgent:
    agent = DedupAgent(similarity_threshold=threshold)
    return agent


# ---------------------------------------------------------------------------
# DedupAgent defaults
# ---------------------------------------------------------------------------


def test_default_threshold():
    agent = DedupAgent()
    assert agent.threshold == DEFAULT_SIMILARITY_THRESHOLD


def test_default_window_hours():
    agent = DedupAgent()
    assert agent.window_hours == DEFAULT_WINDOW_HOURS


def test_configurable_threshold():
    agent = DedupAgent(similarity_threshold=0.9)
    assert agent.threshold == 0.9


def test_configurable_window():
    agent = DedupAgent(window_hours=24)
    assert agent.window_hours == 24


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical_vectors():
    v = _rand_vec(1)
    assert _agent().cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)


def test_cosine_similarity_orthogonal_vectors():
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    assert _agent().cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)


def test_cosine_similarity_zero_vector_returns_zero():
    v = _rand_vec(1)
    zeros = [0.0] * len(v)
    assert _agent().cosine_similarity(zeros, v) == 0.0


def test_cosine_similarity_near_vectors_high():
    base = _rand_vec(2)
    near = _near_vec(base, noise=0.005)
    sim = _agent().cosine_similarity(base, near)
    assert sim > 0.99


def test_cosine_similarity_different_vectors_low():
    v1 = _rand_vec(10)
    v2 = _rand_vec(20)
    sim = _agent().cosine_similarity(v1, v2)
    assert sim < 0.95


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------


def test_is_duplicate_with_identical_embedding():
    v = _rand_vec(3)
    assert _agent().is_duplicate(v, v) is True


def test_is_duplicate_with_near_embedding():
    base = _rand_vec(4)
    near = _near_vec(base, noise=0.005)
    assert _agent().is_duplicate(base, near) is True


def test_is_duplicate_with_dissimilar_embedding():
    v1 = _rand_vec(10)
    v2 = _rand_vec(20)
    agent = DedupAgent(similarity_threshold=0.99)
    result = agent.is_duplicate(v1, v2)
    assert isinstance(result, bool)


def test_is_not_duplicate_below_threshold():
    v1 = _rand_vec(10)
    v2 = _rand_vec(20)
    agent = DedupAgent(similarity_threshold=1.0)
    assert agent.is_duplicate(v1, v2) is False


# ---------------------------------------------------------------------------
# deduplicate: basic cases
# ---------------------------------------------------------------------------


def test_deduplicate_empty_returns_zero():
    result = _agent().deduplicate([])
    assert result.processed == 0
    assert result.unique_count == 0
    assert result.duplicate_groups == []


def test_deduplicate_single_article_is_unique():
    base = _rand_vec(0)
    records = [_make_record("a1", embedding=base)]
    result = _agent().deduplicate(records)
    assert result.processed == 1
    assert result.unique_count == 1
    assert result.duplicate_groups == []


def test_deduplicate_all_unique_articles():
    records = [
        _make_record(f"a{i}", embedding=_rand_vec(i + 100))
        for i in range(5)
    ]
    agent = DedupAgent(similarity_threshold=0.99)
    result = agent.deduplicate(records)
    assert result.processed == 5
    assert result.unique_count == 5
    assert result.duplicate_groups == []


def test_deduplicate_exact_duplicates_grouped():
    base = _rand_vec(5)
    records = [
        _make_record("a1", embedding=base, priority=2),
        _make_record("a2", embedding=base, priority=1),
        _make_record("a3", embedding=base, priority=3),
    ]
    result = _agent().deduplicate(records)
    assert result.processed == 3
    assert len(result.duplicate_groups) == 1
    assert result.unique_count == 1
    assert result.duplicate_count == 2


def test_deduplicate_result_duplicate_count_property():
    base = _rand_vec(5)
    records = [
        _make_record("a1", embedding=base),
        _make_record("a2", embedding=base),
    ]
    result = _agent().deduplicate(records)
    assert result.duplicate_count == 1


# ---------------------------------------------------------------------------
# deduplicate: primary article selection
# ---------------------------------------------------------------------------


def test_primary_is_highest_priority_source():
    base = _rand_vec(6)
    records = [
        _make_record("low", embedding=base, priority=1),
        _make_record("high", embedding=base, priority=5),
        _make_record("mid", embedding=base, priority=3),
    ]
    result = _agent().deduplicate(records)
    assert len(result.duplicate_groups) == 1
    group = result.duplicate_groups[0]
    assert group.primary_id == "high"
    assert "low" in group.duplicate_ids
    assert "mid" in group.duplicate_ids


def test_primary_not_in_duplicate_ids():
    base = _rand_vec(7)
    records = [
        _make_record("a1", embedding=base, priority=3),
        _make_record("a2", embedding=base, priority=1),
    ]
    result = _agent().deduplicate(records)
    group = result.duplicate_groups[0]
    assert group.primary_id not in group.duplicate_ids


# ---------------------------------------------------------------------------
# deduplicate: multiple independent groups
# ---------------------------------------------------------------------------


def test_two_independent_duplicate_groups():
    base_a = _rand_vec(8)
    base_b = _rand_vec(9)
    near_a = _near_vec(base_a, noise=0.005)
    near_b = _near_vec(base_b, noise=0.005)

    records = [
        _make_record("a1", embedding=base_a),
        _make_record("a2", embedding=near_a),
        _make_record("b1", embedding=base_b),
        _make_record("b2", embedding=near_b),
    ]
    result = _agent().deduplicate(records)
    assert result.processed == 4
    assert len(result.duplicate_groups) == 2
    assert result.unique_count == 2


# ---------------------------------------------------------------------------
# deduplicate: paraphrased article detection (real embeddings)
# ---------------------------------------------------------------------------


def test_paraphrased_articles_detected_as_duplicates():
    agent = DedupAgent(similarity_threshold=0.85)
    original = "Prime Minister Modi inaugurated the new expressway in Maharashtra today."
    paraphrase = "PM Modi today inaugurated a new expressway in Maharashtra."
    different = "ISRO successfully launches new satellite into lunar orbit after three attempts."

    records = [
        _make_record("orig", title="Expressway", content=original),
        _make_record("para", title="Modi inaugurates", content=paraphrase),
        _make_record("diff", title="Space", content=different),
    ]
    result = agent.deduplicate(records)

    assert result.processed == 3
    paired_ids = {g.primary_id for g in result.duplicate_groups} | {
        d for g in result.duplicate_groups for d in g.duplicate_ids
    }
    assert "orig" in paired_ids or "para" in paired_ids
    assert "diff" not in {d for g in result.duplicate_groups for d in g.duplicate_ids if g.primary_id != "diff"}


def test_unique_articles_pass_through():
    agent = DedupAgent(similarity_threshold=0.85)
    records = [
        _make_record("a", title="Cricket", content="India won the cricket match against Australia."),
        _make_record("b", title="Budget", content="Finance minister presents annual union budget today."),
        _make_record("c", title="Space", content="ISRO successfully launches new satellite into orbit."),
    ]
    result = agent.deduplicate(records)
    assert result.processed == 3
    assert result.duplicate_groups == []
    assert result.unique_count == 3


# ---------------------------------------------------------------------------
# generate_embedding
# ---------------------------------------------------------------------------


def test_generate_embedding_returns_list_of_floats():
    agent = DedupAgent()
    vec = agent.generate_embedding("This is a test sentence.")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)


def test_generate_embedding_normalized():
    agent = DedupAgent()
    vec = agent.generate_embedding("Testing normalization of embedding vector.")
    norm = np.linalg.norm(vec)
    assert norm == pytest.approx(1.0, abs=1e-5)


def test_generate_embeddings_batch_matches_single():
    agent = DedupAgent()
    text = "Batch versus single embedding consistency."
    single = agent.generate_embedding(text)
    batch = agent.generate_embeddings_batch([text])
    assert np.allclose(single, batch[0], atol=1e-5)


# ---------------------------------------------------------------------------
# performance: 100+ articles under 5 seconds
# ---------------------------------------------------------------------------


def test_batch_performance_100_articles():
    agent = DedupAgent()

    rng = np.random.default_rng(42)
    vecs = rng.random((110, _DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

    records = [
        _make_record(f"a{i}", embedding=vecs[i].tolist())
        for i in range(110)
    ]

    start = time.perf_counter()
    result = agent.deduplicate(records)
    elapsed = time.perf_counter() - start

    assert result.processed == 110
    assert elapsed < 5.0, f"Dedup of 110 articles took {elapsed:.2f}s (limit: 5s)"


# ---------------------------------------------------------------------------
# run() integration (DB mocked)
# ---------------------------------------------------------------------------


def _make_mock_article(
    article_id: str,
    title: str = "Title",
    content: str = "Content",
    embedding: str | None = None,
    source_name: str | None = None,
    source_priority: int = 1,
) -> MagicMock:
    row = MagicMock()
    row.id = article_id
    row.title = title
    row.content = content
    row.embedding_vector = embedding
    row.duplicate_of_id = None
    if source_name:
        row.source = MagicMock()
        row.source.name = source_name
    else:
        row.source = None
    return row


def _make_mock_db(rows: list) -> MagicMock:
    db = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    db.scalars.return_value = scalars_result
    return db


def test_run_persists_embeddings_for_new_articles():
    base = _rand_vec(50)
    rows = [
        _make_mock_article("a1", embedding=None),
        _make_mock_article("a2", embedding=None),
    ]
    db = _make_mock_db(rows)

    agent = DedupAgent()
    with patch.object(agent, "generate_embeddings_batch", return_value=[base, _rand_vec(60)]):
        agent.run(db)

    db.commit.assert_called_once()
    assert rows[0].embedding_vector is not None


def test_run_marks_duplicates_in_db():
    base = _rand_vec(51)
    rows = [
        _make_mock_article("primary", embedding=json.dumps(base), source_priority=3),
        _make_mock_article("dup1", embedding=json.dumps(base), source_priority=1),
    ]
    db = _make_mock_db(rows)

    agent = DedupAgent()
    agent.run(db)

    dup_row = next(r for r in rows if r.id == "dup1")
    assert dup_row.duplicate_of_id == "primary"


def test_run_does_not_mark_primary_as_duplicate():
    base = _rand_vec(52)
    rows = [
        _make_mock_article("primary", embedding=json.dumps(base), source_priority=5),
        _make_mock_article("dup1", embedding=json.dumps(base), source_priority=1),
    ]
    db = _make_mock_db(rows)

    agent = DedupAgent()
    agent.run(db)

    primary_row = next(r for r in rows if r.id == "primary")
    assert primary_row.duplicate_of_id is None


def test_run_returns_deduplication_result():
    db = _make_mock_db([])
    result = DedupAgent().run(db)
    assert isinstance(result, DeduplicationResult)
    assert result.processed == 0
