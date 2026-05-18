from __future__ import annotations

from . import generic_html, irdai_listing

PARSERS = {
    "generic_html": generic_html.parse,
    "irdai_listing": irdai_listing.parse,
}


def get_parser(name: str):
    if name not in PARSERS:
        raise KeyError(f"Unknown parser: {name}")
    return PARSERS[name]
