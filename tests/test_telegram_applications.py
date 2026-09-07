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


def test_submit_captures_telegram_name_and_username(client, auth_headers):
    submit = client.post(
        "/telegram/applications",
        json={
            "telegram_user_id": 321,
            "telegram_full_name": "Daniil CG",
            "telegram_username": "daniil_cg",
            "candidate_text": "hi",
        },
        headers=auth_headers,
    ).json()

    candidate = client.get(f"/external-candidates/{submit['external_candidate_id']}", headers=auth_headers).json()

    assert candidate["parsed_profile"]["full_name"] == "Daniil CG"
    assert candidate["sources"][0]["external_url"] == "https://t.me/daniil_cg"


def test_submit_exposes_vacancy_ref_on_the_candidate(client, auth_headers):
    submit = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 900, "vacancy_ref": "Media Buyer (Facebook)", "candidate_text": "hi"},
        headers=auth_headers,
    ).json()

    candidate = client.get(f"/external-candidates/{submit['external_candidate_id']}", headers=auth_headers).json()

    assert candidate["vacancy_ref"] == "Media Buyer (Facebook)"


def test_submit_without_vacancy_ref_leaves_it_null(client, auth_headers):
    submit = client.post(
        "/telegram/applications", json={"telegram_user_id": 901, "candidate_text": "hi"}, headers=auth_headers
    ).json()

    candidate = client.get(f"/external-candidates/{submit['external_candidate_id']}", headers=auth_headers).json()

    assert candidate["vacancy_ref"] is None


def test_resubmit_updates_vacancy_ref_but_a_general_reply_does_not_clear_it(client, auth_headers):
    first = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 902, "vacancy_ref": "vac-1", "candidate_text": "first"},
        headers=auth_headers,
    ).json()

    client.post(
        "/telegram/applications",
        json={"telegram_user_id": 902, "candidate_text": "general follow-up, no vacancy this time"},
        headers=auth_headers,
    )

    candidate = client.get(f"/external-candidates/{first['external_candidate_id']}", headers=auth_headers).json()
    assert candidate["vacancy_ref"] == "vac-1"  # unchanged — a vacancy-less reply doesn't erase it

    client.post(
        "/telegram/applications",
        json={"telegram_user_id": 902, "vacancy_ref": "vac-2", "candidate_text": "applied elsewhere too"},
        headers=auth_headers,
    )
    candidate = client.get(f"/external-candidates/{first['external_candidate_id']}", headers=auth_headers).json()
    assert candidate["vacancy_ref"] == "vac-2"  # latest actual vacancy wins


def test_list_filters_by_vacancy_ref(client, auth_headers):
    client.post(
        "/telegram/applications",
        json={"telegram_user_id": 910, "vacancy_ref": "vac-a", "candidate_text": "a"},
        headers=auth_headers,
    )
    client.post(
        "/telegram/applications",
        json={"telegram_user_id": 911, "vacancy_ref": "vac-b", "candidate_text": "b"},
        headers=auth_headers,
    )

    vac_a_only = client.get("/external-candidates", params={"vacancy_ref": "vac-a"}, headers=auth_headers).json()

    assert len(vac_a_only) == 1
    assert vac_a_only[0]["vacancy_ref"] == "vac-a"


def test_submit_without_username_leaves_external_url_empty(client, auth_headers):
    submit = client.post(
        "/telegram/applications",
        json={"telegram_user_id": 322, "telegram_full_name": "No Username Here"},
        headers=auth_headers,
    ).json()

    candidate = client.get(f"/external-candidates/{submit['external_candidate_id']}", headers=auth_headers).json()

    assert candidate["sources"][0]["external_url"] is None
