"""Weekly industry-briefing material builder.

This does NOT write the final briefing prose — that is written in-session by
Claude (the assistant), in BimaKavach voice, from the ranked material this
module produces. Here we:

  1. Deduplicate near-identical headlines.
  2. Apply a recency window (7 days, 21-day fallback per section).
  3. Bucket items into the three briefing sections:
       - Major Business & Market Deals
       - Regulatory Actions & Corporate Governance
       - Industry & Premium Trends
  4. Pick a small "Headline" set (top stories overall) for the opener.
  5. Write a markdown material file the assistant reads on Friday.

The Google-News-URL resolution and og:summary enrichment happen in main.py
before the material is written, so links and context are clean.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classifier import ScoredItem, TAG_SECTION
from .whatsapp import clean_title, english_only_title

log = logging.getLogger(__name__)

RECENT_DAYS = 7
EXTENDED_DAYS = 21

# (section_id, display heading). Order = order in the briefing.
SECTIONS: list[tuple[str, str]] = [
    ("deals",      "Major Business & Market Deals"),
    ("regulatory", "Regulatory Actions & Corporate Governance"),
    ("trends",     "Industry & Premium Trends"),
]

HEADLINE_COUNT = 3          # top stories for the "Insurance this week" opener
MAX_ITEMS_PER_SECTION = 6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _date_within(item, days: int) -> bool:
    if not item.publish_date:
        return False
    dt = item.publish_date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= _now() - timedelta(days=days)


# Words to ignore when building a dedup signature — articles, prepositions,
# auxiliaries, and a few connectives that show up in headlines without carrying
# story-identifying meaning.
_DEDUP_STOPWORDS = frozenset({
    "a", "an", "and", "the", "of", "to", "in", "on", "at", "for", "with",
    "as", "by", "is", "are", "was", "were", "be", "been", "being", "that",
    "this", "it", "its", "from", "or", "but", "if", "after", "before",
    "has", "have", "had", "will", "would", "could", "says", "said", "may",
    "can", "vs", "over", "into", "about", "between",
})

# Tail patterns Google News & some direct feeds append to headlines, e.g.
# "..., Reuters" or " | Mint". Stripping these before signature helps the
# same story from different aggregators collapse.
_PUBLISHER_TAIL_RE = re.compile(r"\s*[|,—–-]\s*[A-Za-z][A-Za-z0-9 .&'’]{1,40}$")

# Number of content words in the alphabetical-top-N signature (stage 1).
_DEDUP_SIGNATURE_LEN = 6

# Stage-2 content-word overlap thresholds. Two items collapse if they share
# at least _DEDUP_OVERLAP_MIN content words AND the overlap covers at least
# _DEDUP_OVERLAP_RATIO of the smaller item's content-word set. These values
# were tuned against the W22 corpus so the LIC stake-sale and IRDAI
# exec-pay variants collapse without over-collapsing distinct stake-sale
# stories like Coal India OFS or LIC bonus-dividend explainers.
_DEDUP_OVERLAP_MIN = 4
_DEDUP_OVERLAP_RATIO = 0.6


def _content_words(title: str) -> tuple[list[str], set[str]]:
    """Return (cleaned content-word list, set) for a title — used by both
    the alphabetical-top-N signature and the overlap fallback."""
    t = clean_title(english_only_title(title))
    # Strip publisher tail (", Reuters" / " | Mint" / " - The Economic Times").
    # Apply twice to handle nested suffixes ("..., source - publisher").
    for _ in range(2):
        new = _PUBLISHER_TAIL_RE.sub("", t)
        if new == t:
            break
        t = new
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    words = [w for w in t.split() if w and w not in _DEDUP_STOPWORDS]
    return words, set(words)


def _normalize_for_dedup(title: str) -> str:
    """Build the primary content-word signature: lowercase, strip punctuation
    and publisher-tail, drop English stopwords, take the top-6 remaining words
    sorted alphabetically. Two items with the same signature describe the same
    story when word order/filler differs but core vocabulary matches."""
    words, _ = _content_words(title)
    if not words:
        return ""
    return " ".join(sorted(words)[:_DEDUP_SIGNATURE_LEN])


def dedup(scored: list[ScoredItem]) -> list[ScoredItem]:
    """Two-stage near-duplicate collapse.

    Stage 1 (alphabetical-top-N signature): collapses item pairs whose top-6
    alphabetical content words match exactly. This catches the easy cases
    (Bloomberg + ET running near-identical "India to prepare LIC stake sale"
    headlines).

    Stage 2 (content-word overlap): for items that survived stage 1, collapse
    against any already-kept item that shares >= 4 content words AND covers
    >= 60% of the smaller item's content vocabulary. This catches the harder
    cases where wording diverges but the story is the same — e.g. the three
    IRDAI executive-pay variants in W22 used "compensation/pay" + different
    framing verbs ("tightens" / "links to customer metrics" / "elimination of
    unfair practices") and so produced different stage-1 signatures, yet
    they're clearly the same story.

    Coal India OFS shares only "stake" + "sale" + "india" with LIC stake-sale
    items — below the threshold — so it stays distinct. Niva Bupa, Delhi
    fraud, FDI also pass through untouched."""
    # Stage 1: alphabetical signature.
    by_key: dict[str, ScoredItem] = {}
    for s in scored:
        key = _normalize_for_dedup(s.item.title)
        if not key:
            continue
        if key not in by_key or by_key[key].score < s.score:
            by_key[key] = s
    stage1 = sorted(by_key.values(), key=lambda s: s.score, reverse=True)

    # Stage 2: content-word overlap against kept items (greedy, highest-scoring
    # first). Items with very short content lists (< 5 words) skip overlap to
    # avoid noisy short-headline collisions.
    kept: list[ScoredItem] = []
    kept_sets: list[set[str]] = []
    for s in stage1:
        _, cw = _content_words(s.item.title)
        if len(cw) < 5:
            kept.append(s)
            kept_sets.append(cw)
            continue
        collapsed = False
        for ks in kept_sets:
            if len(ks) < 5:
                continue
            overlap = len(cw & ks)
            smaller = min(len(cw), len(ks)) or 1
            if overlap >= _DEDUP_OVERLAP_MIN and overlap / smaller >= _DEDUP_OVERLAP_RATIO:
                collapsed = True
                log.debug(
                    "dedup stage-2: collapsed %r into existing item (overlap=%d, ratio=%.0f%%)",
                    s.item.title, overlap, 100 * overlap / smaller,
                )
                break
        if not collapsed:
            kept.append(s)
            kept_sets.append(cw)
    return kept


def _section_of(s: ScoredItem) -> str:
    for tag in s.tags:
        if tag in TAG_SECTION:
            return TAG_SECTION[tag]
    return "trends"  # default bucket for anything insurance-relevant


@dataclass
class SectionBucket:
    section_id: str
    heading: str
    items: list[ScoredItem] = field(default_factory=list)
    extended: bool = False


def build_sections(scored: list[ScoredItem]) -> tuple[list[SectionBucket], list[ScoredItem]]:
    """Returns (section buckets, headline picks).

    Each item lands in exactly one section (its primary). Within a section we
    keep the top MAX_ITEMS_PER_SECTION by score from the last RECENT_DAYS,
    falling back to EXTENDED_DAYS if nothing fresh.
    """
    # Assign each item to one section.
    by_section: dict[str, list[ScoredItem]] = {sid: [] for sid, _ in SECTIONS}
    for s in scored:
        by_section[_section_of(s)].append(s)

    buckets: list[SectionBucket] = []
    for sid, heading in SECTIONS:
        pool = by_section[sid]
        recent = [s for s in pool if _date_within(s.item, RECENT_DAYS)]
        extended = False
        chosen = recent
        if not chosen:
            chosen = [s for s in pool if _date_within(s.item, EXTENDED_DAYS)]
            extended = bool(chosen)
        chosen = sorted(chosen, key=lambda s: s.score, reverse=True)[:MAX_ITEMS_PER_SECTION]
        buckets.append(SectionBucket(section_id=sid, heading=heading,
                                     items=chosen, extended=extended))

    # Headline set: the highest-scoring recent items across all sections.
    recent_all = [s for s in scored if _date_within(s.item, RECENT_DAYS)]
    if len(recent_all) < HEADLINE_COUNT:
        recent_all = [s for s in scored if _date_within(s.item, EXTENDED_DAYS)]
    headlines = sorted(recent_all, key=lambda s: s.score, reverse=True)[:HEADLINE_COUNT]
    return buckets, headlines


def _fmt_item(s: ScoredItem, resolved_links: dict[str, str] | None) -> list[str]:
    url = (resolved_links or {}).get(s.item.url, s.item.url)
    date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else "—"
    title = clean_title(english_only_title(s.item.title))
    lines = [f"- **{title}**  ", f"  _{s.item.source_name}_ · {date} · score {s.score}"]
    if s.item.summary:
        lines.append(f"  {s.item.summary.strip()}")
    lines.append(f"  {url}")
    return lines


def write_material_file(
    buckets: list[SectionBucket],
    headlines: list[ScoredItem],
    out_path: Path,
    week_label: str,
    resolved_links: dict[str, str] | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# Industry Briefing Material — {week_label}",
        "",
        f"_Generated {_now().strftime('%Y-%m-%d %H:%M UTC')}. Raw ranked material._",
        "",
        "This is the input for the Friday briefing. The final briefing is "
        "written in-session in BimaKavach voice from the stories below.",
        "",
        "## Headline candidates (top stories this week)",
        "",
    ]
    for s in headlines:
        lines += _fmt_item(s, resolved_links)
    lines.append("")

    for b in buckets:
        suffix = " _(extended window — nothing in last 7 days)_" if b.extended else ""
        lines.append(f"## {b.heading}{suffix}")
        lines.append("")
        if not b.items:
            lines.append("_No items this week._")
            lines.append("")
            continue
        for s in b.items:
            lines += _fmt_item(s, resolved_links)
        lines.append("")

    out_path.write_text("\n".join(lines))
