from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Source:
    id: str
    name: str
    url: str
    parser: str
    tier: int
    enabled: bool
    partner_relevance: int
    categories: list[str] = field(default_factory=list)


@dataclass
class Config:
    user_agent: str
    request_timeout_seconds: int
    max_items_per_source: int
    lookback_days: int
    sources: list[Source]


def load_config(path: str | Path = None) -> Config:
    path = Path(path) if path else Path(__file__).parent / "sources.yml"
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    d = raw.get("defaults", {})
    sources = [Source(**s) for s in raw.get("sources", [])]
    return Config(
        user_agent=d.get("user_agent", "Mozilla/5.0"),
        request_timeout_seconds=int(d.get("request_timeout_seconds", 20)),
        max_items_per_source=int(d.get("max_items_per_source", 15)),
        lookback_days=int(d.get("lookback_days", 7)),
        sources=sources,
    )
