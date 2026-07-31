from __future__ import annotations

import time

from src.agents.summarizer_agent import (
    CATEGORY_STYLES,
    SummarizerAgent,
    check_summary,
    clean_summary,
    find_clickbait,
    find_facts,
)
from src.agents.supervisor import ContentPipeline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ARTICLE_BODY = """
The Reserve Bank of India kept the repo rate unchanged at 6.5 percent on Friday, holding steady
for the eighth consecutive review. Governor Shaktikanta Das said in Mumbai that the committee voted
four to two in favour of the pause because food inflation remains above the comfort band.
Retail inflation stood at 5.1 percent in the previous month, down from 5.7 percent a year earlier.
The central bank also raised its growth forecast for the financial year to 7.2 percent from 7 percent,
citing stronger rural demand and a pickup in manufacturing output across twelve states.
Economists at several brokerages said the first rate cut is now unlikely before the second half of
the year. Bond yields eased three basis points after the announcement while banking stocks gained
in afternoon trade on the National Stock Exchange.
""".strip()

GOOD_SUMMARY = (
    "The Reserve Bank of India held the repo rate at 6.5 percent on Friday, its eighth consecutive pause, "
    "after the monetary policy committee voted four to two because food inflation stayed above the comfort "
    "band. Governor Shaktikanta Das said in Mumbai that retail inflation eased to 5.1 percent, and the "
    "central bank raised its growth forecast to 7.2 percent from 7 percent, citing stronger rural demand "
    "and higher manufacturing output nationwide this year."
)

SHORT_SUMMARY = "The Reserve Bank of India kept the repo rate unchanged on Friday in Mumbai."

CLICKBAIT_SUMMARY = (
    "You won't believe what the Reserve Bank of India announced on Friday in Mumbai. Governor Shaktikanta "
    "Das said the repo rate stays at 6.5 percent because food inflation remains high, and the shocking "
    "growth forecast was raised to 7.2 percent. Read on to find out why economists across India now expect "
    "the first rate cut only in the second half of the year."
)


class FakeLLM:
    """Stands in for ChatGroq. Returns queued replies and records the prompts it saw."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[list[tuple[str, str]]] = []

    def invoke(self, messages):
        self.calls.append(messages)
        reply = self.replies.pop(0) if self.replies else GOOD_SUMMARY
        return type("Reply", (), {"content": reply})()

    @property
    def last_user_prompt(self) -> str:
        return self.calls[-1][1][1]


class SlowLLM(FakeLLM):
    def __init__(self, replies: list[str], delay: float = 0.2) -> None:
        super().__init__(replies)
        self.delay = delay

    def invoke(self, messages):
        time.sleep(self.delay)
        return super().invoke(messages)


def make_agent(replies: list[str], **kwargs) -> tuple[SummarizerAgent, FakeLLM]:
    llm = FakeLLM(replies)
    return SummarizerAgent(llm=llm, **kwargs), llm


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------


def test_good_summary_passes_quality_check():
    report = check_summary(GOOD_SUMMARY)
    assert report.is_valid
    assert 60 <= report.word_count <= 80
    assert len(report.facts) >= 3


def test_short_summary_is_rejected():
    report = check_summary(SHORT_SUMMARY)
    assert not report.is_valid
    assert any("too short" in issue for issue in report.issues)


def test_long_summary_is_rejected():
    report = check_summary(" ".join(["word"] * 130))
    assert not report.is_valid
    assert any("too long" in issue for issue in report.issues)


def test_clickbait_summary_is_rejected():
    report = check_summary(CLICKBAIT_SUMMARY)
    assert not report.is_valid
    assert report.clickbait
    assert any("clickbait" in issue for issue in report.issues)


def test_meta_commentary_is_rejected():
    text = "This article explains how " + GOOD_SUMMARY
    report = check_summary(text)
    assert not report.is_valid
    assert any("meta commentary" in issue for issue in report.issues)


def test_empty_summary_is_rejected():
    report = check_summary("")
    assert not report.is_valid
    assert report.issues == ["empty summary"]


def test_find_facts_detects_who_when_where_why():
    facts = find_facts(GOOD_SUMMARY)
    for expected in ("who", "what", "when", "where", "why"):
        assert expected in facts


def test_find_clickbait_returns_matched_phrases():
    assert find_clickbait(CLICKBAIT_SUMMARY)
    assert find_clickbait(GOOD_SUMMARY) == []


def test_clean_summary_strips_wrappers():
    raw = 'Here is a summary: "The Reserve Bank held rates steady.\n\nExtra paragraph."'
    assert clean_summary(raw) == "The Reserve Bank held rates steady."


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


def test_summarize_returns_paragraph_in_word_range():
    agent, llm = make_agent([GOOD_SUMMARY])
    summary = agent.summarize(ARTICLE_BODY, category="finance")

    assert isinstance(summary, str)
    assert 60 <= len(summary.split()) <= 80
    assert len(llm.calls) == 1


def test_summarize_detailed_carries_metadata_not_attribution_in_text():
    agent, _ = make_agent([GOOD_SUMMARY])
    result = agent.summarize_detailed(
        ARTICLE_BODY,
        category="finance",
        source_name="The Hindu",
        source_url="https://example.com/rbi-policy",
    )

    assert result.is_valid
    assert result.attempts == 1
    assert result.attribution == "The Hindu (https://example.com/rbi-policy)"
    assert "The Hindu" not in result.summary


def test_category_prompts_differ_by_category():
    agent, llm = make_agent([GOOD_SUMMARY, GOOD_SUMMARY])
    agent.summarize(ARTICLE_BODY, category="finance")
    finance_prompt = llm.last_user_prompt
    agent.summarize(ARTICLE_BODY, category="sports")
    sports_prompt = llm.last_user_prompt

    assert CATEGORY_STYLES["finance"] in finance_prompt
    assert CATEGORY_STYLES["sports"] in sports_prompt
    assert finance_prompt != sports_prompt


def test_unknown_category_falls_back_to_default_style():
    agent, llm = make_agent([GOOD_SUMMARY])
    agent.summarize(ARTICLE_BODY, category="weather")
    assert "Category: weather" in llm.last_user_prompt


def test_retry_on_bad_summary_then_succeed():
    agent, llm = make_agent([SHORT_SUMMARY, GOOD_SUMMARY])
    result = agent.summarize_detailed(ARTICLE_BODY, category="finance")

    assert result.is_valid
    assert result.attempts == 2
    assert len(llm.calls) == 2
    assert "rejected" in llm.last_user_prompt


def test_retry_prompt_includes_failure_reasons():
    agent, llm = make_agent([CLICKBAIT_SUMMARY, GOOD_SUMMARY])
    agent.summarize(ARTICLE_BODY, category="national")
    assert "clickbait" in llm.last_user_prompt


def test_retries_are_capped_at_two():
    agent, llm = make_agent([SHORT_SUMMARY, SHORT_SUMMARY, SHORT_SUMMARY, GOOD_SUMMARY], max_retries=2)
    result = agent.summarize_detailed(ARTICLE_BODY, category="finance")

    assert len(llm.calls) == 3
    assert result.attempts == 3
    assert not result.is_valid
    assert result.summary == SHORT_SUMMARY


def test_empty_body_short_circuits_without_calling_llm():
    agent, llm = make_agent([GOOD_SUMMARY])
    result = agent.summarize_detailed("   ", category="finance")

    assert result.summary == ""
    assert not result.is_valid
    assert llm.calls == []


def test_llm_error_is_captured_not_raised():
    class BrokenLLM:
        def invoke(self, messages):
            raise RuntimeError("groq timeout")

    agent = SummarizerAgent(llm=BrokenLLM())
    result = agent.summarize_detailed(ARTICLE_BODY, category="finance")

    assert result.summary == ""
    assert not result.is_valid
    assert any("groq timeout" in issue for issue in result.issues)


def test_language_is_detected_and_defaults_to_english():
    agent, llm = make_agent([GOOD_SUMMARY])
    result = agent.summarize_detailed(ARTICLE_BODY, category="finance")
    assert result.language == "en"
    assert "English" in llm.calls[-1][0][1]


def test_hindi_article_is_summarized_in_hindi():
    # Devanagari body kept out of the repo (ASCII-only rule); the source language is passed in
    # the same way the scraper supplies it.
    agent, llm = make_agent([GOOD_SUMMARY])
    result = agent.summarize_detailed(ARTICLE_BODY, category="finance", language="hi")

    assert result.language == "hi"
    assert "Hindi" in llm.calls[-1][0][1]


def test_long_body_is_truncated_before_prompting():
    agent, llm = make_agent([GOOD_SUMMARY], input_char_limit=500)
    agent.summarize("word " * 5000, category="national")
    assert len(llm.last_user_prompt) < 1500


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


def test_batch_summarize_returns_one_summary_per_article():
    agent, llm = make_agent([GOOD_SUMMARY] * 5)
    summaries = agent.batch_summarize([ARTICLE_BODY] * 5, category="finance")

    assert len(summaries) == 5
    assert all(60 <= len(s.split()) <= 80 for s in summaries)
    assert len(llm.calls) == 5


def test_batch_summarize_accepts_dicts_with_per_article_category():
    agent, llm = make_agent([GOOD_SUMMARY] * 2)
    articles = [
        {"body": ARTICLE_BODY, "category": "finance", "title": "RBI holds rates"},
        {"body": ARTICLE_BODY, "category": "sports", "url": "https://example.com/match"},
    ]
    results = agent.batch_summarize_detailed(articles)

    assert [r.category for r in results] == ["finance", "sports"]
    assert results[1].source_url == "https://example.com/match"
    assert any(CATEGORY_STYLES["sports"] in call[1][1] for call in llm.calls)


def test_batch_summarize_empty_list():
    agent, llm = make_agent([])
    assert agent.batch_summarize([]) == []
    assert llm.calls == []


def test_batch_of_twenty_runs_concurrently():
    agent = SummarizerAgent(llm=SlowLLM([GOOD_SUMMARY] * 20, delay=0.2), max_workers=8)

    started = time.monotonic()
    summaries = agent.batch_summarize([ARTICLE_BODY] * 20, category="finance")
    elapsed = time.monotonic() - started

    assert len(summaries) == 20
    # Serial execution would take 4 seconds; concurrency must beat that clearly.
    assert elapsed < 2.0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def test_pipeline_attaches_summary_and_metadata():
    agent, _ = make_agent([GOOD_SUMMARY])
    pipeline = ContentPipeline(summarizer=agent)
    articles = [{"body": ARTICLE_BODY, "category": "finance", "source_name": "Mint"}]

    result = pipeline.run(articles)

    assert result.stats.summarized == 1
    assert result.articles[0]["summary"] == GOOD_SUMMARY
    assert result.articles[0]["summary_metadata"]["word_count"] == len(GOOD_SUMMARY.split())
    assert articles[0].get("summary") is None


def test_pipeline_skips_short_and_already_summarized_articles():
    agent, llm = make_agent([GOOD_SUMMARY])
    pipeline = ContentPipeline(summarizer=agent)
    articles = [
        {"body": "too short to summarize", "category": "national"},
        {"body": ARTICLE_BODY, "category": "finance", "summary": "already done"},
        {"body": ARTICLE_BODY, "category": "finance"},
    ]

    result = pipeline.run(articles)

    assert result.stats.skipped == 2
    assert result.stats.summarized == 1
    assert len(llm.calls) == 1


def test_pipeline_counts_failed_summaries():
    agent, _ = make_agent([SHORT_SUMMARY] * 3)
    pipeline = ContentPipeline(summarizer=agent)

    result = pipeline.run([{"body": ARTICLE_BODY, "category": "finance"}])

    assert result.stats.failed == 1
    assert result.articles[0]["summary_metadata"]["is_valid"] is False


def test_pipeline_runs_injected_dedup_stage():
    agent, _ = make_agent([GOOD_SUMMARY])
    pipeline = ContentPipeline(summarizer=agent, dedup_agent=lambda articles: articles[:1])

    result = pipeline.run([{"body": ARTICLE_BODY, "category": "finance"}] * 3)

    assert result.stats.received == 3
    assert len(result.articles) == 1


def test_pipeline_handles_empty_input():
    agent, llm = make_agent([])
    result = ContentPipeline(summarizer=agent).run([])

    assert result.articles == []
    assert result.stats.as_dict() == {"received": 0, "skipped": 0, "summarized": 0, "failed": 0}
