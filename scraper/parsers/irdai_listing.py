"""Parser for IRDAI listing pages (circulars, exposure drafts, industry trends).

IRDAI's CMS renders listings as tables of links pointing to PDFs or detail
pages. We extract every anchor that looks like a circular title (skipping
purely-numeric reference codes) and try to pick up a sibling date cell.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import Item

DATE_RE = re.compile(r"\b(\d{1,2}[-/ ][A-Za-z]{3,9}[-/ ]\d{2,4}|\d{4}-\d{2}-\d{2})\b")


def _parse_date(text: str) -> datetime | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return dateparser.parse(m.group(1), dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        return None


def parse(html: str, source) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()

    # Approach 1: table rows with links + dates.
    for row in soup.find_all("tr"):
        link = row.find("a", href=True)
        if not link:
            continue
        title = link.get_text(" ", strip=True)
        if len(title) < 8:
            continue
        href = urljoin(source.url, link["href"])
        if href in seen:
            continue
        seen.add(href)
        date = _parse_date(row.get_text(" ", strip=True))
        items.append(
            Item(
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=href,
                publish_date=date,
                categories=list(source.categories),
                tier=source.tier,
                partner_relevance=source.partner_relevance,
            )
        )

    # Approach 2: fallback to any PDF link if no table rows found.
    if not items:
        for a in soup.find_all("a", href=True):
            title = a.get_text(" ", strip=True)
            href = urljoin(source.url, a["href"])
            if not href.lower().endswith(".pdf"):
                continue
            if len(title) < 8 or href in seen:
                continue
            seen.add(href)
            items.append(
                Item(
                    source_id=source.id,
                    source_name=source.name,
                    title=title,
                    url=href,
                    categories=list(source.categories),
                    tier=source.tier,
                    partner_relevance=source.partner_relevance,
                )
            )
    return items
