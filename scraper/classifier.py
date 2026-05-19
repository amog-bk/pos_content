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
    # Distribution: specifically about how Partners get paid or who can sell.
    # Avoids matching unrelated "consumer commission", "competition commission",
    # "judicial commission" etc.
    (r"\b(commission cap|commission cut|commission hike|commission revision|"
     r"commission structure|broker remuneration|agent (payout|commission|network)|"
     r"bancassurance|posp|insurance broker|insurance agent)\b", "distribution", 6),
    (r"\b(solvency|capital|fdi|composite licen[cs]e|open architecture)\b", "regulation", 4),
    (r"\b(kyc|aml|grievance|complaint|repudiat\w+|ombudsman|bima bharosa|"
     r"consumer commission|consumer forum|consumer court)\b", "consumer", 5),

    # Commercial lines — Partners' bread and butter.
    (r"\b(fire insurance|fire claims?|burglary|industrial all risk|iar|property insurance|factory fire|warehouse fire)\b", "commercial_property", 5),
    (r"\b(marine insurance|marine cargo|cargo insurance|hull insurance|cargo claim|transit insurance)\b", "commercial_marine", 5),
    (r"\b(engineering insurance|car policy|car insurance.{0,30}contractor|ear policy|machinery breakdown|contractors plant|cpm|construction insurance)\b", "commercial_engineering", 5),
    (r"\b(liability insurance|professional indemnity|directors and officers|d&o|public liability|product liability|cgl|errors and omissions)\b", "commercial_liability", 5),
    (r"\b(cyber insurance|ransomware|data breach|cyber cover|dpdp)\b", "cyber", 5),
    (r"\b(workmen[ -]?comp\w*|workers? compensation|gpa|group personal accident|epli)\b", "employee_benefits", 5),
    (r"\b(group health|gmc|group mediclaim|mediclaim|tpa|claims inflation|employee health)\b", "health_group", 4),

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
    r"best.*plan|top 10|sponsored|advertorial|astrolog|horoscope|"
    r"share price|stock price|mutual fund nav|ipo gmp|"
    r"short description)\b",
    re.IGNORECASE,
)

# Whole-title strings that are obvious placeholders / template leakage.
PLACEHOLDER_TITLES = {
    "circular",
    "परिपत्र",
    "परिपत्र / circular",
    "short description",
    "news",
    "press release",
    "notification",
}


@dataclass
class ScoredItem:
    item: Item
    score: int
    tags: list[str]


def score(item: Item) -> ScoredItem:
    text = f"{item.title} {item.summary}".lower()
    if item.title.strip().lower() in PLACEHOLDER_TITLES:
        return ScoredItem(item=item, score=-5, tags=["noise"])
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
