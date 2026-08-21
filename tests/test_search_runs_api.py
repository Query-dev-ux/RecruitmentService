def test_run_template_enqueues_and_returns_queued_status(client, auth_headers):
    create_response = client.post("/search-templates", json={"name": "Media Buyer"}, headers=auth_headers)
    template_id = create_response.json()["id"]

    run_response = client.post(f"/search-templates/{template_id}/run", headers=auth_headers)

    assert run_response.status_code == 202
    body = run_response.json()
    assert body["status"] == "queued"
    assert "search_run_id" in body


def test_run_template_requires_auth(client):
    response = client.post("/search-templates/00000000-0000-0000-0000-000000000000/run")

    assert response.status_code == 401


def test_run_unknown_template_returns_404(client, auth_headers):
    response = client.post(
        "/search-templates/00000000-0000-0000-0000-000000000000/run", headers=auth_headers
    )

    assert response.status_code == 404


def test_get_search_run_returns_details(client, auth_headers):
    create_response = client.post("/search-templates", json={"name": "Media Buyer"}, headers=auth_headers)
    template_id = create_response.json()["id"]
    run_response = client.post(f"/search-templates/{template_id}/run", headers=auth_headers)
    run_id = run_response.json()["search_run_id"]

    get_response = client.get(f"/search-runs/{run_id}", headers=auth_headers)

    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == run_id
    assert body["search_template_id"] == template_id
    assert body["trigger"] == "manual"
    assert body["status"] == "queued"


def test_get_unknown_search_run_returns_404(client, auth_headers):
    response = client.get("/search-runs/00000000-0000-0000-0000-000000000000", headers=auth_headers)

    assert response.status_code == 404


def test_list_search_runs_filters_by_template(client, auth_headers):
    template_a = client.post("/search-templates", json={"name": "A"}, headers=auth_headers).json()["id"]
    template_b = client.post("/search-templates", json={"name": "B"}, headers=auth_headers).json()["id"]
    client.post(f"/search-templates/{template_a}/run", headers=auth_headers)
    client.post(f"/search-templates/{template_b}/run", headers=auth_headers)

    response = client.get("/search-runs", params={"search_template_id": template_a}, headers=auth_headers)

    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["search_template_id"] == template_a


def test_list_search_runs_requires_auth(client):
    response = client.get("/search-runs")

    assert response.status_code == 401
