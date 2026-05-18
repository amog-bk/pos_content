"""Parser for Google News RSS feeds (site-scoped).

We use this as a reliable proxy for sites that block direct scraping
(ET Insurance, Business Standard, Moneycontrol). Google News RSS returns
titles, links, and timestamps for the latest indexed articles on the queried
site, without auth or rate limits in our usage range.

Example URL (in sources.yml):
  https://news.google.com/rss/search?q=site%3Aeconomictimes.indiatimes.com+insurance&hl=en-IN&gl=IN&ceid=IN%3Aen

Google News appends "- Publication Name" to every title; we strip that off
and use it as the displayed source name (if present).
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from .base import Item


def parse(xml: str, source) -> list[Item]:
    soup = BeautifulSoup(xml, "xml")
    items: list[Item] = []
    for entry in soup.find_all("item"):
        title_el = entry.find("title")
        link_el = entry.find("link")
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        url = link_el.get_text(strip=True)
        if not title or not url:
            continue

        pub_el = entry.find("pubDate")
        date = None
        if pub_el:
            try:
                date = dateparser.parse(pub_el.get_text(strip=True))
            except (ValueError, OverflowError, TypeError):
                date = None

        # Google News titles end with " - Publication Name". Promote that name
        # so the digest shows e.g. "Economic Times" rather than just "Google News".
        display_source = source.name
        if " - " in title:
            head, tail = title.rsplit(" - ", 1)
            if 2 <= len(tail) <= 60:
                title = head.strip()
                display_source = tail.strip()

        items.append(
            Item(
                source_id=source.id,
                source_name=display_source,
                title=title,
                url=url,
                publish_date=date,
                categories=list(source.categories),
                tier=source.tier,
                partner_relevance=source.partner_relevance,
            )
        )
    return items
