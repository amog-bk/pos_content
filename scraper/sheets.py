"""Google Sheets uploader.

Appends each weekly run to three tabs in a single sheet:
  - "Digest"          — every scored item that passed the classifier
  - "Partner Messages" — the WhatsApp drafts (one per row, message in one cell)
  - "Errors"           — sources that 403'd or timed out

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
from typing import Iterable

import gspread
from google.oauth2.service_account import Credentials

from .classifier import ScoredItem
from .roundup import CATEGORY_ORDER
from .whatsapp import clean_title, english_only_title, draft_message, _primary_tag

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DIGEST_HEADERS = ["Week", "Section", "Title", "Source", "Date", "URL", "Score", "Tags"]
MESSAGES_HEADERS = ["Week", "Category", "Score", "Title", "Source", "URL", "Message"]
ERRORS_HEADERS = ["Week", "Source ID", "Error"]


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


def upload(
    sheet_id: str,
    scored: list[ScoredItem],
    errors: list[tuple[str, str]],
    week_label: str,
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
    msgs_ws = _get_or_create_tab(book, "Partner Messages", MESSAGES_HEADERS)
    err_ws = _get_or_create_tab(book, "Errors", ERRORS_HEADERS)

    # Digest rows: one per scored item, ordered by score desc.
    digest_rows: list[list] = []
    for s in scored:
        date = s.item.publish_date.strftime("%Y-%m-%d") if s.item.publish_date else ""
        digest_rows.append([
            week_label,
            _primary_section(s),
            s.item.title,
            s.item.source_name,
            date,
            s.item.url,
            s.score,
            ", ".join(s.tags),
        ])

    # Partner Messages rows: top 5 unique-tag items, same selection logic as
    # whatsapp.write_messages. Resolve Google News URLs (passed in from caller).
    msg_rows: list[list] = []
    seen_tags: set[str] = set()
    chosen: list[ScoredItem] = []
    for s in scored:
        tag = _primary_tag(s)
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        chosen.append(s)
        if len(chosen) == 5:
            break
    for s in chosen:
        link = (resolved_links or {}).get(s.item.url, s.item.url)
        # Reuse the same draft generator as the markdown file — single source of voice.
        msg_text = draft_message(s, url=link)
        clean = clean_title(english_only_title(s.item.title))
        msg_rows.append([
            week_label,
            _primary_tag(s),
            s.score,
            clean,
            s.item.source_name,
            link,
            msg_text,
        ])

    err_rows = [[week_label, src_id, err] for src_id, err in errors]

    if digest_rows:
        digest_ws.append_rows(digest_rows, value_input_option="USER_ENTERED")
    if msg_rows:
        msgs_ws.append_rows(msg_rows, value_input_option="USER_ENTERED")
    if err_rows:
        err_ws.append_rows(err_rows, value_input_option="USER_ENTERED")

    log.info("sheet upload complete: %d digest rows, %d message rows, %d error rows",
             len(digest_rows), len(msg_rows), len(err_rows))
