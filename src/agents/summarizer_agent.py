"""NewsSnap AI - LLM summarizer agent (Issue 11).

Compresses a full news article into a crisp single paragraph of roughly 60-80
words. The agent is a small LangGraph state machine:

    prepare -> generate -> validate -> (retry -> generate)* -> END

If langgraph is not installed the same nodes are executed sequentially, so the
agent behaves identically in a bare environment.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from src.config import settings
from src.utils.text_utils import count_words, remove_noise

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a news editor for NewsSnap, an Indian news app that gives readers the full story in 60 seconds. "
    "You rewrite a news article as ONE factual paragraph.\n"
    "Hard rules:\n"
    "- Output only the paragraph. No headline, no preamble, no bullet points, no quotes around it.\n"
    "- Target length is {target_min} to {target_max} words. Never go below {min_words} or above {max_words}.\n"
    "- Preserve the key facts: who, what, when, where and why. At least three of them must be present.\n"
    "- No clickbait, no teasers, no hype, no opinion, no questions to the reader.\n"
    "- Do not say 'this article', 'the report says', 'read on' or name the publication.\n"
    "- Keep numbers, names, places and dates exactly as they appear in the source.\n"
    "- Write in {language_name}, the language of the source article."
)

DEFAULT_STYLE = "Lead with the single most important development, then the supporting detail that explains it."

CATEGORY_STYLES: dict[str, str] = {
    "finance": "Be data heavy. Lead with the numbers: index levels, percentage moves, rates, amounts and the period they cover.",
    "business": "Lead with the company or deal, then the money involved, then what changes for the market.",
    "sports": "Lead with the result and the score or margin, then the decisive performance, then what it means for the series or table.",
    "politics": "Lead with the decision or announcement, attribute the key quote to the person who said it, then give the political consequence.",
    "national": "Lead with the decision or event and the authority behind it, then who is affected and from when.",
    "international": "Lead with the country or body involved and the action taken, then the stated reason and the reaction.",
    "technology": "Lead with the product, company or feature, then the specifications, price or availability that matter.",
    "science": "Lead with the finding, then who did the research and what it enables or proves.",
    "automobile": "Lead with the model and its launch or price, then the key specifications and variants.",
    "education": "Lead with the exam, result or policy, then the dates, eligibility and the students affected.",
    "health": "Lead with the health finding or advisory, then the numbers, the affected group and the official guidance.",
    "entertainment": "Lead with the release, casting or award, then the date and the people involved. Stay factual, no gossip framing.",
    "lifestyle": "Lead with the practical takeaway, then the supporting facts. Avoid listicle phrasing.",
    "crime": "Lead with the incident and the action taken by police or the court, then the charges and the stage of the case. Stay neutral.",
    "environment": "Lead with the measurement or event, then the location, scale and the official response.",
    "jobs": "Lead with the recruiting body and the number of vacancies, then the deadline and eligibility.",
    "defence": "Lead with the force or deal involved and the action, then the capability, value and timeline.",
    "real_estate": "Lead with the project, price or regulation, then the location and who it affects.",
    "opinion": "Report the argument being made and who makes it. Attribute clearly, do not adopt the position.",
}

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
}

# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

CLICKBAIT_PATTERNS: list[str] = [
    r"you (won't|will not) believe",
    r"what happened next",
    r"here('s| is) (why|what|how)",
    r"this is why",
    r"shocking",
    r"jaw[- ]dropping",
    r"mind[- ]blowing",
    r"went viral|goes viral|viral video",
    r"netizens react",
    r"must (read|watch|see)",
    r"click here",
    r"read (on|more)",
    r"find out (why|what|how|more)",
    r"the reason will (shock|surprise)",
    r"\bnumber \d+ will\b",
    r"breaks the internet",
    r"guess what",
]

META_PATTERNS: list[str] = [
    r"\bthis article\b",
    r"\bthe article\b",
    r"\bthe report says\b",
    r"\bin this (story|piece|summary)\b",
    r"\bas an ai\b",
    r"\bhere is (a|the) summary\b",
    r"\bsummary\s*:",
]

_CLICKBAIT_RE = re.compile("|".join(CLICKBAIT_PATTERNS), re.IGNORECASE)
_META_RE = re.compile("|".join(META_PATTERNS), re.IGNORECASE)

_WHO_RE = re.compile(
    r"(\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b)|"
    r"\b(government|ministry|minister|court|police|company|bank|committee|board|commission|team|club|university)\b"
)
_WHAT_RE = re.compile(
    r"\b(said|announced|launched|approved|rejected|won|lost|signed|raised|cut|filed|arrested|ordered|released|"
    r"reported|rose|fell|gained|declined|passed|banned|unveiled|will|has|have|is|are|was|were)\b|\w+ed\b",
    re.IGNORECASE,
)
_WHEN_RE = re.compile(
    r"\b(today|yesterday|tomorrow|tonight|this (week|month|year|morning|evening)|last (week|month|year|night)|"
    r"next (week|month|year)|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|(19|20)\d{2})\b",
    re.IGNORECASE,
)
_WHERE_RE = re.compile(
    r"\b(in|at|from|across|near|outside)\s+[A-Z][a-z]+|"
    r"\b(india|delhi|mumbai|bengaluru|bangalore|chennai|kolkata|hyderabad|pune|lucknow|state|district|"
    r"country|nationwide)\b",
    re.IGNORECASE,
)
_WHY_RE = re.compile(
    r"\b(because|due to|owing to|after|following|amid|citing|in order to|so that|as part of|to (boost|curb|reduce|"
    r"improve|address|counter|expand|support)|led to|resulting in|blamed on|over concerns)\b",
    re.IGNORECASE,
)

FACT_PATTERNS: dict[str, re.Pattern] = {
    "who": _WHO_RE,
    "what": _WHAT_RE,
    "when": _WHEN_RE,
    "where": _WHERE_RE,
    "why": _WHY_RE,
}


def find_clickbait(text: str) -> list[str]:
    """Return the clickbait phrases present in a summary."""
    return [m.group(0).strip() for m in _CLICKBAIT_RE.finditer(text)]


def find_facts(text: str) -> list[str]:
    """Return which of who/what/when/where/why are detectable in a summary."""
    return [name for name, pattern in FACT_PATTERNS.items() if pattern.search(text)]


@dataclass
class QualityReport:
    is_valid: bool
    word_count: int
    facts: list[str] = field(default_factory=list)
    clickbait: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def check_summary(
    summary: str,
    min_words: int = settings.SUMMARY_MIN_WORDS,
    max_words: int = settings.SUMMARY_MAX_WORDS,
    min_facts: int = settings.SUMMARY_MIN_FACTS,
) -> QualityReport:
    """Validate a generated summary against the acceptance rules of Issue 11."""
    text = (summary or "").strip()
    words = count_words(text)
    issues: list[str] = []

    if not text:
        return QualityReport(is_valid=False, word_count=0, issues=["empty summary"])

    if words < min_words:
        issues.append(f"too short: {words} words, minimum is {min_words}")
    if words > max_words:
        issues.append(f"too long: {words} words, maximum is {max_words}")

    facts = find_facts(text)
    if len(facts) < min_facts:
        missing = [name for name in FACT_PATTERNS if name not in facts]
        issues.append(f"only {len(facts)} of 5 key facts present, missing: {', '.join(missing)}")

    clickbait = find_clickbait(text)
    if clickbait:
        issues.append(f"clickbait language: {', '.join(sorted(set(clickbait)))}")

    meta = [m.group(0).strip() for m in _META_RE.finditer(text)]
    if meta:
        issues.append(f"meta commentary about the article: {', '.join(sorted(set(meta)))}")

    if "\n" in text:
        issues.append("summary must be a single paragraph")

    return QualityReport(is_valid=not issues, word_count=words, facts=facts, clickbait=clickbait, issues=issues)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SummaryResult:
    """A summary plus the metadata the pipeline stores alongside it."""

    summary: str
    word_count: int
    category: str
    language: str
    is_valid: bool
    attempts: int = 1
    facts: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    model: Optional[str] = None

    @property
    def attribution(self) -> Optional[str]:
        """Source attribution, deliberately kept out of the summary text body."""
        if self.source_name and self.source_url:
            return f"{self.source_name} ({self.source_url})"
        return self.source_name or self.source_url


ArticleInput = Union[str, dict]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def _default_llm_factory() -> Any:
    """Build the Groq chat model. Imported lazily so tests need no API key."""
    from langchain_groq import ChatGroq

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Copy .env.example to .env and add your Groq key.")

    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=settings.GROQ_TEMPERATURE,
        max_tokens=settings.GROQ_MAX_TOKENS,
        timeout=settings.GROQ_TIMEOUT_SECONDS,
    )


class SummarizerAgent:
    """Summarize news articles into one crisp, factual paragraph."""

    def __init__(
        self,
        llm: Optional[Any] = None,
        llm_factory: Optional[Callable[[], Any]] = None,
        min_words: int = settings.SUMMARY_MIN_WORDS,
        max_words: int = settings.SUMMARY_MAX_WORDS,
        target_min_words: int = settings.SUMMARY_TARGET_MIN_WORDS,
        target_max_words: int = settings.SUMMARY_TARGET_MAX_WORDS,
        min_facts: int = settings.SUMMARY_MIN_FACTS,
        max_retries: int = settings.SUMMARY_MAX_RETRIES,
        max_workers: int = settings.SUMMARY_BATCH_WORKERS,
        input_char_limit: int = settings.SUMMARY_INPUT_CHAR_LIMIT,
    ) -> None:
        self.min_words = min_words
        self.max_words = max_words
        self.target_min_words = target_min_words
        self.target_max_words = target_max_words
        self.min_facts = min_facts
        self.max_retries = max_retries
        self.max_workers = max_workers
        self.input_char_limit = input_char_limit

        self._llm = llm
        self._llm_factory = llm_factory or _default_llm_factory
        self._graph = None

    # -- LLM plumbing -------------------------------------------------------

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = self._llm_factory()
        return self._llm

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        response = self.llm.invoke([("system", system_prompt), ("human", user_prompt)])
        content = getattr(response, "content", response)
        return str(content).strip()

    # -- Prompt building ----------------------------------------------------

    def _system_prompt(self, language: str) -> str:
        return SYSTEM_PROMPT.format(
            target_min=self.target_min_words,
            target_max=self.target_max_words,
            min_words=self.min_words,
            max_words=self.max_words,
            language_name=LANGUAGE_NAMES.get(language, "English"),
        )

    def _user_prompt(self, state: dict) -> str:
        category = state["category"]
        style = CATEGORY_STYLES.get(category, DEFAULT_STYLE)

        parts = [f"Category: {category}", f"Style for this category: {style}"]
        if state.get("title"):
            parts.append(f"Headline: {state['title']}")
        parts.append(f"Article:\n{state['body']}")

        if state.get("issues"):
            parts.append(
                "Your previous attempt was rejected for these reasons:\n- "
                + "\n- ".join(state["issues"])
                + f"\nRewrite it. Stay between {self.target_min_words} and {self.target_max_words} words, "
                "name the people or bodies involved, say when and where it happened, and give the reason or "
                "consequence. Output only the corrected paragraph."
            )

        parts.append("Write the summary paragraph now.")
        return "\n\n".join(parts)

    # -- Graph nodes --------------------------------------------------------

    def _prepare(self, state: dict) -> dict:
        body = remove_noise(state.get("body") or "")
        if len(body) > self.input_char_limit:
            body = body[: self.input_char_limit].rsplit(" ", 1)[0]

        language = state.get("language") or detect_language(body) or "en"
        if language not in LANGUAGE_NAMES:
            language = "en"

        return {**state, "body": body, "language": language, "attempt": 0, "issues": []}

    def _generate(self, state: dict) -> dict:
        attempt = state.get("attempt", 0) + 1
        try:
            raw = self._call_llm(self._system_prompt(state["language"]), self._user_prompt(state))
            return {**state, "summary": clean_summary(raw), "attempt": attempt, "error": None}
        except Exception as exc:
            logger.warning("Groq summarization failed on attempt %s: %s", attempt, exc)
            return {**state, "summary": "", "attempt": attempt, "error": str(exc)}

    def _validate(self, state: dict) -> dict:
        if state.get("error"):
            report = QualityReport(is_valid=False, word_count=0, issues=[f"llm error: {state['error']}"])
        else:
            report = check_summary(
                state.get("summary", ""),
                min_words=self.min_words,
                max_words=self.max_words,
                min_facts=self.min_facts,
            )

        best = state.get("best")
        if best is None or _is_better(report, best["report"]):
            best = {"summary": state.get("summary", ""), "report": report}

        return {**state, "report": report, "issues": report.issues, "best": best}

    def _should_retry(self, state: dict) -> str:
        if state["report"].is_valid:
            return "done"
        if state.get("error"):
            return "done"
        if state["attempt"] > self.max_retries:
            return "done"
        return "retry"

    # -- Graph --------------------------------------------------------------

    def _build_graph(self) -> Any:
        """Compile the LangGraph state machine. Returns None if langgraph is absent."""
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            logger.debug("langgraph not installed, running summarizer nodes sequentially")
            return None

        graph = StateGraph(dict)
        graph.add_node("prepare", self._prepare)
        graph.add_node("generate", self._generate)
        graph.add_node("validate", self._validate)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", "generate")
        graph.add_edge("generate", "validate")
        graph.add_conditional_edges("validate", self._should_retry, {"retry": "generate", "done": END})
        return graph.compile()

    @property
    def graph(self) -> Any:
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def _run_sequential(self, state: dict) -> dict:
        state = self._prepare(state)
        while True:
            state = self._validate(self._generate(state))
            if self._should_retry(state) == "done":
                return state

    # -- Public API ---------------------------------------------------------

    def summarize(
        self,
        body: str,
        category: str = "national",
        title: Optional[str] = None,
        language: Optional[str] = None,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> str:
        """Summarize one article and return the summary paragraph."""
        return self.summarize_detailed(
            body,
            category=category,
            title=title,
            language=language,
            source_name=source_name,
            source_url=source_url,
        ).summary

    def summarize_detailed(
        self,
        body: str,
        category: str = "national",
        title: Optional[str] = None,
        language: Optional[str] = None,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> SummaryResult:
        """Summarize one article and return the summary with its quality metadata."""
        category = category or "national"

        if not (body or "").strip():
            return SummaryResult(
                summary="",
                word_count=0,
                category=category,
                language=language or "en",
                is_valid=False,
                attempts=0,
                issues=["empty article body"],
                source_name=source_name,
                source_url=source_url,
            )

        state = {
            "body": body,
            "category": category,
            "title": title,
            "language": language,
            "source_name": source_name,
            "source_url": source_url,
        }

        graph = self.graph
        final = graph.invoke(state) if graph is not None else self._run_sequential(state)

        report = final["best"]["report"]
        return SummaryResult(
            summary=final["best"]["summary"],
            word_count=report.word_count,
            category=final["category"],
            language=final["language"],
            is_valid=report.is_valid,
            attempts=final["attempt"],
            facts=report.facts,
            issues=report.issues,
            source_name=source_name,
            source_url=source_url,
            model=settings.GROQ_MODEL,
        )

    def batch_summarize(self, articles: list[ArticleInput], category: str = "national") -> list[str]:
        """Summarize many articles concurrently and return the summary paragraphs."""
        return [result.summary for result in self.batch_summarize_detailed(articles, category=category)]

    def batch_summarize_detailed(
        self,
        articles: list[ArticleInput],
        category: str = "national",
    ) -> list[SummaryResult]:
        """Summarize many articles concurrently, preserving input order.

        Each item is either the article body as a string, or a dict with the keys
        body, category, title, language, source_name and source_url.
        """
        if not articles:
            return []

        payloads = [_coerce_article(item, default_category=category) for item in articles]
        workers = max(1, min(self.max_workers, len(payloads)))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda kwargs: self.summarize_detailed(**kwargs), payloads))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WRAPPING_QUOTES = ('"', "'")
_LEAD_IN_RE = re.compile(
    r"^((here|this) (is|are)\s+)?(a|the)?\s*(summary|paragraph|news snap|snap)\s*[:\-]\s*",
    re.IGNORECASE,
)


def clean_summary(text: str) -> str:
    """Strip the wrappers an LLM likes to add around the paragraph."""
    cleaned = (text or "").strip()
    cleaned = _LEAD_IN_RE.sub("", cleaned).strip()

    for quote in _WRAPPING_QUOTES:
        if len(cleaned) > 1 and cleaned.startswith(quote) and cleaned.endswith(quote):
            cleaned = cleaned[1:-1].strip()
            break

    # Collapse an accidental multi paragraph answer into its first paragraph.
    blocks = [block.strip() for block in re.split(r"\n\s*\n", cleaned) if block.strip()]
    if blocks:
        cleaned = blocks[0]

    return re.sub(r"\s+", " ", cleaned).strip()


def detect_language(text: str) -> Optional[str]:
    """Best effort source language detection. Returns None when undetectable."""
    if not text or len(text.split()) < 5:
        return None
    try:
        from langdetect import detect

        return detect(text[:2000])
    except Exception:
        return None


def _is_better(candidate: QualityReport, current: QualityReport) -> bool:
    """Rank quality reports so the least broken attempt survives all retries."""
    if candidate.is_valid != current.is_valid:
        return candidate.is_valid
    if len(candidate.issues) != len(current.issues):
        return len(candidate.issues) < len(current.issues)
    return len(candidate.facts) > len(current.facts)


def _coerce_article(item: ArticleInput, default_category: str) -> dict:
    if isinstance(item, str):
        return {"body": item, "category": default_category}

    return {
        "body": item.get("body") or item.get("content") or "",
        "category": item.get("category") or item.get("category_slug") or default_category,
        "title": item.get("title"),
        "language": item.get("language"),
        "source_name": item.get("source_name"),
        "source_url": item.get("source_url") or item.get("url"),
    }
