from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    ok: bool
    error: str | None = None


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
