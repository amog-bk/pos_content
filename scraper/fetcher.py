from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    ok: bool
    error: str | None = None


def resolve_redirect(url: str, user_agent: str, timeout: int = 10) -> str:
    """Follow redirects and return the final URL. Used to unwrap Google News
    RSS redirect URLs (news.google.com/rss/articles/CBMi...) into the actual
    publication URL so the roundup doesn't carry 500-char base64 links.

    Returns the original URL on failure or if redirection stays on
    news.google.com (which can happen when GN serves a JS interstitial)."""
    headers = {"User-Agent": user_agent}
    try:
        r = requests.get(url, headers=headers, timeout=timeout,
                         allow_redirects=True, stream=True)
        final = r.url
        r.close()
        if final and "news.google.com" not in final:
            return final
    except requests.RequestException as e:
        log.debug("resolve_redirect failed for %s: %s", url, e)
    return url


def fetch_og_summary(url: str, user_agent: str, timeout: int = 10) -> str:
    """Fetch an article page and extract a short description from its meta
    tags (og:description, name=description, twitter:description). Returns
    empty string on failure. Used to enrich top roundup items with real
    article context — Google News RSS descriptions are unusable (they list
    related articles instead of summarising the story)."""
    if not url or "news.google.com" in url:
        return ""
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if not r.ok or "html" not in r.headers.get("Content-Type", "").lower():
            return ""
        soup = BeautifulSoup(r.text, "lxml")
        for kwargs in (
            {"property": "og:description"},
            {"name": "description"},
            {"name": "twitter:description"},
        ):
            el = soup.find("meta", attrs=kwargs)
            if el and el.get("content"):
                return el["content"].strip()
    except requests.RequestException as e:
        log.debug("og fetch failed for %s: %s", url, e)
    return ""


def fetch(url: str, user_agent: str, timeout: int = 20, retries: int = 2) -> FetchResult:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    last_err: str | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            return FetchResult(url=url, status=r.status_code, text=r.text, ok=r.ok)
        except requests.RequestException as e:
            last_err = str(e)
            log.warning("fetch failed (attempt %d): %s — %s", attempt + 1, url, e)
            time.sleep(2 ** attempt)
    return FetchResult(url=url, status=0, text="", ok=False, error=last_err)
