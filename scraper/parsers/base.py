from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    source_id: str
    source_name: str
    title: str
    url: str
    summary: str = ""
    publish_date: datetime | None = None
    categories: list[str] = field(default_factory=list)
    tier: int = 3
    partner_relevance: int = 1
    keywords: list[str] = field(default_factory=list)
