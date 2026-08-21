import httpx
import pytest
import respx

from app.providers.hh.client import HHAccessDeniedError, HHAuthError, HHClient, HHRateLimitedError


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_get_returns_response_on_success(respx_mock):
    respx_mock.get("/resumes").mock(return_value=httpx.Response(200, json={"items": []}))

    async with HHClient("token") as client:
        response = await client.get("/resumes")

    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_sends_bearer_token(respx_mock):
    route = respx_mock.get("/resumes").mock(return_value=httpx.Response(200, json={}))

    async with HHClient("my-secret-token") as client:
        await client.get("/resumes")

    assert route.calls.last.request.headers["Authorization"] == "Bearer my-secret-token"


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_401_raises_auth_error(respx_mock):
    respx_mock.get("/resumes").mock(return_value=httpx.Response(401))

    async with HHClient("token") as client:
        with pytest.raises(HHAuthError):
            await client.get("/resumes")


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_403_raises_access_denied_error(respx_mock):
    respx_mock.get("/resumes").mock(return_value=httpx.Response(403))

    async with HHClient("token") as client:
        with pytest.raises(HHAccessDeniedError):
            await client.get("/resumes")


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_retries_429_then_succeeds(respx_mock):
    route = respx_mock.get("/resumes")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"items": ["ok"]}),
    ]

    async with HHClient("token", max_retries=3) as client:
        response = await client.get("/resumes")

    assert response.status_code == 200
    assert route.call_count == 2


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_exhausts_retries_and_raises_rate_limited(respx_mock):
    respx_mock.get("/resumes").mock(return_value=httpx.Response(429, headers={"Retry-After": "0"}))

    async with HHClient("token", max_retries=2) as client:
        with pytest.raises(HHRateLimitedError):
            await client.get("/resumes")
