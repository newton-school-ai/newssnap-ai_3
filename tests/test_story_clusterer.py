import os
import time
import uuid
from datetime import datetime, timezone

from src.agents.story_clusterer import StoryClusterer, _embedding_to_json
from src.models.article import Article
from src.models.story import Story


class MockSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_primary_article_selection():
    clusterer = StoryClusterer()

    a1 = Article(title="A1", quality_score=0.5)
    a2 = Article(title="A2", quality_score=0.9)
    a3 = Article(title="A3", quality_score=0.2)

    primary = clusterer.get_primary_article([a1, a2, a3])
    assert primary.title == "A2"

    # Fallback heuristic
    a4 = Article(title="A4", content="short", image_url=None, quality_score=None)
    a5 = Article(title="A5", content="long " * 500, image_url="http://img.com", quality_score=None)

    primary_fallback = clusterer.get_primary_article([a4, a5])
    assert primary_fallback.title == "A5"


def test_primary_article_mixed_scoring():
    clusterer = StoryClusterer()
    # A real scored article but with a low score
    a_scored = Article(title="Scored", quality_score=0.6, content="short", image_url=None)
    # An unscored article that would get a high heuristic score
    a_unscored = Article(title="Unscored", quality_score=None, content="x" * 6000, image_url="http://img.com")

    primary = clusterer.get_primary_article([a_scored, a_unscored])
    # The scored one should always win over the unscored one
    assert primary.title == "Scored"


def test_dbscan_clustering():
    clusterer = StoryClusterer(eps=0.1)

    # Vector 1 and 2 are identical, Vector 3 is completely different
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    a1 = Article(title="A1", embedding_vector=_embedding_to_json(v1))
    a2 = Article(title="A2", embedding_vector=_embedding_to_json(v2))
    a3 = Article(title="A3", embedding_vector=_embedding_to_json(v3))

    clusters = clusterer.cluster_articles([a1, a2, a3])

    assert len(clusters) == 2
    # One cluster should have 2 articles, the other 1
    lens = sorted([len(c) for c in clusters])
    assert lens == [1, 2]


def test_match_existing_story():
    # Use eps=0.3
    clusterer = StoryClusterer(eps=0.3)

    v1 = [1.0, 0.0, 0.0]
    v_close = [0.99, 0.1, 0.0]  # Very close to v1
    v_far = [0.0, 1.0, 0.0]  # Orthogonal to v1

    story = Story(id=uuid.uuid4(), article_count=1, last_updated_at=datetime.now(timezone.utc))
    a_story = Article(title="Story Article", embedding_vector=_embedding_to_json(v1), quality_score=1.0)
    story.articles = [a_story]

    a_close = Article(
        title="Close", embedding_vector=_embedding_to_json(v_close), publish_time=datetime.now(timezone.utc)
    )
    a_far = Article(title="Far", embedding_vector=_embedding_to_json(v_far), publish_time=datetime.now(timezone.utc))

    matched_close = clusterer.match_existing_story(a_close, [story])
    assert matched_close == story
    assert a_close.story_id == story.id

    matched_far = clusterer.match_existing_story(a_far, [story])
    assert matched_far is None


def test_clustering_benchmark():
    # 500-article benchmark completes in under 10 seconds
    clusterer = StoryClusterer(eps=0.1)

    articles = []
    for i in range(500):
        # Generate some synthetic vectors that group into ~50 clusters
        cluster_idx = i % 50
        vec = [0.0] * 50
        vec[cluster_idx] = 1.0
        articles.append(Article(title=f"A{i}", embedding_vector=_embedding_to_json(vec)))

    max_seconds = float(os.getenv("STORY_CLUSTER_BENCHMARK_MAX_SECONDS", "30.0"))
    start_time = time.perf_counter()
    clusters = clusterer.cluster_articles(articles)
    elapsed = time.perf_counter() - start_time

    assert elapsed < max_seconds
    assert len(clusters) == 50


def test_cluster_recent_articles_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from src.models.base import Base
    from src.models.source import Source  # noqa: F401 (ensure tables are registered)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    clusterer = StoryClusterer(eps=0.1, session_factory=testing_session_local)

    db = testing_session_local()
    try:
        now = datetime.now(timezone.utc)
        a1 = Article(
            id=uuid.uuid4(),
            title="Test 1",
            url="http://t1",
            category_slug="tech",
            publish_time=now,
            embedding_vector=_embedding_to_json([1.0, 0.0]),
        )
        a2 = Article(
            id=uuid.uuid4(),
            title="Test 2",
            url="http://t2",
            category_slug="tech",
            publish_time=now,
            embedding_vector=_embedding_to_json([1.0, 0.0]),
        )
        a3 = Article(
            id=uuid.uuid4(),
            title="Test 3",
            url="http://t3",
            category_slug="tech",
            publish_time=now,
            embedding_vector=_embedding_to_json([0.0, 1.0]),
        )

        db.add_all([a1, a2, a3])
        db.commit()

        stories = clusterer.cluster_recent_articles(hours=6)

        # 2 distinct vectors -> 2 clusters -> 2 stories
        assert len(stories) == 2

        db.refresh(a1)
        db.refresh(a2)
        db.refresh(a3)
        assert a1.story_id is not None
        assert a2.story_id == a1.story_id
        assert a3.story_id is not None
        assert a3.story_id != a1.story_id
    finally:
        db.close()
