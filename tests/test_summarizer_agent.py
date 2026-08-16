from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from src.agents.summarizer_agent import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_WORDS,
    DEFAULT_MIN_WORDS,
    DEFAULT_STYLE_HINT,
    SummarizerAgent,
    SummaryResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_summary(word_count: int = 70) -> str:
    return " ".join(["word"] * word_count)


def _agent(**kwargs) -> SummarizerAgent:
    return SummarizerAgent(api_key="test-key", **kwargs)


# ---------------------------------------------------------------------------
# Defaults / configuration
# ---------------------------------------------------------------------------


def test_default_word_bounds():
    agent = _agent()
    assert agent.min_words == DEFAULT_MIN_WORDS
    assert agent.max_words == DEFAULT_MAX_WORDS


def test_default_max_retries():
    agent = _agent()
    assert agent.max_retries == DEFAULT_MAX_RETRIES


def test_configurable_word_bounds():
    agent = _agent(min_words=40, max_words=100)
    assert agent.min_words == 40
    assert agent.max_words == 100


def test_configurable_max_retries():
    agent = _agent(max_retries=5)
    assert agent.max_retries == 5


# ---------------------------------------------------------------------------
# style_hint / build_prompt
# ---------------------------------------------------------------------------


def test_style_hint_known_category():
    agent = _agent()
    hint = agent.style_hint("finance")
    assert "market" in hint.lower() or "number" in hint.lower()


def test_style_hint_unknown_category_falls_back():
    agent = _agent()
    assert agent.style_hint("some_unknown_category") == DEFAULT_STYLE_HINT


def test_style_hint_case_insensitive():
    agent = _agent()
    assert agent.style_hint("SPORTS") == agent.style_hint("sports")


def test_build_prompt_includes_title_content_and_category():
    agent = _agent()
    prompt = agent.build_prompt("Big News", "Something happened today.", "politics")
    assert "Big News" in prompt
    assert "Something happened today." in prompt
    assert "politics" in prompt
    assert str(agent.min_words) in prompt
    assert str(agent.max_words) in prompt


# ---------------------------------------------------------------------------
# count_words / is_clickbait
# ---------------------------------------------------------------------------


def test_count_words_basic():
    agent = _agent()
    assert agent.count_words("one two three") == 3


def test_count_words_empty():
    assert _agent().count_words("") == 0


@pytest.mark.parametrize(
    "text",
    [
        "You won't believe what happened next",
        "This is SHOCKING news for everyone",
        "Doctors hate this one weird trick",
        "This story is truly unbelievable",
    ],
)
def test_is_clickbait_detects_known_patterns(text):
    assert _agent().is_clickbait(text) is True


def test_is_clickbait_false_for_factual_text():
    agent = _agent()
    text = "The finance minister announced a new policy on infrastructure spending today."
    assert agent.is_clickbait(text) is False


# ---------------------------------------------------------------------------
# validate_summary
# ---------------------------------------------------------------------------


def test_validate_summary_within_bounds_is_valid():
    agent = _agent()
    valid, error = agent.validate_summary(_valid_summary(70))
    assert valid is True
    assert error is None


def test_validate_summary_too_short():
    agent = _agent()
    valid, error = agent.validate_summary(_valid_summary(10))
    assert valid is False
    assert "short" in error


def test_validate_summary_too_long():
    agent = _agent()
    valid, error = agent.validate_summary(_valid_summary(150))
    assert valid is False
    assert "long" in error


def test_validate_summary_empty():
    agent = _agent()
    valid, error = agent.validate_summary("")
    assert valid is False
    assert "empty" in error


def test_validate_summary_clickbait_rejected():
    agent = _agent()
    text = " ".join(["word"] * 68) + " this is shocking news"
    valid, error = agent.validate_summary(text)
    assert valid is False
    assert "clickbait" in error


def test_validate_summary_exact_min_boundary():
    agent = _agent()
    valid, _ = agent.validate_summary(_valid_summary(agent.min_words))
    assert valid is True


def test_validate_summary_exact_max_boundary():
    agent = _agent()
    valid, _ = agent.validate_summary(_valid_summary(agent.max_words))
    assert valid is True


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


def test_generate_summary_extracts_content_from_response():
    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content="  a generated summary  ")
    agent._client = mock_client

    result = agent.generate_summary("Title", "Content", "national")
    assert result == "a generated summary"
    mock_client.invoke.assert_called_once()


# ---------------------------------------------------------------------------
# summarize(): LangGraph retry state machine
# ---------------------------------------------------------------------------


def test_summarize_succeeds_on_first_attempt():
    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(70))
    agent._client = mock_client

    result = agent.summarize("story-1", "Title", "Content", "national")

    assert isinstance(result, SummaryResult)
    assert result.success is True
    assert result.attempts == 1
    assert result.summary == _valid_summary(70)
    assert result.error is None


def test_summarize_retries_then_succeeds():
    agent = _agent(max_retries=2)
    mock_client = MagicMock()
    mock_client.invoke.side_effect = [
        MagicMock(content=_valid_summary(10)),  # too short, attempt 1
        MagicMock(content=_valid_summary(70)),  # valid, attempt 2
    ]
    agent._client = mock_client

    result = agent.summarize("story-1", "Title", "Content", "national")

    assert result.success is True
    assert result.attempts == 2
    assert mock_client.invoke.call_count == 2


def test_summarize_exhausts_retries_and_fails():
    agent = _agent(max_retries=2)
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(5))  # always too short
    agent._client = mock_client

    result = agent.summarize("story-1", "Title", "Content", "national")

    assert result.success is False
    assert result.summary is None
    assert result.attempts == 3  # 1 initial + 2 retries
    assert mock_client.invoke.call_count == 3
    assert "short" in result.error


def test_summarize_max_retries_zero_only_tries_once():
    agent = _agent(max_retries=0)
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(5))
    agent._client = mock_client

    result = agent.summarize("story-1", "Title", "Content", "national")

    assert result.attempts == 1
    assert mock_client.invoke.call_count == 1
    assert result.success is False


# ---------------------------------------------------------------------------
# summarize_batch
# ---------------------------------------------------------------------------


def test_summarize_batch_empty_returns_empty():
    agent = _agent()
    assert agent.summarize_batch([]) == []


def test_summarize_batch_preserves_order_and_count():
    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(70))
    agent._client = mock_client

    items = [
        {"story_id": f"s{i}", "title": f"Title {i}", "content": f"Content {i}", "category": "national"}
        for i in range(5)
    ]
    results = agent.summarize_batch(items)

    assert len(results) == 5
    assert [r.story_id for r in results] == [f"s{i}" for i in range(5)]
    assert all(r.success for r in results)


def test_summarize_batch_20_articles_under_30_seconds():
    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(70))
    agent._client = mock_client

    items = [
        {"story_id": f"s{i}", "title": f"Title {i}", "content": f"Content {i}", "category": "national"}
        for i in range(20)
    ]

    start = time.perf_counter()
    results = agent.summarize_batch(items)
    elapsed = time.perf_counter() - start

    assert len(results) == 20
    assert all(r.success for r in results)
    assert elapsed < 30.0, f"Batch of 20 took {elapsed:.2f}s (limit: 30s)"


# ---------------------------------------------------------------------------
# run() integration (DB mocked)
# ---------------------------------------------------------------------------


def _make_mock_article(title: str, content: str = "Some article content here.") -> MagicMock:
    article = MagicMock()
    article.title = title
    article.content = content
    article.summary = None
    return article


def _make_mock_story(story_id: str, title: str, category_slug: str = "national", articles=None) -> MagicMock:
    story = MagicMock()
    story.id = story_id
    story.title = title
    story.category_slug = category_slug
    story.summary = None
    story.articles = articles or [_make_mock_article(title)]
    return story


def _make_mock_db(stories: list) -> MagicMock:
    db = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = stories
    db.scalars.return_value = scalars_result
    return db


def test_run_returns_empty_when_no_stories_need_summary():
    db = _make_mock_db([])
    agent = _agent()
    results = agent.run(db)
    assert results == []
    db.commit.assert_not_called()


def test_run_persists_summary_on_success():
    story = _make_mock_story("story-1", "Budget announced")
    db = _make_mock_db([story])

    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(70))
    agent._client = mock_client

    results = agent.run(db)

    assert len(results) == 1
    assert results[0].success is True
    assert story.summary == _valid_summary(70)
    db.commit.assert_called_once()


def test_run_does_not_persist_summary_on_failure():
    story = _make_mock_story("story-1", "Budget announced")
    db = _make_mock_db([story])

    agent = _agent(max_retries=0)
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(5))  # always invalid
    agent._client = mock_client

    results = agent.run(db)

    assert results[0].success is False
    assert story.summary is None
    db.commit.assert_called_once()


def test_run_combines_all_article_content_in_story():
    articles = [_make_mock_article("Headline A", "Content A"), _make_mock_article("Headline B", "Content B")]
    story = _make_mock_story("story-1", "Combined story", articles=articles)
    db = _make_mock_db([story])

    agent = _agent()
    captured_prompts = []

    def fake_invoke(prompt):
        captured_prompts.append(prompt)
        return MagicMock(content=_valid_summary(70))

    mock_client = MagicMock()
    mock_client.invoke.side_effect = fake_invoke
    agent._client = mock_client

    agent.run(db)

    assert len(captured_prompts) == 1
    assert "Headline A" in captured_prompts[0]
    assert "Headline B" in captured_prompts[0]


def test_run_falls_back_to_story_title_when_no_article_content():
    story = _make_mock_story("story-1", "Fallback Title", articles=[])
    db = _make_mock_db([story])

    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(70))
    agent._client = mock_client

    results = agent.run(db)

    assert results[0].success is True


def test_run_returns_list_of_summary_results():
    story = _make_mock_story("story-1", "Title")
    db = _make_mock_db([story])

    agent = _agent()
    mock_client = MagicMock()
    mock_client.invoke.return_value = MagicMock(content=_valid_summary(70))
    agent._client = mock_client

    results = agent.run(db)
    assert isinstance(results, list)
    assert all(isinstance(r, SummaryResult) for r in results)
