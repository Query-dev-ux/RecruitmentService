import httpx
import pytest

from app.providers.hh.client import HHClient
from app.providers.hh.negotiations import iter_negotiation_resumes


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_negotiation_resumes_calls_response_collection_with_vacancy_id(respx_mock):
    route = respx_mock.get("/negotiations/response").mock(
        return_value=httpx.Response(200, json={"items": [], "pages": 0})
    )

    async with HHClient("token") as client:
        _ = [item async for item in iter_negotiation_resumes(client, "999")]

    sent = route.calls.last.request.url.params
    assert sent["vacancy_id"] == "999"
    assert sent["page"] == "0"


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_negotiation_resumes_yields_embedded_resume_with_negotiation_metadata(respx_mock):
    respx_mock.get("/negotiations/response").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "neg-1",
                        "state": {"id": "response", "name": "Отклик"},
                        "created_at": "2026-09-01T10:00:00+0300",
                        "resume": {"id": "res-1", "title": "Media Buyer"},
                    }
                ],
                "pages": 1,
            },
        )
    )

    async with HHClient("token") as client:
        items = [item async for item in iter_negotiation_resumes(client, "999")]

    assert len(items) == 1
    assert items[0]["id"] == "res-1"
    assert items[0]["title"] == "Media Buyer"
    assert items[0]["_negotiation"] == {"id": "neg-1", "state": "response", "created_at": "2026-09-01T10:00:00+0300"}


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_negotiation_resumes_handles_missing_resume_gracefully(respx_mock):
    respx_mock.get("/negotiations/response").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "neg-2", "state": {"id": "response"}, "created_at": "..."}], "pages": 1},
        )
    )

    async with HHClient("token") as client:
        items = [item async for item in iter_negotiation_resumes(client, "999")]

    assert len(items) == 1
    assert items[0]["_negotiation"]["id"] == "neg-2"


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_negotiation_resumes_pages_until_exhausted(respx_mock):
    respx_mock.get("/negotiations/response", params={"page": "0"}).mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "n1", "resume": {"id": "r1"}}], "pages": 2}
        )
    )
    respx_mock.get("/negotiations/response", params={"page": "1"}).mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "n2", "resume": {"id": "r2"}}], "pages": 2}
        )
    )

    async with HHClient("token") as client:
        items = [item async for item in iter_negotiation_resumes(client, "999")]

    assert [i["id"] for i in items] == ["r1", "r2"]


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_iter_negotiation_resumes_stops_when_no_items(respx_mock):
    respx_mock.get("/negotiations/response").mock(return_value=httpx.Response(200, json={"items": [], "pages": 1}))

    async with HHClient("token") as client:
        items = [item async for item in iter_negotiation_resumes(client, "999")]

    assert items == []
