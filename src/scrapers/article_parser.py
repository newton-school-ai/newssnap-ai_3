from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.image_utils import extract_lead_image
from src.utils.text_utils import count_words, is_incomplete, remove_noise, strip_html

logger = logging.getLogger(__name__)

MIN_COMPLETE_WORDS = 100

CONTENT_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "sports": ["cricket", "football", "tennis", "ipl", "match", "tournament", "player", "stadium", "goal", "wicket"],
    "technology": ["smartphone", "laptop", "startup", "software", "app", "ai", "artificial intelligence", "tech", "gadget"],
    "business": ["market", "stock", "economy", "rupee", "gdp", "inflation", "budget", "shares", "investment", "company"],
    "entertainment": ["bollywood", "movie", "film", "actor", "actress", "celebrity", "ott", "series", "award"],
    "health": ["hospital", "doctor", "vaccine", "disease", "health", "medicine", "patient", "surgery", "covid"],
    "international": ["us", "usa", "china", "pakistan", "russia", "ukraine", "un", "nato", "global", "world"],
    "politics": ["parliament", "minister", "election", "vote", "party", "government", "bjp", "congress", "policy"],
}


@dataclass
class ParsedArticle:
    title: str
    body: str
    image_url: Optional[str]
    source_url: str
    publish_time: Optional[datetime]
    category: str


@dataclass
class NormalizedArticle:
    title: str
    body: str
    image_url: Optional[str]
    source_url: str
    publish_time: Optional[datetime]
    category: str
    language: Optional[str] = field(default=None)
    word_count: int = field(default=0)
    is_complete: bool = field(default=True)


# ---------------------------------------------------------------------------
# Existing helpers (used by playwright_scraper and rss_scraper)
# ---------------------------------------------------------------------------


def extract_meta_content(soup: BeautifulSoup, selector: str) -> Optional[str]:
    tag = soup.select_one(selector)
    if tag is None:
        return None
    if tag.name == "meta":
        return tag.get("content")
    return tag.get_text(strip=True)


def extract_links(html: str, base_url: str, link_selector: str, limit: int = 30) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for el in soup.select(link_selector)[:limit]:
        href = el.get("href")
        if not href:
            continue
        absolute = urljoin(base_url, href)
        if absolute not in links:
            links.append(absolute)
    return links


def map_category(url: str, category_mapping: dict[str, str], default: str) -> str:
    for path_fragment, category in category_mapping.items():
        if path_fragment in url:
            return category
    return default


def extract_article_body(soup: BeautifulSoup, body_selector: str) -> str:
    container = soup.select_one(body_selector)
    if container is None:
        return ""
    paragraphs = [p.get_text(strip=True) for p in container.find_all("p")]
    text = "\n".join(p for p in paragraphs if p)
    return text or container.get_text(strip=True)


# ---------------------------------------------------------------------------
# New: language detection
# ---------------------------------------------------------------------------


def detect_language(text: str) -> Optional[str]:
    if not text or len(text.split()) < 5:
        return None
    try:
        from langdetect import detect

        return detect(text[:2000])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# New: newspaper3k extraction
# ---------------------------------------------------------------------------


def extract_with_newspaper(html: str, url: str) -> dict:
    try:
        from newspaper import Article

        article = Article(url)
        article.set_html(html)
        article.parse()
        return {
            "title": article.title or "",
            "body": article.text or "",
            "image_url": article.top_image or None,
            "publish_date": article.publish_date,
            "language": article.meta_lang or None,
        }
    except Exception as exc:
        logger.warning("newspaper3k extraction failed for %s: %s", url, exc)
        return {"title": "", "body": "", "image_url": None, "publish_date": None, "language": None}


# ---------------------------------------------------------------------------
# New: content-based category detection
# ---------------------------------------------------------------------------


def category_from_content(text: str, category_mapping: dict[str, str] | None = None) -> Optional[str]:
    lower = text.lower()
    scores: dict[str, int] = {}
    for cat, keywords in CONTENT_CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[cat] = score
    if not scores:
        return None
    return max(scores, key=lambda c: scores[c])


# ---------------------------------------------------------------------------
# New: full normalization pipeline
# ---------------------------------------------------------------------------


def normalize_article(
    html: str,
    url: str,
    config,
    source_language: Optional[str] = None,
) -> NormalizedArticle:
    soup = BeautifulSoup(html, "html.parser")

    np_data = extract_with_newspaper(html, url)

    title = np_data["title"]
    body = np_data["body"]
    image_url = np_data["image_url"]
    publish_time = np_data["publish_date"]

    if not title and config.title_selector:
        title = extract_meta_content(soup, config.title_selector) or ""

    if not body and config.body_selector:
        raw_body = extract_article_body(soup, config.body_selector)
        body = strip_html(raw_body)

    body = remove_noise(body)

    if not image_url:
        base = getattr(config, "base_url", None)
        image_url = extract_lead_image(soup, base_url=base)
        if not image_url and config.image_selector:
            image_url = extract_meta_content(soup, config.image_selector)

    if not publish_time and config.date_selector:
        from src.utils.time_utils import parse_datetime

        raw_date = extract_meta_content(soup, config.date_selector)
        publish_time = parse_datetime(raw_date)

    category = map_category(url, config.category_mapping, config.category_slug)
    if category == config.category_slug:
        detected_cat = category_from_content(body)
        if detected_cat:
            category = detected_cat

    language = detect_language(body) or source_language

    wc = count_words(body)
    complete = not is_incomplete(body, min_words=MIN_COMPLETE_WORDS)

    return NormalizedArticle(
        title=title,
        body=body,
        image_url=image_url,
        source_url=url,
        publish_time=publish_time,
        category=category,
        language=language,
        word_count=wc,
        is_complete=complete,
    )
