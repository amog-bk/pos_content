"""Generic HTML link extractor.

Designed as a robust fallback that works against most news/index pages without
hand-tuning per site. Strategy:
  - Parse <a> tags inside the main content area (heuristics: <main>, <article>,
    largest <section>, or fall back to <body>).
  - Keep links whose text reads like a headline (3+ words, not nav-ish).
  - Resolve relative URLs against the source URL.
  - Deduplicate by URL.

Per-site parsers can be added later when a source's HTML demands it — drop a
new file under parsers/ and reference it by `parser:` in sources.yml.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import Item

NAV_PATTERNS = re.compile(
    r"^(home|about|contact|login|sign[- ]?in|register|subscribe|newsletter|menu|"
    r"privacy|terms|cookies|advertise|jobs|careers|help|faq|search|share|follow|"
    r"tweet|whatsapp|facebook|linkedin|instagram|youtube|telegram|copy link|"
    r"more|read more|view all|see all|next|previous|back to top|skip to)$",
    re.IGNORECASE,
)


def _looks_like_headline(text: str) -> bool:
    text = text.strip()
    if len(text) < 20 or len(text) > 220:
        return False
    if NAV_PATTERNS.match(text):
        return False
    words = text.split()
    if len(words) < 4:
        return False
    if sum(1 for w in words if w[:1].isupper()) / max(len(words), 1) > 0.85:
        return False
    return True


def _pick_main(soup: BeautifulSoup):
    for tag in ("main", "article"):
        el = soup.find(tag)
        if el:
            return el
    sections = soup.find_all("section")
    if sections:
        return max(sections, key=lambda s: len(s.get_text(strip=True)))
    return soup.body or soup


def parse(html: str, source) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    main = _pick_main(soup)
    base = source.url
    base_host = urlparse(base).netloc

    seen: set[str] = set()
    items: list[Item] = []

    for a in main.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if not _looks_like_headline(text):
            continue
        href = urljoin(base, a["href"])
        # Stay on-domain for noise reduction.
        if urlparse(href).netloc and base_host not in urlparse(href).netloc:
            continue
        if href in seen:
            continue
        seen.add(href)
        items.append(
            Item(
                source_id=source.id,
                source_name=source.name,
                title=text,
                url=href,
                categories=list(source.categories),
                tier=source.tier,
                partner_relevance=source.partner_relevance,
            )
        )
    return items
