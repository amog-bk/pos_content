"""Google Sheets uploader.

Appends each weekly run to three tabs in a single sheet:
  - "Digest"          — every scored item that passed the classifier
  - "Weekly Roundup"  — one row per week with per-section items + the full
                         consolidated <300-word roundup message in the last
                         column
  - "Errors"          — sources that 403'd or timed out, per week

Tabs and headers are created on first use, so the user doesn't have to
pre-format the spreadsheet.

Auth: a service account JSON, supplied via env var `GOOGLE_SHEETS_SA_JSON`
(the JSON text itself, not a file path — easier to ship from GitHub
Secrets to a workflow).

If the env var is missing/blank, upload is a no-op and the scraper keeps
working without the sheet — useful while the user is still wiring up
credentials.
"""
from __future__ import annotations

import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials

from .classifier import ScoredItem
from .roundup import CATEGORY_ORDER
from .roundup_message import SECTIONS, SectionPick
from .whatsapp import clean_title, english_only_title

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DIGEST_HEADERS = ["Week", "Section", "Title", "Source", "Date", "URL", "Score", "Tags"]
ERRORS_HEADERS = ["Week", "Source ID", "Error"]
# Roundup headers: Week, one column per section, then the full message.
ROUNDUP_HEADERS = ["Week"] + [heading for _, heading, _ in SECTIONS] + ["Full Roundup (≤300 words)"]


def _open_sheet(sheet_id: str, sa_json: str) -> gspread.Spreadsheet:
    creds_info = json.loads(sa_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)


def _get_or_create_tab(book: gspread.Spreadsheet, name: str, headers: list[str]) -> gspread.Worksheet:
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=1000, cols=max(len(headers), 8))
        ws.update("A1", [headers])
        ws.freeze(rows=1)
        log.info("created worksheet: %s", name)
    return ws


def _primary_section(s: ScoredItem) -> str:
    return next((t for t in CATEGORY_ORDER if t in s.tags), "general")


def _format_section_items(pick: SectionPick, resolved_links: dict[str, str] | None) -> str:
    """Multi-line cell content listing the items that informed a section."""
    if not pick.items:
        return ""
    lines: list[str] = []
    if pick.extended:
        lines.append("(no fresh items this week — extended window)")
    for s in pick.items:
        url = (resolved_links or {}).get(s.item.url, s.item.url)
        date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else "no date"
        title = clean_title(english_only_title(s.item.title))
        lines.append(f"• {title}")
        lines.append(f"  {s.item.source_name} · {date}")
        lines.append(f"  {url}")
    return "\n".join(lines)


def upload(
    sheet_id: str,
    scored: list[ScoredItem],
    errors: list[tuple[str, str]],
    week_label: str,
    picks: list[SectionPick] | None = None,
    roundup_text: str = "",
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
    roundup_ws = _get_or_create_tab(book, "Weekly Roundup", ROUNDUP_HEADERS)
    err_ws = _get_or_create_tab(book, "Errors", ERRORS_HEADERS)

    # Digest rows: one per scored item, ordered by score desc.
    digest_rows: list[list] = []
    for s in scored:
        date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else ""
        url = (resolved_links or {}).get(s.item.url, s.item.url)
        digest_rows.append([
            week_label,
            _primary_section(s),
            clean_title(english_only_title(s.item.title)),
            s.item.source_name,
            date,
            url,
            s.score,
            ", ".join(s.tags),
        ])

    # Roundup row: one row, one column per section + final roundup column.
    roundup_row: list = [week_label]
    if picks:
        for pick in picks:
            roundup_row.append(_format_section_items(pick, resolved_links))
    else:
        roundup_row.extend([""] * len(SECTIONS))
    roundup_row.append(roundup_text)

    err_rows = [[week_label, src_id, err] for src_id, err in errors]

    if digest_rows:
        digest_ws.append_rows(digest_rows, value_input_option="USER_ENTERED")
    roundup_ws.append_rows([roundup_row], value_input_option="USER_ENTERED")
    if err_rows:
        err_ws.append_rows(err_rows, value_input_option="USER_ENTERED")

    log.info("sheet upload complete: %d digest rows, 1 roundup row, %d error rows",
             len(digest_rows), len(err_rows))
