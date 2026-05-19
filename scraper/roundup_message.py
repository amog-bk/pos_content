"""Single consolidated weekly roundup writer.

Replaces the per-item WhatsApp drafts with ONE message of <= 300 words,
broken into sections (Regulation, Claims & Fraud, Property/Fire, Marine,
Engineering, Liability, Cyber, Health & Group).

Voice follows pos-engagement-skill/SKILL.md:
  - Namaste opening
  - Simple, warm, educational
  - Short sentences, no jargon, no hype
  - Warm closing

This module is template-driven (no LLM). Each section is a 2-line block:
  <Section heading>
  <Cleaned headline>. <One-line "why this matters" explainer>.

If a section has nothing in the last 7 days, we extend the window for that
section to 45 days. If still nothing, the section is skipped.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from .classifier import ScoredItem
from .whatsapp import clean_title, english_only_title

log = logging.getLogger(__name__)

RECENT_DAYS = 7
EXTENDED_DAYS = 45

# Section order in the final roundup. Each maps to one or more classifier tags.
SECTIONS: list[tuple[str, str, list[str]]] = [
    # (section_id, display_heading, classifier_tags_in_priority_order)
    ("regulation",  "Regulation",            ["regulation", "distribution"]),
    ("claims_fraud", "Claims & Fraud",        ["fraud", "consumer", "claims"]),
    ("property",    "Property & Fire",       ["commercial_property"]),
    ("marine",      "Marine",                ["commercial_marine"]),
    ("engineering", "Engineering",           ["commercial_engineering"]),
    ("liability",   "Liability",             ["commercial_liability"]),
    ("cyber",       "Cyber",                 ["cyber"]),
    ("health",      "Health & Group",        ["health_group", "employee_benefits"]),
]

SECTION_EXPLAINER = {
    "regulation":   "This may affect how you sell or renew some policies.",
    "claims_fraud": "Useful when guiding your clients on claims and complaints.",
    "property":     "Helpful for clients with shops, factories, or warehouses.",
    "marine":       "Relevant for clients who trade or move goods.",
    "engineering":  "Useful for builders, contractors, and machinery-heavy clients.",
    "liability":    "Matters for clients in professional services or any business that deals with the public.",
    "cyber":        "More small businesses are buying cyber cover now.",
    "health":       "Useful when your clients offer cover to their workers and staff.",
}


@dataclass
class SectionPick:
    section_id: str
    heading: str
    items: list[ScoredItem]  # all candidates for that section (used for sheet "items" column)
    headline_item: ScoredItem | None  # the one chosen for the message
    extended: bool  # True if we had to extend the recency window


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date_within(item, days: int) -> bool:
    if not item.publish_date:
        return False
    dt = item.publish_date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= _now() - timedelta(days=days)


def _normalize_for_dedup(title: str) -> str:
    t = clean_title(english_only_title(title)).lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Trim to first 12 words so near-duplicates with extra suffixes collapse.
    return " ".join(t.split()[:12])


def dedup(scored: list[ScoredItem]) -> list[ScoredItem]:
    """Collapse near-duplicate titles, keeping highest score."""
    by_key: dict[str, ScoredItem] = {}
    for s in scored:
        key = _normalize_for_dedup(s.item.title)
        if not key:
            continue
        if key not in by_key or by_key[key].score < s.score:
            by_key[key] = s
    return sorted(by_key.values(), key=lambda s: s.score, reverse=True)


def _candidates_for_section(scored: list[ScoredItem], tags: list[str],
                            days: int) -> list[ScoredItem]:
    out: list[ScoredItem] = []
    for s in scored:
        if not _date_within(s.item, days):
            continue
        if any(tag in s.tags for tag in tags):
            out.append(s)
    return out


def pick_sections(scored: list[ScoredItem]) -> list[SectionPick]:
    """For each section, pick the items that should appear in this week's
    roundup. Strict 7-day window per section; fallback to 45 days for that
    section if nothing fresh."""
    used_urls: set[str] = set()
    picks: list[SectionPick] = []

    for section_id, heading, tags in SECTIONS:
        items = _candidates_for_section(scored, tags, RECENT_DAYS)
        extended = False
        if not items:
            items = _candidates_for_section(scored, tags, EXTENDED_DAYS)
            extended = bool(items)

        # Don't reuse an item across sections (e.g. a story tagged both
        # cyber and regulation should appear in one place only).
        items = [s for s in items if s.item.url not in used_urls]

        # Pick the single highest-score item as the section headline; keep
        # the top 5 candidates for the sheet's "items" column.
        items = items[:5]
        headline = items[0] if items else None
        if headline:
            used_urls.add(headline.item.url)

        picks.append(SectionPick(
            section_id=section_id,
            heading=heading,
            items=items,
            headline_item=headline,
            extended=extended,
        ))
    return picks


# ---------------------------------------------------------------------------
# Top-N picks for the Full Roundup (independent of section bucketing)
# ---------------------------------------------------------------------------

# Maps classifier tag -> roundup section_id (for the "what this means for you"
# line in each piece block).
TAG_TO_SECTION = {
    "regulation":            "regulation",
    "distribution":          "regulation",
    "fraud":                 "claims_fraud",
    "consumer":              "claims_fraud",
    "claims":                "claims_fraud",
    "commercial_property":   "property",
    "commercial_marine":     "marine",
    "commercial_engineering": "engineering",
    "commercial_liability":  "liability",
    "cyber":                 "cyber",
    "health_group":          "health",
    "employee_benefits":     "health",
}

# One short Partner-voice line per section, following the POS Engagement Skill
# (simple words, no jargon, no hype, max ~12-15 words).
PIECE_EXPLAINER = {
    "regulation":   "Worth knowing if you sell or renew policies this could affect.",
    "claims_fraud": "Useful when you guide your clients through claims or complaints.",
    "property":     "Helpful for clients with shops, factories, or warehouses.",
    "marine":       "Relevant for clients who trade or move goods.",
    "engineering":  "Useful for clients in construction or with machinery-heavy work.",
    "liability":    "Matters for clients in professional services or any client-facing business.",
    "cyber":        "A good moment to bring up cyber cover with your business clients.",
    "health":       "Useful when your clients offer health cover to their staff.",
    "general":      "Worth a quick read to stay updated on our industry.",
}


def _section_for_item(s: ScoredItem) -> str:
    for tag in s.tags:
        if tag in TAG_TO_SECTION:
            return TAG_TO_SECTION[tag]
    return "general"


def pick_top_for_message(
    scored: list[ScoredItem],
    max_n: int = 5,
    min_n: int = 3,
    high_threshold: int = 10,
    recent_days: int = RECENT_DAYS,
    extended_days: int = EXTENDED_DAYS,
) -> list[ScoredItem]:
    """Pure top-score selection for the Full Roundup column.

    Strategy:
      1. Prefer items from the last `recent_days` with score >= high_threshold.
         If 3+ qualify, return up to `max_n` of them.
      2. Otherwise, take items from the last `recent_days` (any score) — up to max_n.
      3. If still <3, fall back to the extended window (up to `extended_days`).
      4. As a last resort, return the top min_n by score regardless of date.
    """
    recent = [s for s in scored if _date_within(s.item, recent_days)]
    recent_high = [s for s in recent if s.score >= high_threshold]
    if len(recent_high) >= min_n:
        return recent_high[:max_n]
    if len(recent) >= min_n:
        return recent[:max_n]
    extended = [s for s in scored if _date_within(s.item, extended_days)]
    if len(extended) >= min_n:
        return extended[:max_n]
    return scored[:min_n]


def _clean_summary(text: str, max_words: int = 35) -> str:
    """Strip HTML, collapse whitespace, drop trailing 'Read more', truncate."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "lxml")
    plain = soup.get_text(" ", strip=True)
    plain = re.sub(r"\s+", " ", plain).strip()
    # Drop common publisher tails.
    plain = re.sub(r"(read more|continue reading)\.?\s*$", "", plain, flags=re.IGNORECASE).strip()
    words = plain.split()
    if len(words) > max_words:
        plain = " ".join(words[:max_words]).rstrip(",;:") + "..."
    return plain


def _piece_block(rank_n: int, s: ScoredItem, link: str) -> str:
    title = clean_title(english_only_title(s.item.title))
    section = _section_for_item(s)
    explainer = PIECE_EXPLAINER[section]
    summary = _clean_summary(s.item.summary, max_words=32)

    lines = [f"{rank_n}. {title}"]
    if summary:
        lines.append(summary)
    lines.append(explainer)
    lines.append(f"Source: {s.item.source_name} — {link}")
    return "\n".join(lines)


def _word_count_prose(text: str) -> int:
    """Word count that ignores URLs (URLs aren't 'words' in editorial counts)."""
    no_urls = re.sub(r"https?://\S+", "", text)
    return len(re.findall(r"\b\w+\b", no_urls))


def render_roundup(
    scored: list[ScoredItem],
    resolved_links: dict[str, str] | None = None,
    max_words: int = 300,
    max_n: int = 5,
    min_n: int = 3,
    high_threshold: int = 10,
) -> tuple[str, list[ScoredItem]]:
    """Build the Full Roundup column text. Returns (text, items_used)."""
    intro = ("Namaste,\n\nHere is this week's roundup of business insurance "
             "updates worth your attention.")
    closing = "We are here to support you.\nTeam BimaKavach"

    picks = pick_top_for_message(scored, max_n=max_n, min_n=min_n,
                                  high_threshold=high_threshold)
    if not picks:
        return (f"{intro}\n\nNo major business insurance news this week worth "
                f"flagging.\n\n{closing}"), []

    n = len(picks)
    while n >= 1:
        blocks = []
        for i, s in enumerate(picks[:n], 1):
            link = (resolved_links or {}).get(s.item.url, s.item.url)
            blocks.append(_piece_block(i, s, link))
        full = f"{intro}\n\n" + "\n\n".join(blocks) + f"\n\n{closing}"
        if _word_count_prose(full) <= max_words or n == max(min_n, 1):
            return full, picks[:n]
        n -= 1
    return f"{intro}\n\n{closing}", []


def write_roundup_file(
    picks: list[SectionPick],
    scored: list[ScoredItem],
    out_path: Path,
    week_label: str,
    resolved_links: dict[str, str] | None = None,
) -> tuple[str, list[ScoredItem]]:
    """Writes the Partner roundup markdown file. Returns (roundup_text,
    items_used_in_message)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text, items_used = render_roundup(scored, resolved_links=resolved_links)
    wc = _word_count_prose(text)

    lines = [
        f"# Weekly Roundup — {week_label}",
        "",
        f"_Generated {_now().strftime('%Y-%m-%d %H:%M UTC')} · {wc} words._",
        "",
        "Send to Partner WhatsApp groups, or translate to "
        "Gujarati/Hindi/Kannada/Tamil for the relevant Partner groups.",
        "",
        "## Full Roundup",
        "",
        "```",
        text,
        "```",
        "",
        "## Items by section (for reference)",
        "",
    ]

    for p in picks:
        if not p.items:
            continue
        suffix = " _(extended window)_" if p.extended else ""
        lines.append(f"### {p.heading}{suffix}")
        lines.append("")
        for s in p.items:
            date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else "—"
            link = (resolved_links or {}).get(s.item.url, s.item.url)
            lines.append(f"- [{clean_title(english_only_title(s.item.title))}]({link})  ")
            lines.append(f"  _{s.item.source_name}_ · {date} · score {s.score}")
        lines.append("")

    out_path.write_text("\n".join(lines))
    return text, items_used
