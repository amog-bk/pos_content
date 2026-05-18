"""Turn the top scored items into Partner-ready WhatsApp messages.

Voice rules come from pos-engagement-skill/SKILL.md:
  - Warm, simple, educational, relationship-led
  - 6-10 short lines, paragraphs of 1-2 lines
  - No jargon, no hype, no multiple emojis (only 🙏🏽 if any)
  - Test: "Would a 50-year-old Gujarati uncle who speaks limited English get this?"

This module DOES NOT use an LLM. It writes safe, template-driven drafts the
content team will review before sending. An LLM rewrite step can be bolted on
later if you want — but template-only keeps voice tight and predictable.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .classifier import ScoredItem
from .config import Config
from .fetcher import resolve_redirect

# Devanagari (Hindi) Unicode block — used to detect and strip bilingual titles.
DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]+")


def clean_title(title: str) -> str:
    """Trim Google News' trailing '..' truncation marker and surrounding
    whitespace. Doesn't restore the lost text but stops drafts from reading
    like cut-off thoughts."""
    t = title.strip()
    # GN uses ".." or "..." — trim either.
    t = re.sub(r"\s*\.{2,}\s*$", "", t)
    # Stray ellipsis char too.
    t = re.sub(r"\s*…\s*$", "", t)
    return t.strip()


def english_only_title(title: str) -> str:
    """IRDAI titles are often 'हिंदी शीर्षक / English Title'. Keep the English
    half for Partner WhatsApp drafts (the digest keeps the full bilingual form
    for the internal team)."""
    if not DEVANAGARI_RE.search(title):
        return title.strip()
    # Try common split markers, longest first.
    for sep in [" / ", "/", " | ", "|", " - ", " – "]:
        if sep in title:
            parts = [p.strip() for p in title.split(sep)]
            english = [p for p in parts if p and not DEVANAGARI_RE.search(p)]
            if english:
                return english[0]
    # No separator — strip Hindi runs and collapse whitespace.
    cleaned = DEVANAGARI_RE.sub(" ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" /-|")
    return cleaned or title.strip()


# Plain-English explainers per category. These are the "what it means for you"
# lines that translate well to Hindi/Gujarati/Kannada/Tamil.
CATEGORY_EXPLAINER = {
    "regulation": "This is an IRDAI update that may change how some policies are sold or renewed.",
    "distribution": "This change can affect how Partners earn or work with insurers, so it is worth knowing.",
    "consumer": "This is useful when guiding clients who have questions about claims or complaints.",
    "claims": "This helps you set the right expectations with your clients about claims.",
    "fraud": "Please share this with your clients so they can stay safe and not fall for fake offers.",
    "commercial_property": "This is helpful when you speak to shops, factories, or warehouses about fire and property covers.",
    "commercial_marine": "Keep this in mind when you talk to clients who move goods or run trading businesses.",
    "commercial_engineering": "This is useful for builders, contractors, and machinery-heavy businesses.",
    "commercial_liability": "This matters for clients in professional services or any business that deals with the public.",
    "cyber": "More small businesses are buying cyber cover now. This will help you start that conversation.",
    "employee_benefits": "Useful when you advise clients on covers for their workers and staff.",
    "health_group": "This will help you support clients who provide health cover to their employees.",
    "stats": "These numbers give you a clear picture of the market and help you in client conversations.",
    "reinsurance": "This is global context. It may affect pricing for some commercial policies over time.",
    "markets": "This is industry news. Good to know, even if it does not change your daily work.",
    "general": "Worth a quick read so you stay updated on what is happening in our industry.",
}

# Short, friendly hook lines per category.
CATEGORY_HOOK = {
    "regulation": "There is a new IRDAI update we want to share with you.",
    "distribution": "There is a change in our industry that affects Partners directly.",
    "consumer": "We came across something useful for your client conversations.",
    "claims": "We are sharing a small update on claims that can help you.",
    "fraud": "Please be aware of a new pattern we are seeing in the market.",
    "commercial_property": "Here is something useful for your clients with shops, factories, or warehouses.",
    "commercial_marine": "Here is a small update for clients in trading and goods movement.",
    "commercial_engineering": "Here is a useful note for clients in construction and machinery.",
    "commercial_liability": "Sharing a small update on liability covers for your business clients.",
    "cyber": "More businesses are asking about cyber insurance these days.",
    "employee_benefits": "Sharing a small update on covers for your clients' workers.",
    "health_group": "We have an update on group health insurance to share with you.",
    "stats": "We are sharing some numbers that may be useful in your client meetings.",
    "reinsurance": "A small update from the wider insurance world.",
    "markets": "A short market update from this week.",
    "general": "We came across this and thought it would be useful for you.",
}


def _primary_tag(s: ScoredItem) -> str:
    for tag in s.tags:
        if tag in CATEGORY_HOOK:
            return tag
    return "general"


def draft_message(s: ScoredItem, url: str | None = None) -> str:
    tag = _primary_tag(s)
    hook = CATEGORY_HOOK[tag]
    explainer = CATEGORY_EXPLAINER[tag]
    # Keep the title human — English-only, stripped of surrounding quotes
    # and trailing truncation markers.
    title = clean_title(english_only_title(s.item.title)).strip().strip("\"'")
    link = url or s.item.url
    return (
        "Namaste,\n"
        "\n"
        f"{hook}\n"
        "\n"
        f"{title}\n"
        "\n"
        f"{explainer}\n"
        "\n"
        "Please go through it when you have time.\n"
        "\n"
        f"Source: {s.item.source_name}\n"
        f"Link: {link}\n"
        "\n"
        "We are here to support you.\n"
        "Team BimaKavach"
    )


def select_top_messages(scored: list[ScoredItem], top_n: int = 5) -> list[ScoredItem]:
    """Pick top_n items, deduplicating by primary tag so we don't send 5
    commercial_property messages in the same week."""
    chosen: list[ScoredItem] = []
    seen_tags: set[str] = set()
    for s in scored:
        tag = _primary_tag(s)
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        chosen.append(s)
        if len(chosen) == top_n:
            break
    return chosen


def resolve_links_for(items: list[ScoredItem], user_agent: str) -> dict[str, str]:
    """Return {original_url: resolved_url} for items whose URL points at
    news.google.com. Resolution is best-effort; on failure the original is
    kept."""
    out: dict[str, str] = {}
    for s in items:
        url = s.item.url
        if "news.google.com" in url:
            out[url] = resolve_redirect(url, user_agent, timeout=10)
    return out


def write_messages(scored: list[ScoredItem], out_path: Path, week_label: str,
                   top_n: int = 5, config: Config | None = None,
                   resolved_links: dict[str, str] | None = None) -> list[ScoredItem]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# Partner WhatsApp Drafts — {week_label}")
    lines.append("")
    lines.append(f"_Drafts only — please review for voice and accuracy before sending. "
                 f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}._")
    lines.append("")
    lines.append("Each block below is one WhatsApp message. Send as-is, or "
                 "translate to Gujarati/Hindi/Kannada/Tamil for the relevant Partner groups.")
    lines.append("")

    chosen = select_top_messages(scored, top_n=top_n)
    if resolved_links is None:
        ua = config.user_agent if config else "Mozilla/5.0"
        resolved_links = resolve_links_for(chosen, ua)

    for i, s in enumerate(chosen, 1):
        link = resolved_links.get(s.item.url, s.item.url)
        lines.append(f"---")
        lines.append("")
        lines.append(f"## Message {i} — _{_primary_tag(s)}_ (score {s.score})")
        lines.append("")
        lines.append("```")
        lines.append(draft_message(s, url=link))
        lines.append("```")
        lines.append("")

    if not chosen:
        lines.append("_No items qualified this week. Consider lowering the classifier "
                     "min_score in scraper/main.py or enabling more sources._")
        lines.append("")

    out_path.write_text("\n".join(lines))
    return chosen
