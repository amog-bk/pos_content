"""Internal long-form digest writer.

Produces a single markdown file listing every scored item, grouped by tag —
the full set the team can scan behind the curated briefing.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .classifier import ScoredItem

CATEGORY_ORDER = [
    "deals",
    "results",
    "people",
    "insurtech",
    "regulatory",
    "governance",
    "trends",
    "data",
    "player",
    "general",
]


def _bucket(scored: list[ScoredItem]) -> dict[str, list[ScoredItem]]:
    buckets: dict[str, list[ScoredItem]] = {}
    for s in scored:
        primary = next((t for t in CATEGORY_ORDER if t in s.tags), "general")
        buckets.setdefault(primary, []).append(s)
    return buckets


def write_digest(
    scored: list[ScoredItem],
    fetch_errors: list[tuple[str, str]],
    out_path: Path,
    week_label: str,
    chronic: list[tuple[str, int]] | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# India Business Insurance — Weekly Roundup ({week_label})")
    lines.append("")
    lines.append(f"_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_  ")
    lines.append(f"_Total items after filtering: {len(scored)}_  ")
    lines.append("")
    lines.append("This is the internal digest. Pick 3–5 items below and hand them to "
                 "`whatsapp.py` (or the content team) to turn into Partner messages.")
    lines.append("")

    buckets = _bucket(scored)
    for cat in CATEGORY_ORDER:
        items = buckets.get(cat)
        if not items:
            continue
        lines.append(f"## {cat.replace('_', ' ').title()}")
        lines.append("")
        for s in items[:10]:
            date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else "—"
            lines.append(f"- **[{s.item.title}]({s.item.url})**")
            lines.append(f"  · _{s.item.source_name}_ · {date} · score {s.score} · tags: {', '.join(s.tags)}")
            if s.item.summary:
                lines.append(f"  · {s.item.summary[:280]}")
        lines.append("")

    if chronic:
        lines.append("## ⚠ Chronic feed failures (action needed)")
        lines.append("")
        lines.append("These sources have failed every weekly run for 3+ weeks. "
                     "Fix the URL, swap to a backup feed, or disable them in "
                     "sources.yml — their coverage is currently lost.")
        lines.append("")
        for src, n in chronic:
            lines.append(f"- `{src}` — {n} consecutive weeks down")
        lines.append("")

    if fetch_errors:
        chronic_ids = {src for src, _ in (chronic or [])}
        lines.append("## Sources that failed this week")
        lines.append("")
        for src, err in fetch_errors:
            marker = " ⚠ chronic" if src in chronic_ids else ""
            lines.append(f"- `{src}` — {err}{marker}")
        lines.append("")

    out_path.write_text("\n".join(lines))
