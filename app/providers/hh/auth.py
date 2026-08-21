"""HH OAuth2 flow (authorization_code + refresh_token).

Per the plan's confirmed HH.ru research: access tokens last 14 days,
refresh tokens are single-use and rotate on every refresh. HH_CLIENT_ID/
HH_CLIENT_SECRET/HH_REDIRECT_URI come from the app registered on dev.hh.ru
(currently under HH's review). NOT verified against a live call yet — no
approved app/credentials exist in this environment; endpoint URLs match
HH's documented OAuth flow, confirm against dev.hh.ru once credentials land.
"""

from typing import TypedDict
from urllib.parse import urlencode

import httpx

from app.config import settings

HH_AUTHORIZE_URL = "https://hh.ru/oauth/authorize"
HH_TOKEN_URL = "https://api.hh.ru/token"


class TokenResponse(TypedDict):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def build_authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.HH_CLIENT_ID,
        "redirect_uri": settings.HH_REDIRECT_URI,
        "state": state,
    }
    return f"{HH_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> TokenResponse:
    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.post(
            HH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.HH_CLIENT_ID,
                "client_secret": settings.HH_CLIENT_SECRET,
                "redirect_uri": settings.HH_REDIRECT_URI,
                "code": code,
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.post(
            HH_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        response.raise_for_status()
        return response.json()
