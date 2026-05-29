"""Score and bucket items for the weekly BimaKavach industry briefing.

Audience: BimaKavach team members who track the whole Indian insurance
market (life + non-life + health + reinsurance). The briefing covers
M&A and deals, company results, regulatory and corporate-governance
actions, and premium/industry trends.

Each item gets a primary "section" tag aligned to the briefing structure:
  - deals       → Major Business & Market Deals
  - regulatory  → Regulatory Actions & Corporate Governance
  - trends      → Industry & Premium Trends
plus finer tags (m&a, results, governance, health, life, commercial, etc.)
kept for reference/filtering.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parsers.base import Item

# (regex, tag, weight). Higher weight = bigger story for the briefing.
SIGNALS: list[tuple[str, str, int]] = [
    # ---- Major business & market deals ----
    (r"\b(acquir\w+|acquisition|to buy|buyout|merger|amalgamat\w+|"
     r"stake (sale|buy|purchase)|sells? .* stake|divest\w*|takeover|"
     r"open offer|controlling stake)\b", "deals", 8),
    (r"\b(ipo|initial public offering|drhp|files? (for )?ipo|gets? listed|"
     r"lists? on|fund ?rais\w+|raises? (rs|₹|\$)|valuation|pre-?ipo|anchor investor)\b", "deals", 6),
    (r"\b(net profit|profit (jump|surg\w+|ris\w+|up|down|fall|decline)|"
     r"q[1-4] ?fy\d*|quarterly results|annual results|posts? .* profit|"
     r"bonus (to|payout|of)|policyholder bonus|new business premium|"
     r"\bape\b|\bvnb\b|embedded value)\b", "results", 5),
    (r"\b(expansion|new (branch\w*|sales units?|offices?)|enters? .* market|"
     r"partnership|tie-?up|joint venture|distribution pact)\b", "deals", 4),

    # ---- Regulatory & corporate governance ----
    (r"\b(irdai|regulator|circular|notification|regulation|exposure draft|gazette|master circular)\b", "regulatory", 6),
    (r"\b(governance|\bboard\b|ceo pay|executive (pay|compensation)|variable pay|"
     r"remuneration|\bkpi\b|key performance|expense of management|\beom\b)\b", "governance", 6),
    (r"\b(solvency|capital infusion|\bfdi\b|composite licen[cs]e|"
     r"\breit\b|\binvit\b|investment norm\w*|listing norm\w*)\b", "regulatory", 5),
    (r"\b(penalt\w+|fine[ds]?|show ?cause|crack ?down|withh(eld|olding)|"
     r"directive|warning|disgorg\w+|cancel\w* licen[cs]e)\b", "regulatory", 5),

    # ---- Industry & premium trends ----
    (r"\b(premium (growth|income|surg\w+|ris\w+)|gross written premium|gwp|gdpi|"
     r"year-?on-?year|yoy growth|retail health|group health|health premium)\b", "trends", 5),
    (r"\b(penetration|insurance density|combined ratio|loss ratio|claims ratio|"
     r"underwriting (profit|loss)|incurred claims)\b", "trends", 5),
    (r"\b(commission|intermediary|bancassurance|agency channel|distribution cost|"
     r"renewal business)\b", "trends", 4),
    (r"\b(price (cut|hike|ris\w+)|cheaper|discount\w*|tariff|repric\w+|premium (cut|hike))\b", "trends", 4),

    # ---- Claims / consumer / fraud (fold into trends) ----
    (r"\b(claim|repudiat\w+|settlement ratio|grievance|ombudsman|"
     r"consumer commission|consumer forum|consumer court)\b", "trends", 4),
    (r"\b(fraud|fake polic\w+|mis-?selling|scam|ghost polic\w+)\b", "trends", 5),

    # ---- Lines of business (supporting context) ----
    (r"\b(cyber insurance|fire insurance|marine insurance|liability insurance|"
     r"engineering insurance|workmen comp\w*|d&o|directors and officers|"
     r"professional indemnity|crop insurance|motor insurance)\b", "trends", 3),
    (r"\b(life insurance|term (plan|insurance)|ulip|annuit\w+|pension plan|"
     r"endowment|par product|non-?par)\b", "trends", 3),
]

# Major Indian insurers / groups — a small recognition boost so company-
# specific stories rank above generic explainers.
PLAYERS = re.compile(
    r"\b(lic|hdfc life|hdfc ergo|sbi (life|general)|icici (pru|prudential|lombard)|"
    r"max life|tata aia|bajaj allianz|star health|new india|gic re|go ?digit|"
    r"niva bupa|kotak (life|general)|aditya birla (health|sun life)|bharti (axa|life)|"
    r"prudential|reliance (general|nippon)|future generali|cholamandalam|"
    r"royal sundaram|liberty general|acko|navi|care health|manipal cigna|"
    r"indusind|nippon life|zurich kotak)\b",
    re.IGNORECASE,
)

# Spam / non-news only (life-insurance product news is now allowed).
# We also filter US-political headlines that mention "insurance" tangentially
# (e.g. SPLC / Obamacare / Senate hearings) — these leaked into Trends in
# W22. We stay narrow to US-political signatures; Indian-political coverage
# of insurance (BJP, Modi government, etc.) remains in scope and must NOT be
# matched here.
NOISE = re.compile(
    r"\b(best .{0,30}plan to buy|top \d+ .{0,30}plans?|"
    r"sponsored|advertorial|astrolog\w+|horoscope|"
    r"share price|stock price|mutual fund nav|ipo gmp|"
    r"short description|"
    # --- US politics noise ---
    r"splc|kkk|obamacare|"
    r"house republicans|house democrats|house hearing|"
    r"gop|dems|"
    r"senator [a-z]+(?: [a-z]+)? \(?[rd]-|"
    r"biden administration|trump administration)\b",
    re.IGNORECASE,
)

PLACEHOLDER_TITLES = {
    "circular",
    "परिपत्र",
    "परिपत्र / circular",
    "short description",
    "news",
    "press release",
    "notification",
}

# Maps each tag to its briefing section (used by briefing.py and the digest).
TAG_SECTION = {
    "deals": "deals",
    "results": "deals",
    "regulatory": "regulatory",
    "governance": "regulatory",
    "trends": "trends",
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
            if tag not in tags:
                tags.append(tag)

    if PLAYERS.search(text):
        total += 2
        tags.append("player")

    total += {1: 2, 2: 1, 3: 0}.get(item.tier, 0)
    return ScoredItem(item=item, score=total, tags=tags or ["general"])


def rank(items: list[Item], min_score: int = 6) -> list[ScoredItem]:
    scored = [score(i) for i in items]
    scored = [s for s in scored if s.score >= min_score]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
