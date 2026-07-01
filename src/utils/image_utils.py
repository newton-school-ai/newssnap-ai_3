from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

_SKIP_EXTENSIONS = (".gif", ".svg", ".ico", ".webp")
_MIN_SRC_LENGTH = 10

_ARTICLE_CONTAINERS = ["article", "main", ".article-body", "#article-body", ".post-content", ".entry-content"]


def _is_usable_src(src: str) -> bool:
    if not src or len(src) < _MIN_SRC_LENGTH:
        return False
    if src.startswith("data:"):
        return False
    lower = src.lower()
    return not any(lower.endswith(ext) for ext in _SKIP_EXTENSIONS)


def extract_lead_image(soup: BeautifulSoup, base_url: str | None = None) -> str | None:
    for meta_attrs in [
        {"property": "og:image"},
        {"name": "twitter:image"},
        {"property": "twitter:image"},
        {"property": "article:image"},
        {"name": "thumbnail"},
    ]:
        tag = soup.find("meta", attrs=meta_attrs)
        if tag and tag.get("content"):
            return tag["content"]

    for selector in _ARTICLE_CONTAINERS:
        container = soup.select_one(selector)
        if container:
            img = container.find("img", src=True)
            if img:
                src = img["src"]
                if base_url:
                    src = urljoin(base_url, src)
                if _is_usable_src(src):
                    return src

    for figure in soup.find_all("figure"):
        img = figure.find("img", src=True)
        if img:
            src = img["src"]
            if base_url:
                src = urljoin(base_url, src)
            if _is_usable_src(src):
                return src

    for img in soup.find_all("img", src=True):
        src = img["src"]
        if base_url:
            src = urljoin(base_url, src)
        if _is_usable_src(src):
            return src

    return None
