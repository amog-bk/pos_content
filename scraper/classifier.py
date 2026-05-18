"""Score and bucket items by relevance to Partners selling business insurance.

Partners are 40-60 year old POSP/agents who mostly sell COMMERCIAL lines to
SMEs (fire, marine, engineering, liability, cyber, workmen comp, group health).
Reinsurance treaty pricing and global cat losses are interesting but rarely
actionable for them — they get downweighted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parsers.base import Item

# (regex, category, weight). Higher weight = more directly useful to Partners.
SIGNALS: list[tuple[str, str, int]] = [
    # Regulation & commissions — top priority.
    (r"\b(irdai|circular|notification|regulation|exposure draft|gazette)\b", "regulation", 5),
    (r"\b(commission|payout|remuneration|posp|broker|agent|bancassurance)\b", "distribution", 6),
    (r"\b(solvency|capital|fdi|composite licen[cs]e|open architecture)\b", "regulation", 4),
    (r"\b(kyc|aml|grievance|complaint|repudiation|ombudsman|bima bharosa)\b", "consumer", 5),

    # Commercial lines — Partners' bread and butter.
    (r"\b(fire insurance|burglary|industrial all risk|iar|property insurance)\b", "commercial_property", 5),
    (r"\b(marine|cargo|hull|transit)\b", "commercial_marine", 5),
    (r"\b(engineering|car|ear|machinery breakdown|contractors plant|cpm)\b", "commercial_engineering", 5),
    (r"\b(liability|professional indemnity|d&o|public liability|product liability|cgl)\b", "commercial_liability", 5),
    (r"\b(cyber insurance|ransomware|data breach|cyber cover)\b", "cyber", 5),
    (r"\b(workmen[ -]?comp\w*|workers? compensation|gpa|group personal accident|epli)\b", "employee_benefits", 5),
    (r"\b(group health|gmc|mediclaim|tpa|claims inflation)\b", "health_group", 4),

    # Claims, fraud, consumer experience.
    (r"\b(claim|claims ratio|loss ratio|combined ratio|repudiation|settlement)\b", "claims", 4),
    (r"\b(fraud|fake polic|mis-?selling|scam|ghost)\b", "fraud", 5),

    # Stats relevant to selling business insurance.
    (r"\b(premium growth|gwp|sme|msme|industry data|penetration|density)\b", "stats", 3),

    # Lower-priority noise.
    (r"\b(reinsurance|treaty|retrocession|catastrophe|nat[- ]?cat)\b", "reinsurance", 2),
    (r"\b(ipo|listing|share price|stock|q[1-4] results|quarterly)\b", "markets", 1),
]

NOISE = re.compile(
    r"\b(life insurance plan|term plan|ulip|endowment|child plan|retirement plan|"
    r"best.*plan|top 10|sponsored|advertorial|astrolog|horoscope)\b",
    re.IGNORECASE,
)


@dataclass
class ScoredItem:
    item: Item
    score: int
    tags: list[str]


def score(item: Item) -> ScoredItem:
    text = f"{item.title} {item.summary}".lower()
    if NOISE.search(text):
        return ScoredItem(item=item, score=-5, tags=["noise"])

    total = item.partner_relevance  # base from source config
    tags: list[str] = []
    for pattern, tag, weight in SIGNALS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            total += weight
            tags.append(tag)

    # Tier bonus: tier 1 sources start with a slight edge.
    total += {1: 2, 2: 1, 3: 0}.get(item.tier, 0)
    return ScoredItem(item=item, score=total, tags=tags or ["general"])


def rank(items: list[Item], min_score: int = 5) -> list[ScoredItem]:
    scored = [score(i) for i in items]
    scored = [s for s in scored if s.score >= min_score]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
