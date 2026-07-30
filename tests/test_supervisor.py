from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.supervisor import ContentPipelineSupervisor, PipelineResult


def _make_supervisor():
    dedup_agent = MagicMock()
    story_clusterer = MagicMock()
    summarizer_agent = MagicMock()
    supervisor = ContentPipelineSupervisor(
        dedup_agent=dedup_agent,
        story_clusterer=story_clusterer,
        summarizer_agent=summarizer_agent,
    )
    return supervisor, dedup_agent, story_clusterer, summarizer_agent


def test_run_calls_agents_in_order():
    supervisor, dedup_agent, story_clusterer, summarizer_agent = _make_supervisor()

    call_order = []
    dedup_agent.run.side_effect = lambda *a, **kw: call_order.append("dedup") or MagicMock(
        unique_count=1, processed=1
    )
    story_clusterer.run.side_effect = lambda *a, **kw: call_order.append("cluster") or MagicMock(
        stories_created=1
    )
    summarizer_agent.run.side_effect = lambda *a, **kw: call_order.append("summarize") or []

    db = MagicMock()
    supervisor.run(db)

    assert call_order == ["dedup", "cluster", "summarize"]


def test_run_passes_db_and_registry_to_dedup_agent():
    supervisor, dedup_agent, story_clusterer, summarizer_agent = _make_supervisor()
    dedup_agent.run.return_value = MagicMock(unique_count=0, processed=0)
    story_clusterer.run.return_value = MagicMock(stories_created=0)
    summarizer_agent.run.return_value = []

    db = MagicMock()
    registry = MagicMock()
    supervisor.run(db, registry=registry)

    dedup_agent.run.assert_called_once_with(db, registry=registry)
    story_clusterer.run.assert_called_once_with(db)
    summarizer_agent.run.assert_called_once_with(db)


def test_run_returns_pipeline_result():
    supervisor, dedup_agent, story_clusterer, summarizer_agent = _make_supervisor()
    dedup_result = MagicMock(unique_count=3, processed=5)
    clustering_result = MagicMock(stories_created=2)
    summary_results = [MagicMock(success=True), MagicMock(success=False)]

    dedup_agent.run.return_value = dedup_result
    story_clusterer.run.return_value = clustering_result
    summarizer_agent.run.return_value = summary_results

    result = supervisor.run(MagicMock())

    assert isinstance(result, PipelineResult)
    assert result.dedup is dedup_result
    assert result.clustering is clustering_result
    assert result.summaries == summary_results


def test_default_construction_uses_real_agent_classes():
    supervisor = ContentPipelineSupervisor()
    from src.agents.dedup_agent import DedupAgent
    from src.agents.story_clusterer import StoryClusterer
    from src.agents.summarizer_agent import SummarizerAgent

    assert isinstance(supervisor.dedup_agent, DedupAgent)
    assert isinstance(supervisor.story_clusterer, StoryClusterer)
    assert isinstance(supervisor.summarizer_agent, SummarizerAgent)
