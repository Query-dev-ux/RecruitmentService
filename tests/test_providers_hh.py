import httpx
import pytest


def test_status_reports_not_connected_when_no_account(client, auth_headers):
    response = client.get("/providers/hh/status", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "connected": False,
        "account_id": None,
        "label": None,
        "status": None,
        "connected_at": None,
    }


def test_status_requires_auth(client):
    response = client.get("/providers/hh/status")

    assert response.status_code == 401


def test_connect_returns_authorize_url(client, auth_headers):
    response = client.post("/providers/hh/connect", headers=auth_headers)

    assert response.status_code == 200
    url = response.json()["authorize_url"]
    assert url.startswith("https://hh.ru/oauth/authorize?")
    assert "response_type=code" in url


def test_connect_requires_auth(client):
    response = client.post("/providers/hh/connect")

    assert response.status_code == 401


@pytest.mark.respx(base_url="https://api.hh.ru")
def test_callback_connects_account_and_status_reflects_it(client, auth_headers, respx_mock):
    respx_mock.post("/token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "at", "refresh_token": "rt", "token_type": "bearer", "expires_in": 1209600}
        )
    )

    callback_response = client.get("/providers/hh/callback", params={"code": "the-code"})
    assert callback_response.status_code == 200
    assert callback_response.json() == {"status": "connected"}

    status_response = client.get("/providers/hh/status", headers=auth_headers)
    body = status_response.json()
    assert body["connected"] is True
    assert body["status"] == "connected"
    assert body["connected_at"] is not None


@pytest.mark.respx(base_url="https://api.hh.ru")
def test_callback_does_not_require_service_token(client, respx_mock):
    # No Authorization header — should never bounce with our own 401. HH
    # itself would reject a bogus code (mocked here as a 400), which is a
    # different failure than "you forgot the internal service token".
    respx_mock.post("/token").mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))

    response = client.get("/providers/hh/callback", params={"code": "whatever"})

    assert response.status_code == 400
    assert response.status_code != 401
