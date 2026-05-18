"""Weekly scrape entry point.

Run:  python -m scraper.main [--week 2026-W20] [--out roundups]

The script:
  1. Loads sources.yml.
  2. Fetches each enabled source.
  3. Parses items, scores them for Partner relevance.
  4. Writes:
       roundups/<week>/digest.md          — internal long-form review
       roundups/<week>/partner-messages.md — top 5 WhatsApp drafts
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .classifier import rank
from .config import load_config
from .fetcher import fetch
from .parsers import get_parser
from .parsers.base import Item
from .roundup import write_digest
from .whatsapp import write_messages

log = logging.getLogger("scraper")


def week_label(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def run(week: str, out_root: Path, min_score: int) -> int:
    cfg = load_config()
    all_items: list[Item] = []
    errors: list[tuple[str, str]] = []

    for src in cfg.sources:
        if not src.enabled:
            log.info("skip (disabled): %s", src.id)
            continue
        log.info("fetching %s — %s", src.id, src.url)
        res = fetch(src.url, cfg.user_agent, cfg.request_timeout_seconds)
        if not res.ok:
            err = res.error or f"HTTP {res.status}"
            log.warning("fetch failed: %s — %s", src.id, err)
            errors.append((src.id, err))
            continue
        try:
            items = get_parser(src.parser)(res.text, src)
        except Exception as e:
            log.exception("parser error: %s", src.id)
            errors.append((src.id, f"parser error: {e}"))
            continue
        items = items[: cfg.max_items_per_source]
        log.info("  → %d items", len(items))
        all_items.extend(items)

    scored = rank(all_items, min_score=min_score)
    log.info("ranked: %d items above min_score=%d", len(scored), min_score)

    week_dir = out_root / week
    write_digest(scored, errors, week_dir / "digest.md", week)
    write_messages(scored, week_dir / "partner-messages.md", week, top_n=5)

    log.info("wrote %s/", week_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly India business-insurance scraper")
    parser.add_argument("--week", default=None, help="ISO week label (default: current week)")
    parser.add_argument("--out", default="roundups", help="Output root directory")
    parser.add_argument("--min-score", type=int, default=5, help="Minimum classifier score")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    week = args.week or week_label()
    return run(week=week, out_root=Path(args.out), min_score=args.min_score)


if __name__ == "__main__":
    sys.exit(main())
