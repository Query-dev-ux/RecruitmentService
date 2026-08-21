import httpx
import pytest

from app.providers.hh.client import HHClient
from app.providers.hh.resumes import get_resume, iter_all_resumes, search_resumes


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_search_resumes_passes_pagination_params(respx_mock):
    route = respx_mock.get("/resumes").mock(return_value=httpx.Response(200, json={"items": [], "pages": 0}))

    async with HHClient("token") as client:
        await search_resumes(client, {"text": "media buyer"}, page=1, per_page=50)

    sent = route.calls.last.request.url.params
    assert sent["page"] == "1"
    assert sent["per_page"] == "50"
    assert sent["text"] == "media buyer"


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_search_resumes_caps_per_page_at_100(respx_mock):
    route = respx_mock.get("/resumes").mock(return_value=httpx.Response(200, json={"items": [], "pages": 0}))

    async with HHClient("token") as client:
        await search_resumes(client, {}, per_page=500)

    assert route.calls.last.request.url.params["per_page"] == "100"


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_all_resumes_pages_until_exhausted(respx_mock):
    respx_mock.get("/resumes", params={"page": "0"}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "1"}, {"id": "2"}], "pages": 2})
    )
    respx_mock.get("/resumes", params={"page": "1"}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "3"}], "pages": 2})
    )

    async with HHClient("token") as client:
        items = [item async for item in iter_all_resumes(client, {}, per_page=2)]

    assert [i["id"] for i in items] == ["1", "2", "3"]


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_all_resumes_stops_at_max_results(respx_mock):
    respx_mock.get("/resumes", params={"page": "0"}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "1"}, {"id": "2"}, {"id": "3"}], "pages": 1})
    )

    async with HHClient("token") as client:
        items = [item async for item in iter_all_resumes(client, {}, per_page=3, max_results=2)]

    assert [i["id"] for i in items] == ["1", "2"]


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_get_resume_fetches_by_id(respx_mock):
    respx_mock.get("/resumes/abc123").mock(return_value=httpx.Response(200, json={"id": "abc123", "title": "X"}))

    async with HHClient("token") as client:
        resume = await get_resume(client, "abc123")

    assert resume == {"id": "abc123", "title": "X"}
