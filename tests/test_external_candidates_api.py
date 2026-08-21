def test_list_requires_auth(client):
    response = client.get("/external-candidates")

    assert response.status_code == 401


def test_list_returns_candidate_with_sources_and_scores(client, auth_headers):
    template = client.post(
        "/search-templates",
        json={
            "name": "Media Buyer",
            "criteria": [{"key": "vertical", "value": "igaming", "mode": "preferred", "weight": 100}],
        },
        headers=auth_headers,
    ).json()

    submit = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 42, "vacancy_ref": None, "candidate_text": "iGaming media buyer"},
        headers=auth_headers,
    ).json()
    candidate_id = submit["external_candidate_id"]

    response = client.get("/external-candidates", headers=auth_headers)

    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["id"] == candidate_id
    assert candidate["sources"] == [
        {
            "source": "telegram",
            "external_id": "42",
            "external_url": None,
            "first_seen_at": candidate["sources"][0]["first_seen_at"],
            "last_seen_at": candidate["sources"][0]["last_seen_at"],
        }
    ]
    assert candidate["scores"] == []  # no vacancy_ref given -> not scored against the template above


def test_get_candidate_by_id(client, auth_headers):
    submit = client.post(
        "/telegram/applications", json={"telegram_user_id": 99, "candidate_text": "hi"}, headers=auth_headers
    ).json()
    candidate_id = submit["external_candidate_id"]

    response = client.get(f"/external-candidates/{candidate_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == candidate_id


def test_get_unknown_candidate_returns_404(client, auth_headers):
    response = client.get("/external-candidates/00000000-0000-0000-0000-000000000000", headers=auth_headers)

    assert response.status_code == 404


def test_list_filters_by_source(client, auth_headers):
    client.post("/telegram/applications", json={"telegram_user_id": 1}, headers=auth_headers)

    telegram_only = client.get("/external-candidates", params={"source": "telegram"}, headers=auth_headers).json()
    hh_only = client.get("/external-candidates", params={"source": "hh"}, headers=auth_headers).json()

    assert len(telegram_only) == 1
    assert hh_only == []


def test_list_filters_by_search_template_and_min_score(client, auth_headers):
    template = client.post(
        "/search-templates",
        json={
            "name": "Media Buyer",
            "crm_vacancy_id": "vac-1",
            "criteria": [{"key": "vertical", "value": "igaming", "mode": "preferred", "weight": 100}],
        },
        headers=auth_headers,
    ).json()

    client.post(
        "/telegram/applications",
        json={"telegram_user_id": 10, "vacancy_ref": "vac-1", "candidate_text": "iGaming expert"},
        headers=auth_headers,
    )
    client.post(
        "/telegram/applications",
        json={"telegram_user_id": 11, "vacancy_ref": "vac-1", "candidate_text": "unrelated skills"},
        headers=auth_headers,
    )

    scoped = client.get(
        "/external-candidates", params={"search_template_id": template["id"]}, headers=auth_headers
    ).json()
    high_scorers = client.get(
        "/external-candidates", params={"search_template_id": template["id"], "min_score": 50}, headers=auth_headers
    ).json()

    assert len(scoped) == 2
    assert len(high_scorers) == 1


def test_list_respects_limit(client, auth_headers):
    for i in range(3):
        client.post("/telegram/applications", json={"telegram_user_id": i}, headers=auth_headers)

    response = client.get("/external-candidates", params={"limit": 2}, headers=auth_headers)

    assert len(response.json()) == 2
