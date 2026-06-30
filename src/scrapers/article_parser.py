from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass
class ParsedArticle:
    title: str
    body: str
    image_url: Optional[str]
    source_url: str
    publish_time: Optional[datetime]
    category: str


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
