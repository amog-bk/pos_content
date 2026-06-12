"""Per-source feed-health tracking across weekly runs.

Keeps a small JSON ledger (roundups/feed-health.json — committed by the
workflow alongside the weekly material) recording, for every enabled
source: consecutive failure count, last successful week, last error, and
total failures. Sources failing CHRONIC_THRESHOLD weeks in a row get
flagged in the digest so feed decay is noticed instead of being
discovered mid-briefing on a Friday.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

CHRONIC_THRESHOLD = 3  # consecutive failed weeks before a source is "chronic"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log.warning("feed-health ledger unreadable (%s) — starting fresh", e)
        return {}


def update(
    health: dict,
    enabled_ids: list[str],
    failures: dict[str, str],
    week_label: str,
) -> dict:
    """Record this week's outcome per enabled source. `failures` maps
    source_id -> error string for sources that failed; everything else in
    `enabled_ids` counts as a success."""
    for sid in enabled_ids:
        entry = health.setdefault(sid, {
            "consecutive_failures": 0,
            "total_failures": 0,
            "last_ok_week": None,
            "last_error": None,
        })
        if sid in failures:
            entry["consecutive_failures"] += 1
            entry["total_failures"] += 1
            entry["last_error"] = f"{week_label}: {failures[sid]}"
        else:
            entry["consecutive_failures"] = 0
            entry["last_ok_week"] = week_label
            entry["last_error"] = None
    return health


def chronic(health: dict) -> list[tuple[str, int]]:
    """Sources at or past the chronic threshold, worst first."""
    out = [(sid, e["consecutive_failures"]) for sid, e in health.items()
           if e.get("consecutive_failures", 0) >= CHRONIC_THRESHOLD]
    return sorted(out, key=lambda t: t[1], reverse=True)


def save(health: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health, indent=2, sort_keys=True) + "\n")
