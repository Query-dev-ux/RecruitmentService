def test_submit_requires_auth(client):
    response = client.post("/telegram/applications", json={"telegram_user_id": 1})

    assert response.status_code == 401


def test_submit_creates_candidate(client, auth_headers):
    response = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 12345, "candidate_text": "Опыт в Facebook Ads, iGaming"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["external_candidate_id"]
    assert body["scored_against_templates"] == 0  # no vacancy_ref given


def test_submit_dedupes_by_telegram_user_id(client, auth_headers):
    first = client.post("/telegram/applications", json={"telegram_user_id": 555}, headers=auth_headers).json()
    second = client.post("/telegram/applications", json={"telegram_user_id": 555}, headers=auth_headers).json()

    assert first["external_candidate_id"] == second["external_candidate_id"]
    assert first["telegram_application_id"] != second["telegram_application_id"]  # two distinct applications


def test_submit_scores_against_matching_vacancy_templates(client, auth_headers):
    template_payload = {
        "name": "Media Buyer",
        "crm_vacancy_id": "vac-42",
        "criteria": [{"key": "vertical", "value": "igaming", "mode": "preferred", "weight": 100}],
    }
    client.post("/search-templates", json=template_payload, headers=auth_headers)

    response = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 777, "vacancy_ref": "vac-42", "candidate_text": "iGaming media buyer"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["scored_against_templates"] == 1


def test_submit_does_not_score_against_unrelated_vacancy(client, auth_headers):
    client.post("/search-templates", json={"name": "Other role", "crm_vacancy_id": "vac-99"}, headers=auth_headers)

    response = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 888, "vacancy_ref": "vac-does-not-exist"},
        headers=auth_headers,
    )

    assert response.json()["scored_against_templates"] == 0
