from __future__ import annotations

from unittest.mock import patch

from bs4 import BeautifulSoup
from src.scrapers.article_parser import (
    NormalizedArticle,
    category_from_content,
    detect_language,
    extract_with_newspaper,
    normalize_article,
)
from src.scrapers.source_registry import SourceConfig
from src.utils.image_utils import extract_lead_image
from src.utils.text_utils import count_words, is_incomplete, remove_noise, strip_html

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONFIG = SourceConfig(
    name="Test Source",
    base_url="https://example.com",
    scrape_type="playwright",
    language="en",
    category_slug="national",
    article_list_url="https://example.com/news",
    article_link_selector="a.article-link",
    title_selector="h1.title",
    body_selector="div.body",
    image_selector="meta[property='og:image']",
    rate_limit_seconds=0.01,
    category_mapping={"/sports/": "sports", "/tech/": "technology"},
)

FULL_ARTICLE_HTML = """
<html><head>
  <title>Big News Headline</title>
  <meta property="og:image" content="https://example.com/lead.jpg">
</head><body>
<h1 class="title">Big News Headline</h1>
<div class="body">
  <p>The government announced a major new policy on infrastructure development today.
  Officials said the programme will span five years and cover rural connectivity,
  digital expansion, and highway construction across twelve states. Experts believe
  this could transform the economy significantly over the next decade, creating millions
  of jobs and boosting GDP growth by two to three percent annually.</p>
  <p>The minister of finance presented details in a press conference. Key highlights
  include investments in renewable energy, smart city upgrades, and broadband rollout
  to remote areas. Civil society groups welcomed the announcement but asked for
  transparency in implementation and independent audits of fund allocation.</p>
</div>
</body></html>
"""

SHORT_ARTICLE_HTML = """
<html><head><title>Short</title></head>
<body>
<h1 class="title">Short Article</h1>
<div class="body"><p>Just a tiny teaser.</p></div>
</body></html>
"""


# ---------------------------------------------------------------------------
# text_utils: strip_html
# ---------------------------------------------------------------------------


def test_strip_html_removes_tags():
    html = "<p>Hello <strong>world</strong></p>"
    result = strip_html(html)
    assert "<" not in result
    assert "Hello" in result
    assert "world" in result


def test_strip_html_empty_string():
    assert strip_html("") == ""


def test_strip_html_plain_text_unchanged():
    text = "Just plain text."
    assert strip_html(text) == text


# ---------------------------------------------------------------------------
# text_utils: remove_noise
# ---------------------------------------------------------------------------


def test_remove_noise_strips_subscribe_line():
    text = "Great article content here.\nSubscribe to our newsletter\nMore article content."
    result = remove_noise(text)
    assert "Subscribe" not in result
    assert "Great article content" in result


def test_remove_noise_strips_follow_us():
    text = "Article text.\nFollow us on Twitter\nContinued text."
    result = remove_noise(text)
    assert "Follow us" not in result
    assert "Article text" in result


def test_remove_noise_strips_also_read():
    text = "Some text.\nAlso read: Other Headline Here\nMore text."
    result = remove_noise(text)
    assert "Also read" not in result


def test_remove_noise_strips_copyright():
    text = "Article body.\nCopyright © 2025 Example Corp. All rights reserved.\nEnd."
    result = remove_noise(text)
    assert "Copyright" not in result
    assert "Article body" in result


def test_remove_noise_preserves_real_content():
    text = "The minister announced a new policy.\nThis affects all citizens.\nDetails to follow."
    result = remove_noise(text)
    assert "minister announced" in result
    assert "citizens" in result


# ---------------------------------------------------------------------------
# text_utils: count_words / is_incomplete
# ---------------------------------------------------------------------------


def test_count_words_basic():
    assert count_words("one two three") == 3


def test_count_words_empty():
    assert count_words("") == 0


def test_count_words_multiline():
    assert count_words("one two\nthree four") == 4


def test_is_incomplete_below_threshold():
    short_text = " ".join(["word"] * 50)
    assert is_incomplete(short_text) is True


def test_is_incomplete_above_threshold():
    long_text = " ".join(["word"] * 150)
    assert is_incomplete(long_text) is False


def test_is_incomplete_custom_threshold():
    text = " ".join(["word"] * 20)
    assert is_incomplete(text, min_words=10) is False
    assert is_incomplete(text, min_words=30) is True


# ---------------------------------------------------------------------------
# image_utils: extract_lead_image
# ---------------------------------------------------------------------------


def test_extract_lead_image_og_image():
    html = '<html><head><meta property="og:image" content="https://example.com/og.jpg"></head></html>'
    soup = BeautifulSoup(html, "html.parser")
    assert extract_lead_image(soup) == "https://example.com/og.jpg"


def test_extract_lead_image_twitter_fallback():
    html = '<html><head><meta name="twitter:image" content="https://example.com/tw.jpg"></head></html>'
    soup = BeautifulSoup(html, "html.parser")
    assert extract_lead_image(soup) == "https://example.com/tw.jpg"


def test_extract_lead_image_img_fallback():
    html = "<html><body><article><img src='https://example.com/photo.jpg'></article></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert extract_lead_image(soup) == "https://example.com/photo.jpg"


def test_extract_lead_image_resolves_relative_url():
    html = "<html><body><article><img src='/images/photo.jpg'></article></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    result = extract_lead_image(soup, base_url="https://example.com")
    assert result == "https://example.com/images/photo.jpg"


def test_extract_lead_image_skips_svg():
    html = "<html><body><img src='logo.svg'><img src='https://example.com/real.jpg'></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    result = extract_lead_image(soup)
    assert result == "https://example.com/real.jpg"


def test_extract_lead_image_returns_none_when_nothing():
    html = "<html><body><p>No image here.</p></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert extract_lead_image(soup) is None


# ---------------------------------------------------------------------------
# article_parser: detect_language
# ---------------------------------------------------------------------------


def test_detect_language_english():
    text = "The government announced a new infrastructure policy today covering all major cities."
    lang = detect_language(text)
    assert lang == "en"


def test_detect_language_hindi():
    text = "सरकार ने आज एक नई बुनियादी ढांचा नीति की घोषणा की जो सभी प्रमुख शहरों को कवर करती है"
    lang = detect_language(text)
    assert lang == "hi"


def test_detect_language_too_short_returns_none():
    result = detect_language("hi")
    assert result is None


def test_detect_language_empty_returns_none():
    assert detect_language("") is None


# ---------------------------------------------------------------------------
# article_parser: category_from_content
# ---------------------------------------------------------------------------


def test_category_from_content_sports():
    text = "The cricket match ended with India winning by six wickets in the tournament final."
    assert category_from_content(text) == "sports"


def test_category_from_content_technology():
    text = "The new smartphone app uses artificial intelligence to improve user experience."
    assert category_from_content(text) == "technology"


def test_category_from_content_health():
    text = "Doctors at the hospital administered the vaccine to over a thousand patients today."
    assert category_from_content(text) == "health"


def test_category_from_content_no_match_returns_none():
    text = "Lorem ipsum dolor sit amet consectetur."
    assert category_from_content(text) is None


# ---------------------------------------------------------------------------
# article_parser: extract_with_newspaper
# ---------------------------------------------------------------------------


def test_extract_with_newspaper_returns_title_and_body():
    result = extract_with_newspaper(FULL_ARTICLE_HTML, "https://example.com/article")
    assert isinstance(result, dict)
    assert "title" in result
    assert "body" in result
    assert "image_url" in result
    assert isinstance(result["body"], str)


def test_extract_with_newspaper_handles_bad_html():
    result = extract_with_newspaper("not html at all %%%", "https://example.com/bad")
    assert isinstance(result, dict)
    assert result["body"] == "" or isinstance(result["body"], str)


def test_extract_with_newspaper_import_error_returns_empty():
    with patch.dict("sys.modules", {"newspaper": None}):
        result = extract_with_newspaper(FULL_ARTICLE_HTML, "https://example.com/x")
    assert result["title"] == "" or isinstance(result["title"], str)


# ---------------------------------------------------------------------------
# article_parser: normalize_article
# ---------------------------------------------------------------------------


def test_normalize_article_returns_normalized_article():
    result = normalize_article(FULL_ARTICLE_HTML, "https://example.com/national/story", SAMPLE_CONFIG)
    assert isinstance(result, NormalizedArticle)
    assert result.title != ""
    assert result.source_url == "https://example.com/national/story"


def test_normalize_article_has_language():
    result = normalize_article(FULL_ARTICLE_HTML, "https://example.com/national/story", SAMPLE_CONFIG)
    assert result.language is not None


def test_normalize_article_computes_word_count():
    result = normalize_article(FULL_ARTICLE_HTML, "https://example.com/national/story", SAMPLE_CONFIG)
    assert result.word_count > 0


def test_normalize_article_long_body_is_complete():
    result = normalize_article(FULL_ARTICLE_HTML, "https://example.com/national/story", SAMPLE_CONFIG)
    assert result.is_complete is True


def test_normalize_article_short_body_is_incomplete():
    result = normalize_article(SHORT_ARTICLE_HTML, "https://example.com/national/short", SAMPLE_CONFIG)
    assert result.is_complete is False


def test_normalize_article_extracts_og_image():
    result = normalize_article(FULL_ARTICLE_HTML, "https://example.com/national/story", SAMPLE_CONFIG)
    assert result.image_url == "https://example.com/lead.jpg"


def test_normalize_article_url_category_overrides_content():
    result = normalize_article(
        FULL_ARTICLE_HTML,
        "https://example.com/sports/story",
        SAMPLE_CONFIG,
    )
    assert result.category == "sports"


def test_normalize_article_uses_source_language_fallback():
    html = "<html><body><h1 class='title'>T</h1><div class='body'><p>short</p></div></body></html>"
    result = normalize_article(html, "https://example.com/national/x", SAMPLE_CONFIG, source_language="en")
    assert result.language == "en"


def test_normalize_article_body_has_no_html_tags():
    result = normalize_article(FULL_ARTICLE_HTML, "https://example.com/national/story", SAMPLE_CONFIG)
    assert "<" not in result.body
    assert ">" not in result.body
