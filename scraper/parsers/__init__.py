from __future__ import annotations

from . import generic_html, google_news_rss, irdai_listing

PARSERS = {
    "generic_html": generic_html.parse,
    "irdai_listing": irdai_listing.parse,
    "google_news_rss": google_news_rss.parse,
}


def get_parser(name: str):
    if name not in PARSERS:
        raise KeyError(f"Unknown parser: {name}")
    return PARSERS[name]
