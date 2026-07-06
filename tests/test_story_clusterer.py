from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
from src.agents.story_clusterer import (
    DEFAULT_EPS,
    DEFAULT_EXISTING_THRESHOLD,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_WINDOW_HOURS,
    ArticleInput,
    ClusteringResult,
    StoryCluster,
    StoryClusterer,
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


def _make_article(
    article_id: str = "a1",
    title: str = "Title",
    content: str = "Content",
    quality_score: float = 0.5,
    publish_time: datetime | None = None,
    embedding: list[float] | None = None,
    category_slug: str = "national",
    language: str = "en",
    image_url: str | None = None,
) -> ArticleInput:
    return ArticleInput(
        article_id=article_id,
        title=title,
        content=content,
        category_slug=category_slug,
        language=language,
        publish_time=publish_time or datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        image_url=image_url,
        quality_score=quality_score,
        embedding=embedding or [],
    )


def _clusterer(**kwargs) -> StoryClusterer:
    return StoryClusterer(**kwargs)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_eps():
    assert StoryClusterer().eps == DEFAULT_EPS


def test_default_min_samples():
    assert StoryClusterer().min_samples == DEFAULT_MIN_SAMPLES


def test_default_window_hours():
    assert StoryClusterer().window_hours == DEFAULT_WINDOW_HOURS


def test_default_existing_threshold():
    assert StoryClusterer().existing_story_threshold == DEFAULT_EXISTING_THRESHOLD


def test_configurable_eps():
    assert StoryClusterer(eps=0.2).eps == 0.2


def test_configurable_min_samples():
    assert StoryClusterer(min_samples=3).min_samples == 3


# ---------------------------------------------------------------------------
# cluster(): basic cases
# ---------------------------------------------------------------------------


def test_cluster_empty_returns_empty():
    result = _clusterer().cluster([])
    assert result == []


def test_cluster_single_article_is_noise():
    articles = [_make_article("a1", embedding=_rand_vec(0))]
    result = _clusterer().cluster(articles)
    assert result == []


def test_cluster_two_dissimilar_articles_are_noise():
    articles = [
        _make_article("a1", embedding=_rand_vec(10)),
        _make_article("a2", embedding=_rand_vec(20)),
    ]
    clusterer = StoryClusterer(eps=0.01)
    result = clusterer.cluster(articles)
    assert result == []


def test_cluster_two_similar_articles_grouped():
    base = _rand_vec(5)
    articles = [
        _make_article("a1", embedding=base),
        _make_article("a2", embedding=_near_vec(base, noise=0.005)),
    ]
    result = _clusterer().cluster(articles)
    assert len(result) == 1
    cluster = result[0]
    assert set([cluster.primary_article_id] + cluster.related_article_ids) == {"a1", "a2"}


def test_cluster_returns_story_cluster_type():
    base = _rand_vec(6)
    articles = [
        _make_article("a1", embedding=base),
        _make_article("a2", embedding=_near_vec(base, noise=0.005)),
    ]
    result = _clusterer().cluster(articles)
    assert isinstance(result[0], StoryCluster)
    assert isinstance(result[0].related_article_ids, list)


# ---------------------------------------------------------------------------
# cluster(): primary article selection
# ---------------------------------------------------------------------------


def test_cluster_primary_is_highest_quality_score():
    base = _rand_vec(7)
    articles = [
        _make_article("low", embedding=base, quality_score=0.3),
        _make_article("high", embedding=_near_vec(base, noise=0.005), quality_score=0.9),
        _make_article("mid", embedding=_near_vec(base, noise=0.003), quality_score=0.6),
    ]
    result = _clusterer().cluster(articles)
    assert len(result) == 1
    assert result[0].primary_article_id == "high"
    assert "low" in result[0].related_article_ids
    assert "mid" in result[0].related_article_ids


def test_cluster_primary_is_earliest_on_equal_quality():
    base = _rand_vec(8)
    early = datetime(2026, 7, 6, 8, 0, tzinfo=timezone.utc)
    late = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    articles = [
        _make_article("later", embedding=base, quality_score=0.5, publish_time=late),
        _make_article("earlier", embedding=_near_vec(base, noise=0.005), quality_score=0.5, publish_time=early),
    ]
    result = _clusterer().cluster(articles)
    assert len(result) == 1
    assert result[0].primary_article_id == "earlier"


def test_cluster_primary_not_in_related():
    base = _rand_vec(9)
    articles = [
        _make_article("a1", embedding=base, quality_score=0.8),
        _make_article("a2", embedding=_near_vec(base, noise=0.005), quality_score=0.3),
    ]
    result = _clusterer().cluster(articles)
    group = result[0]
    assert group.primary_article_id not in group.related_article_ids


# ---------------------------------------------------------------------------
# cluster(): multiple independent clusters
# ---------------------------------------------------------------------------


def test_cluster_two_independent_clusters():
    base_a = _rand_vec(10)
    base_b = _rand_vec(11)

    articles = [
        _make_article("a1", embedding=base_a),
        _make_article("a2", embedding=_near_vec(base_a, noise=0.005)),
        _make_article("b1", embedding=base_b),
        _make_article("b2", embedding=_near_vec(base_b, noise=0.005)),
    ]
    result = _clusterer().cluster(articles)
    assert len(result) == 2

    all_ids = {r.primary_article_id for r in result} | {d for r in result for d in r.related_article_ids}
    assert all_ids == {"a1", "a2", "b1", "b2"}


# ---------------------------------------------------------------------------
# assign_to_existing
# ---------------------------------------------------------------------------


def test_assign_to_existing_empty_centroids():
    clusterer = _clusterer()
    result = clusterer.assign_to_existing(_rand_vec(0), {})
    assert result is None


def test_assign_to_existing_empty_embedding():
    clusterer = _clusterer()
    centroids = {"story1": _rand_vec(1)}
    result = clusterer.assign_to_existing([], centroids)
    assert result is None


def test_assign_to_existing_matches_similar_centroid():
    base = _rand_vec(2)
    near = _near_vec(base, noise=0.005)
    clusterer = StoryClusterer(existing_story_threshold=0.5)
    result = clusterer.assign_to_existing(near, {"story1": base})
    assert result == "story1"


def test_assign_to_existing_no_match_below_threshold():
    v1 = _rand_vec(10)
    v2 = _rand_vec(20)
    clusterer = StoryClusterer(existing_story_threshold=0.99)
    result = clusterer.assign_to_existing(v1, {"story1": v2})
    assert result is None


def test_assign_to_existing_picks_best_match():
    base = _rand_vec(3)
    near = _near_vec(base, noise=0.005)
    far = _rand_vec(30)
    clusterer = StoryClusterer(existing_story_threshold=0.5)
    result = clusterer.assign_to_existing(near, {"s_near": base, "s_far": far})
    assert result == "s_near"


# ---------------------------------------------------------------------------
# Real embeddings
# ---------------------------------------------------------------------------


def test_same_event_articles_clustered():
    clusterer = StoryClusterer()
    articles = [
        _make_article(
            "a1",
            title="Modi inaugurates metro",
            content="PM Modi inaugurated the new metro line extension in Delhi today.",
        ),
        _make_article(
            "a2",
            title="Delhi metro inaugurated",
            content="Prime Minister Modi today inaugurated the metro rail extension in New Delhi.",
        ),
        _make_article(
            "a3",
            title="ISRO satellite launch",
            content="ISRO successfully launched a new communication satellite into orbit on Sunday.",
        ),
    ]
    result = clusterer.cluster(articles)

    clustered_ids = {
        a_id
        for sc in result
        for a_id in [sc.primary_article_id] + sc.related_article_ids
    }
    assert "a1" in clustered_ids or "a2" in clustered_ids
    assert "a3" not in clustered_ids


def test_different_events_not_clustered():
    clusterer = StoryClusterer()
    articles = [
        _make_article("a", title="Cricket", content="India won the cricket World Cup final against Australia."),
        _make_article("b", title="Budget", content="Finance minister presents the union budget in parliament."),
        _make_article("c", title="Space", content="ISRO launches new lunar probe in historic mission."),
    ]
    result = clusterer.cluster(articles)
    assert result == []


# ---------------------------------------------------------------------------
# Performance: 500 articles in < 10 seconds
# ---------------------------------------------------------------------------


def test_performance_500_articles_under_10_seconds():
    clusterer = StoryClusterer()

    rng = np.random.default_rng(42)
    vecs = rng.random((500, _DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

    articles = [
        _make_article(f"a{i}", embedding=vecs[i].tolist())
        for i in range(500)
    ]

    start = time.perf_counter()
    result = clusterer.cluster(articles)
    elapsed = time.perf_counter() - start

    assert isinstance(result, list)
    assert elapsed < 10.0, f"Clustering 500 articles took {elapsed:.2f}s (limit: 10s)"


# ---------------------------------------------------------------------------
# run() integration (DB mocked)
# ---------------------------------------------------------------------------


def _make_mock_article_row(
    article_id: str,
    title: str = "Title",
    content: str = "Content",
    category_slug: str = "national",
    language: str = "en",
    quality_score: float = 0.5,
    embedding: str | None = None,
    image_url: str | None = None,
    publish_time: datetime | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = article_id
    row.title = title
    row.content = content
    row.category_slug = category_slug
    row.language = language
    row.quality_score = quality_score
    row.embedding_vector = embedding
    row.image_url = image_url
    row.story_id = None
    row.duplicate_of_id = None
    row.publish_time = publish_time or datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    return row


def _make_mock_db(article_rows: list, story_rows: list | None = None) -> MagicMock:
    db = MagicMock()

    article_result = MagicMock()
    article_result.all.return_value = article_rows

    story_result = MagicMock()
    story_result.all.return_value = story_rows or []

    db.scalars.side_effect = [article_result, story_result]
    return db


def test_run_empty_articles_returns_zero():
    db = _make_mock_db([])
    result = StoryClusterer().run(db)
    assert isinstance(result, ClusteringResult)
    assert result.stories_created == 0
    assert result.articles_assigned == 0
    assert result.noise_count == 0


def test_run_creates_story_for_cluster():
    base = _rand_vec(50)
    near = _near_vec(base, noise=0.005)
    rows = [
        _make_mock_article_row("a1", embedding=json.dumps(base), quality_score=0.9),
        _make_mock_article_row("a2", embedding=json.dumps(near), quality_score=0.5),
    ]
    db = _make_mock_db(rows)

    clusterer = StoryClusterer()
    result = clusterer.run(db)

    db.add.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_called_once()
    assert result.stories_created == 1
    assert result.articles_assigned == 2


def test_run_assigns_story_id_to_articles():
    base = _rand_vec(51)
    near = _near_vec(base, noise=0.005)
    rows = [
        _make_mock_article_row("a1", embedding=json.dumps(base)),
        _make_mock_article_row("a2", embedding=json.dumps(near)),
    ]
    db = _make_mock_db(rows)

    StoryClusterer().run(db)

    assert rows[0].story_id is not None or rows[1].story_id is not None


def test_run_noise_article_assigned_to_existing_story():
    noise = _rand_vec(52)

    noise_row = _make_mock_article_row("noise", embedding=json.dumps(noise))
    rows = [noise_row]

    db = _make_mock_db(rows)

    mock_story = MagicMock()
    mock_story.id = "existing-story-id"
    mock_story.last_updated_at = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    art_with_emb = MagicMock()
    art_with_emb.embedding_vector = json.dumps(noise)
    mock_story.articles = [art_with_emb]

    db.scalars.side_effect = None
    article_result = MagicMock()
    article_result.all.return_value = rows
    story_result = MagicMock()
    story_result.all.return_value = [mock_story]
    db.scalars.side_effect = [article_result, story_result]

    clusterer = StoryClusterer(existing_story_threshold=0.5)
    result = clusterer.run(db)

    assert noise_row.story_id == "existing-story-id"
    assert result.articles_assigned == 1


def test_run_persists_embeddings_for_new_articles():
    row = _make_mock_article_row("a1", embedding=None)
    db = _make_mock_db([row])

    clusterer = StoryClusterer()
    with patch.object(clusterer, "generate_embeddings_batch", return_value=[_rand_vec(99)]):
        clusterer.run(db)

    assert row.embedding_vector is not None


def test_run_returns_clustering_result_type():
    db = _make_mock_db([])
    result = StoryClusterer().run(db)
    assert isinstance(result, ClusteringResult)


def test_run_commits_db():
    isolated = _make_mock_article_row("iso2", embedding=json.dumps(_rand_vec(101)))
    db = _make_mock_db([isolated])
    StoryClusterer().run(db)
    db.commit.assert_called_once()


def test_run_noise_count_reflects_unassigned():
    isolated = _make_mock_article_row("iso", embedding=json.dumps(_rand_vec(100)))
    db = _make_mock_db([isolated])

    result = StoryClusterer().run(db)

    assert result.noise_count == 1
    assert result.stories_created == 0
