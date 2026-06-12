"""Google Sheets uploader for the weekly industry briefing.

Appends each weekly run to three tabs in a single sheet:
  - "Digest"    — every scored item (Week, Section, Title, Source, Date,
                  URL, Score, Tags)
  - "Briefing"  — one row per week: a Headlines column, one column per
                  section (Deals / Regulatory & Governance / Industry &
                  Premium Trends) listing the ranked stories, a clean
                  "Final Briefing" column with just the shareable
                  WhatsApp-formatted writeup (no links), and a separate
                  "Sources" column with the publisher links — both filled
                  in-session.
  - "Errors"    — sources that 403'd or timed out, per week

Auth: service account JSON via env var GOOGLE_SHEETS_SA_JSON. No-op if the
env var is missing, so the scraper still runs without credentials.
"""
from __future__ import annotations

import json
import logging
import os

from .briefing import SECTIONS, SectionBucket
from .classifier import ScoredItem, TAG_SECTION
from .whatsapp import clean_title, english_only_title

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DIGEST_HEADERS = ["Week", "Section", "Title", "Source", "Date", "URL", "Score", "Tags"]
ERRORS_HEADERS = ["Week", "Source ID", "Error"]
BRIEFING_HEADERS = (
    ["Week", "Headlines"]
    + [heading for _, heading in SECTIONS]
    + ["Final Briefing (written in-session)", "Sources"]
)


def _open_sheet(sheet_id: str, sa_json: str):
    # Lazy-import gspread so the scraper can run without it when no sheet
    # credentials are configured (e.g. local dry-runs).
    import gspread
    from google.oauth2.service_account import Credentials

    creds_info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)


def _get_or_create_tab(book, name: str, headers: list[str]):
    import gspread
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=1000, cols=max(len(headers), 8))
        ws.update("A1", [headers])
        ws.freeze(rows=1)
        log.info("created worksheet: %s", name)
    return ws


def _digest_section(s: ScoredItem) -> str:
    if "data" in s.tags:  # Council NBP/GDPI releases always sit in Trends
        return "trends"
    for tag in s.tags:
        if tag in TAG_SECTION:
            return TAG_SECTION[tag]
    return "trends"


def _format_items_cell(items: list[ScoredItem], resolved_links: dict[str, str] | None,
                       extended: bool = False) -> str:
    if not items:
        return ""
    lines: list[str] = []
    if extended:
        lines.append("(no fresh items this week — extended window)")
    for s in items:
        url = (resolved_links or {}).get(s.item.url, s.item.url)
        date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else "no date"
        title = clean_title(english_only_title(s.item.title))
        lines.append(f"• {title}")
        meta = f"  {s.item.source_name} · {date}"
        lines.append(meta)
        if s.item.summary:
            lines.append(f"  {s.item.summary.strip()}")
        lines.append(f"  {url}")
    return "\n".join(lines)


def upload(
    sheet_id: str,
    scored: list[ScoredItem],
    errors: list[tuple[str, str]],
    week_label: str,
    buckets: list[SectionBucket] | None = None,
    headlines: list[ScoredItem] | None = None,
    final_briefing: str = "",
    final_sources: str = "",
    resolved_links: dict[str, str] | None = None,
) -> None:
    sa_json = os.environ.get("GOOGLE_SHEETS_SA_JSON", "").strip()
    if not sa_json:
        log.info("GOOGLE_SHEETS_SA_JSON not set — skipping sheet upload.")
        return
    if not sheet_id:
        log.info("No sheet_id provided — skipping sheet upload.")
        return

    log.info("uploading %d items to sheet %s", len(scored), sheet_id)
    book = _open_sheet(sheet_id, sa_json)

    digest_ws = _get_or_create_tab(book, "Digest", DIGEST_HEADERS)
    briefing_ws = _get_or_create_tab(book, "Briefing", BRIEFING_HEADERS)
    err_ws = _get_or_create_tab(book, "Errors", ERRORS_HEADERS)

    digest_rows: list[list] = []
    for s in scored:
        date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else ""
        url = (resolved_links or {}).get(s.item.url, s.item.url)
        digest_rows.append([
            week_label,
            _digest_section(s),
            clean_title(english_only_title(s.item.title)),
            s.item.source_name,
            date,
            url,
            s.score,
            ", ".join(s.tags),
        ])

    # Briefing row: Week | Headlines | <section cells...> | Final Briefing | Sources
    briefing_row: list = [week_label]
    briefing_row.append(_format_items_cell(headlines or [], resolved_links))
    bucket_by_id = {b.section_id: b for b in (buckets or [])}
    for sid, _heading in SECTIONS:
        b = bucket_by_id.get(sid)
        if b:
            briefing_row.append(_format_items_cell(b.items, resolved_links, b.extended))
        else:
            briefing_row.append("")
    briefing_row.append(final_briefing)
    briefing_row.append(final_sources)

    err_rows = [[week_label, src_id, err] for src_id, err in errors]

    if digest_rows:
        digest_ws.append_rows(digest_rows, value_input_option="USER_ENTERED")
    briefing_ws.append_rows([briefing_row], value_input_option="USER_ENTERED")
    if err_rows:
        err_ws.append_rows(err_rows, value_input_option="USER_ENTERED")

    log.info("sheet upload complete: %d digest rows, 1 briefing row, %d error rows",
             len(digest_rows), len(err_rows))
