import httpx
import pytest
import respx

from app.config import settings
from app.providers.hh.auth import build_authorize_url, exchange_code_for_token, refresh_access_token


def test_build_authorize_url_contains_required_params():
    url = build_authorize_url(state="abc123")

    assert url.startswith("https://hh.ru/oauth/authorize?")
    assert "response_type=code" in url
    assert "state=abc123" in url
    assert f"client_id={settings.HH_CLIENT_ID}" in url


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_exchange_code_for_token_posts_authorization_code_grant(respx_mock):
    route = respx_mock.post("/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "at", "refresh_token": "rt", "token_type": "bearer", "expires_in": 1209600}
        )
    )

    token = await exchange_code_for_token("the-code")

    assert token["access_token"] == "at"
    sent_body = route.calls.last.request.content.decode()
    assert "grant_type=authorization_code" in sent_body
    assert "code=the-code" in sent_body


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_refresh_access_token_posts_refresh_token_grant(respx_mock):
    route = respx_mock.post("/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "at2", "refresh_token": "rt2", "token_type": "bearer", "expires_in": 1209600}
        )
    )

    token = await refresh_access_token("old-refresh-token")

    assert token["access_token"] == "at2"
    sent_body = route.calls.last.request.content.decode()
    assert "grant_type=refresh_token" in sent_body
    assert "refresh_token=old-refresh-token" in sent_body
