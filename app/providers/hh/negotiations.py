"""Reading inbound candidate responses ("negotiations") to a vacancy the
employer posted on HH — a distinct source from active resume search
(search.py + resumes.py): confirmed via the plan's HH.ru research that
reading responses to your own vacancy needs no paid "database access"
tariff, unlike searching the resume database.

HH's API here is a two-step structure, not a flat list:
  1. GET /negotiations                              -> a collections index
     (per-state buckets: response/invitation/phone_calls/...), mostly
     informational (UI badge counts).
  2. GET /negotiations/{collection_name}?vacancy_id=... -> the actual
     paginated items for one bucket.

We only ever read the "response" collection — freshly inbound applications
not yet acted on. Other collections (invitation, phone_calls, ...)
represent later pipeline stages that are CRM's concern once a candidate is
synced, not ours to source from. `collection_name` values are stable,
well-known ids (not per-employer-generated), so we go straight to
`/negotiations/response` without querying the index first.

Deliberately sends no resume-search-style filter params (age_from, area,
...) even though the endpoint accepts them — the OpenAPI spec documents a
possible 403 "bad authorization / payment method" response on this
endpoint without stating exactly which condition triggers it; keeping the
call to just vacancy_id/page/per_page sidesteps that ambiguity rather than
risk it.

Each negotiation item embeds a resume snapshot inline — a shorter object
than the full/search resume schema, not independently field-mapped this
session. providers.hh.normalize.normalize_resume() is reused as-is rather
than duplicated: it's .get()-based throughout, so any field this shorter
shape lacks just stays None instead of crashing.
"""

from typing import Any, AsyncIterator

from app.providers.hh.client import HHClient

RESPONSE_COLLECTION = "response"
MAX_PER_PAGE = 50  # HH's documented cap for /negotiations/{collection_name} (lower than /resumes' 100)


async def iter_negotiation_resumes(
    client: HHClient, vacancy_id: str, *, per_page: int = MAX_PER_PAGE
) -> AsyncIterator[dict[str, Any]]:
    """Yields each negotiation's embedded resume dict, annotated with the
    negotiation's own id/state/timestamp under "_negotiation" so callers
    can trace a candidate back to the specific response if needed."""
    per_page = min(per_page, MAX_PER_PAGE)
    page = 0

    while True:
        response = await client.get(
            f"/negotiations/{RESPONSE_COLLECTION}",
            params={"vacancy_id": vacancy_id, "page": page, "per_page": per_page},
        )
        payload = response.json()
        items = payload.get("items") or []
        if not items:
            return

        for item in items:
            resume = dict(item.get("resume") or {})
            resume["_negotiation"] = {
                "id": item.get("id"),
                "state": (item.get("state") or {}).get("id"),
                "created_at": item.get("created_at"),
            }
            yield resume

        if page >= (payload.get("pages") or 1) - 1:
            return
        page += 1
