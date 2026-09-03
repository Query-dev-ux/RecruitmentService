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
            "via": None,
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


async def test_list_filters_by_via(client, auth_headers, db_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models.enums import DiscoveryChannel, SourceType
    from app.repositories import candidates as repo

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        await repo.get_or_create_candidate(
            session,
            source=SourceType.HH,
            external_id="res-search",
            external_url=None,
            raw_data={},
            parsed_profile={},
            via=DiscoveryChannel.SEARCH,
        )
        await repo.get_or_create_candidate(
            session,
            source=SourceType.HH,
            external_id="res-negotiation",
            external_url=None,
            raw_data={},
            parsed_profile={},
            via=DiscoveryChannel.NEGOTIATION,
        )

    search_only = client.get("/external-candidates", params={"via": "search"}, headers=auth_headers).json()
    negotiation_only = client.get(
        "/external-candidates", params={"via": "negotiation"}, headers=auth_headers
    ).json()

    assert len(search_only) == 1
    assert search_only[0]["sources"][0]["external_id"] == "res-search"
    assert len(negotiation_only) == 1
    assert negotiation_only[0]["sources"][0]["external_id"] == "res-negotiation"


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


def test_new_candidate_starts_pending(client, auth_headers):
    submit = client.post("/telegram/applications", json={"telegram_user_id": 500}, headers=auth_headers).json()

    candidate = client.get(f"/external-candidates/{submit['external_candidate_id']}", headers=auth_headers).json()

    assert candidate["review_status"] == "pending"
    assert candidate["reviewed_at"] is None
    assert candidate["reviewed_by"] is None


def test_review_candidate_marks_added(client, auth_headers):
    submit = client.post("/telegram/applications", json={"telegram_user_id": 501}, headers=auth_headers).json()
    candidate_id = submit["external_candidate_id"]

    response = client.patch(
        f"/external-candidates/{candidate_id}/review",
        json={"decision": "added", "reviewed_by": "hr@company.com"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "added"
    assert body["reviewed_by"] == "hr@company.com"
    assert body["reviewed_at"] is not None


def test_review_candidate_can_be_undone_back_to_pending(client, auth_headers):
    submit = client.post("/telegram/applications", json={"telegram_user_id": 502}, headers=auth_headers).json()
    candidate_id = submit["external_candidate_id"]
    client.patch(f"/external-candidates/{candidate_id}/review", json={"decision": "skipped"}, headers=auth_headers)

    response = client.patch(f"/external-candidates/{candidate_id}/review", json={"decision": "pending"}, headers=auth_headers)

    assert response.json()["review_status"] == "pending"


def test_review_unknown_candidate_returns_404(client, auth_headers):
    response = client.patch(
        "/external-candidates/00000000-0000-0000-0000-000000000000/review",
        json={"decision": "added"},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_review_requires_auth(client):
    response = client.patch(
        "/external-candidates/00000000-0000-0000-0000-000000000000/review", json={"decision": "added"}
    )

    assert response.status_code == 401


def test_list_filters_by_review_status(client, auth_headers):
    added = client.post("/telegram/applications", json={"telegram_user_id": 600}, headers=auth_headers).json()
    client.post("/telegram/applications", json={"telegram_user_id": 601}, headers=auth_headers)
    client.patch(
        f"/external-candidates/{added['external_candidate_id']}/review",
        json={"decision": "added"},
        headers=auth_headers,
    )

    pending = client.get("/external-candidates", params={"review_status": "pending"}, headers=auth_headers).json()
    added_list = client.get("/external-candidates", params={"review_status": "added"}, headers=auth_headers).json()

    assert len(pending) == 1
    assert len(added_list) == 1
    assert added_list[0]["id"] == added["external_candidate_id"]
