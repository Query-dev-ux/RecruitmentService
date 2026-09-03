"""Shared helper for OR-alternative criterion values.

A criterion's `value` can be a single value, or several alternatives
separated by `|` (pipe) — meaning "matches ANY of these". Covers real
recruiting needs like a position title with several accepted synonyms
("Media Buyer|Facebook Media Buyer|Senior Media Buyer|Traffic Manager"), a
GEO group ("USA|UK|Canada|Australia"), or a job-search-status set
("active_search|looking_for_offers").

Used by both providers/hh/search.py (building the HH query) and
scoring/engine.py (scoring a fetched candidate) so the same criterion value
means the same thing in both places. Plain single-value criteria — the
common case — are unaffected: splitting a pipe-free string just returns a
one-item list.
"""


def split_alternatives(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]
