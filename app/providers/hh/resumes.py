"""Search execution and full-resume fetch against HH's employer resume API.

Limits below are per the plan's confirmed HH.ru findings: max `per_page` is
100, and total reachable depth (page * per_page) is capped at 2000 results —
HH simply won't paginate past that, so a template's search must narrow its
filters rather than expect to page through more than that.
"""

from typing import Any, AsyncIterator, Optional

from app.providers.hh.client import HHClient

MAX_PER_PAGE = 100
MAX_RESULT_DEPTH = 2000


async def search_resumes(
    client: HHClient, params: dict[str, Any], *, page: int = 0, per_page: int = 20
) -> dict[str, Any]:
    per_page = min(per_page, MAX_PER_PAGE)
    response = await client.get("/resumes", params={**params, "page": page, "per_page": per_page})
    return response.json()


async def iter_all_resumes(
    client: HHClient, params: dict[str, Any], *, per_page: int = 100, max_results: Optional[int] = None
) -> AsyncIterator[dict[str, Any]]:
    """Pages through /resumes until HH stops returning items, the resource's
    own reachable depth is exhausted, or max_results is hit — whichever
    comes first."""
    per_page = min(per_page, MAX_PER_PAGE)
    page = 0
    yielded = 0

    while page * per_page < MAX_RESULT_DEPTH:
        payload = await search_resumes(client, params, page=page, per_page=per_page)
        items = payload.get("items") or []
        if not items:
            return

        for item in items:
            yield item
            yielded += 1
            if max_results is not None and yielded >= max_results:
                return

        if page >= (payload.get("pages") or 0) - 1:
            return
        page += 1


async def get_resume(client: HHClient, resume_id: str) -> dict[str, Any]:
    response = await client.get(f"/resumes/{resume_id}")
    return response.json()
