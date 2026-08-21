"""Thin async HTTP client for the HH API.

Handles bearer auth, exponential backoff + Retry-After on 429/5xx, and
surfaces access-tier problems (403 — e.g. no paid "database access" tariff)
as a distinct exception so callers can log a clear, actionable event instead
of a generic crash. See the plan's HH.ru findings: no published fixed rate
limits, so backoff here is generic/defensive rather than tuned to a number.
"""

import asyncio
from typing import Any, Optional

import httpx

from app.logging_config import get_logger, log_event

logger = get_logger(__name__)

HH_API_BASE_URL = "https://api.hh.ru"
_MAX_BACKOFF_SECONDS = 30.0


class HHError(Exception):
    """Base error for HH API failures."""


class HHAuthError(HHError):
    """401 — access token invalid/expired."""


class HHAccessDeniedError(HHError):
    """403 — action not permitted for this employer account, e.g. missing
    the paid "database access" (resume search / contacts) tariff."""


class HHRateLimitedError(HHError):
    """429/5xx that persisted past all retries."""


class HHClient:
    def __init__(self, access_token: str, *, base_url: str = HH_API_BASE_URL, max_retries: int = 3):
        self._access_token = access_token
        self._max_retries = max_retries
        self._http = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "HHClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", None) or {}
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("User-Agent", "CelestialGroup-RecruitmentService/1.0")

        attempt = 0
        while True:
            attempt += 1
            response = await self._http.request(method, path, headers=headers, **kwargs)

            if response.status_code == 401:
                raise HHAuthError(f"HH API returned 401 for {method} {path}")
            if response.status_code == 403:
                raise HHAccessDeniedError(
                    f"HH API returned 403 for {method} {path} "
                    "(likely missing a paid access tier, e.g. resume database access)"
                )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt > self._max_retries:
                    log_event(
                        logger, "HH_REQUEST_FAILED", level="error",
                        method=method, path=path, status=response.status_code, attempt=attempt,
                    )
                    raise HHRateLimitedError(
                        f"HH API returned {response.status_code} for {method} {path} after {attempt} attempts"
                    )
                delay = _retry_delay(response, attempt)
                log_event(
                    logger, "HH_REQUEST_RETRY", level="warning",
                    method=method, path=path, status=response.status_code, attempt=attempt, delay_seconds=delay,
                )
                await asyncio.sleep(delay)
                continue

            response.raise_for_status()
            return response

    async def get(self, path: str, *, params: Optional[dict] = None) -> httpx.Response:
        return await self.request("GET", path, params=params)


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return min(2**attempt, _MAX_BACKOFF_SECONDS)
