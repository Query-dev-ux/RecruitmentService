def test_list_requires_auth(client):
    response = client.get("/search-templates")

    assert response.status_code == 401


def test_list_rejects_wrong_token(client):
    response = client.get("/search-templates", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401


def test_create_and_get_template(client, auth_headers):
    payload = {
        "name": "Media Buyer (Facebook, iGaming)",
        "crm_vacancy_id": "vac-123",
        "auto_search_enabled": True,
        "interval_minutes": 60,
        "criteria": [
            {"key": "vertical", "value": "igaming", "mode": "required", "weight": 25},
            {"key": "keitaro", "value": "true", "mode": "preferred", "weight": 10},
        ],
    }

    create_response = client.post("/search-templates", json=payload, headers=auth_headers)
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == payload["name"]
    assert len(body["criteria"]) == 2
    assert {c["key"] for c in body["criteria"]} == {"vertical", "keitaro"}

    get_response = client.get(f"/search-templates/{body['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_list_returns_created_templates(client, auth_headers):
    client.post("/search-templates", json={"name": "Template A"}, headers=auth_headers)
    client.post("/search-templates", json={"name": "Template B"}, headers=auth_headers)

    response = client.get("/search-templates", headers=auth_headers)

    assert response.status_code == 200
    names = {t["name"] for t in response.json()}
    assert names == {"Template A", "Template B"}


def test_invalid_interval_rejected(client, auth_headers):
    payload = {"name": "Bad interval", "auto_search_enabled": True, "interval_minutes": 45}

    response = client.post("/search-templates", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_update_replaces_criteria_and_delete_removes_template(client, auth_headers):
    create_response = client.post(
        "/search-templates",
        json={"name": "Temp", "criteria": [{"key": "geo", "value": "US", "mode": "required", "weight": 20}]},
        headers=auth_headers,
    )
    template_id = create_response.json()["id"]

    update_response = client.put(
        f"/search-templates/{template_id}",
        json={"is_active": False, "criteria": [{"key": "geo", "value": "PH", "mode": "required", "weight": 20}]},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["is_active"] is False
    assert len(updated["criteria"]) == 1
    assert updated["criteria"][0]["value"] == "PH"

    delete_response = client.delete(f"/search-templates/{template_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing_response = client.get(f"/search-templates/{template_id}", headers=auth_headers)
    assert missing_response.status_code == 404


def test_get_unknown_template_returns_404(client, auth_headers):
    response = client.get("/search-templates/00000000-0000-0000-0000-000000000000", headers=auth_headers)

    assert response.status_code == 404
