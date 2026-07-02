from __future__ import annotations

import re

from bs4 import BeautifulSoup

_NOISE_LINE_RE = re.compile(
    r"(?i)^("
    r"subscribe(d)?( to)?( (our|the|this))?( (newsletter|daily brief|updates|alerts|email))?|"
    r"sign up( now| for free| today)?|"
    r"advertisement|sponsored( content| post)?|"
    r"share (this|on) (article|story|twitter|facebook|whatsapp|linkedin|instagram)?|"
    r"follow us( on (twitter|facebook|instagram|youtube|social media))?|"
    r"also read\s*:.*|read more\s*:.*|click here\s*(to|for).*|"
    r"terms of (use|service)|privacy policy|cookie policy|"
    r"all rights reserved|copyright\s*©?\s*\d{4}.*|"
    r"(tags|topics|categories)\s*:.*"
    r")\s*$"
)

_SHORT_NOISE_RE = re.compile(
    r"(?i)\b(share|tweet|email|print|save|bookmark|comments?|loading\.\.\.|"
    r"related (articles?|stories?|news)|you might also like|"
    r"more from|sponsored by|brought to you by)\b"
)

def strip_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip = True)



def remove_noise(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if _NOISE_LINE_RE.match(stripped):
            continue
        words = stripped.split()
        if len(words) <= 3 and _SHORT_NOISE_RE.search(stripped):
            continue
        cleaned.append(stripped)

    result = "\n".join(cleaned)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def is_incomplete(text: str, min_words: int = 100) -> bool:
    return count_words(text) < min_words
