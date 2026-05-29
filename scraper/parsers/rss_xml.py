"""Parser for direct publisher RSS feeds.

This is the same RSS parsing logic as `google_news_rss` minus the
" - PublicationName" tail-stripping (direct publisher feeds already carry
clean titles, and the splitting heuristic occasionally chops legitimate
"Foo - Bar: Baz" titles).

Use this for feeds like:
  - https://www.moneycontrol.com/rss/business.xml
  - https://www.livemint.com/rss/money
  - https://www.business-standard.com/rss/finance-103.rss
  - https://economictimes.indiatimes.com/.../rssfeeds/13352306.cms
  - https://www.thehindubusinessline.com/feeder/default.rss

Items keep their natural publisher URL (no Google News redirect base64),
so og:description enrichment in main.py works against them.
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

        # Use the RSS <description> if it looks substantive (not just the
        # title echoed back). Many publisher feeds carry a real teaser here.
        summary = ""
        desc_el = entry.find("description")
        if desc_el:
            raw = desc_el.get_text(" ", strip=True)
            if raw and raw.lower() != title.lower() and len(raw) > 30:
                summary = raw[:500]

        items.append(
            Item(
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=url,
                summary=summary,
                publish_date=date,
                categories=list(source.categories),
                tier=source.tier,
                partner_relevance=source.partner_relevance,
            )
        )
    return items
