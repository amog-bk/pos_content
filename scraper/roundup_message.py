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
# Roundup message text
# ---------------------------------------------------------------------------

def _section_block(pick: SectionPick) -> str | None:
    if not pick.headline_item:
        return None
    title = clean_title(english_only_title(pick.headline_item.item.title))
    explainer = SECTION_EXPLAINER.get(pick.section_id, "")
    return f"{pick.heading}\n{title}. {explainer}".rstrip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def render_roundup(picks: list[SectionPick], week_label: str,
                   max_words: int = 300) -> str:
    """Build the consolidated message. Drops the lowest-priority sections if
    we go over the word budget (sections are ordered by priority in SECTIONS).
    """
    intro = "Namaste,\n\nHere is this week's update on what is happening in business insurance in India."
    closing = "We are here to support you.\nTeam BimaKavach"

    blocks = [b for b in (_section_block(p) for p in picks) if b]

    while True:
        body = "\n\n".join(blocks)
        full = f"{intro}\n\n{body}\n\n{closing}" if blocks else f"{intro}\n\nNo major business insurance news this week worth flagging.\n\n{closing}"
        if _word_count(full) <= max_words or not blocks:
            return full
        # Over budget: drop the lowest-priority section that has content.
        blocks.pop()


def write_roundup_file(picks: list[SectionPick], out_path: Path, week_label: str) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = render_roundup(picks, week_label)
    wc = _word_count(text)

    lines = [
        f"# Weekly Roundup — {week_label}",
        "",
        f"_Generated {_now().strftime('%Y-%m-%d %H:%M UTC')} · {wc} words._",
        "",
        "Send to Partner WhatsApp groups, or translate to "
        "Gujarati/Hindi/Kannada/Tamil for the relevant Partner groups.",
        "",
        "```",
        text,
        "```",
        "",
        "## Items used",
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
            lines.append(f"- [{clean_title(english_only_title(s.item.title))}]({s.item.url})  ")
            lines.append(f"  _{s.item.source_name}_ · {date} · score {s.score}")
        lines.append("")

    out_path.write_text("\n".join(lines))
    return text
