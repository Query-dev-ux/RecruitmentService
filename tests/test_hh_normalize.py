from datetime import date

from app.providers.hh.normalize import normalize_resume

RESUME_FIXTURE = {
    "title": "Media Buyer (Facebook, iGaming)",
    "first_name": "Иван",
    "last_name": "Иванов",
    "total_experience": {"months": 18},
    "area": {"id": "1", "name": "Москва"},
    "salary": {"amount": 1500, "currency": "USD"},
    "employment": {"id": "full", "name": "Полная занятость"},
    "schedule": {"id": "remote", "name": "Удалённая работа"},
    "job_search_status": {"id": "active_search", "name": "Активно ищет работу"},
    "language": [{"id": "eng", "name": "Английский", "level": {"id": "b2", "name": "B2"}}],
    "skill_set": ["Facebook Ads", "Keitaro", "PWA"],
    "experience": [
        {
            "position": "Media Buyer",
            "company": "iGaming Co",
            "start": "2023-01-01",
            "end": None,
            "description": "Facebook, iGaming, Keitaro, budgets $1000+/day",
        }
    ],
}


def test_normalize_maps_structured_fields():
    profile = normalize_resume(RESUME_FIXTURE)

    assert profile.full_name == "Иванов Иван"
    assert profile.position_title == "Media Buyer (Facebook, iGaming)"
    assert profile.total_experience_months == 18
    assert profile.geo == "Москва"
    assert profile.employment_type == "full"
    assert profile.work_format == "remote"
    assert profile.salary_expectation == 1500
    assert profile.salary_currency == "USD"
    assert profile.job_search_status == "active_search"
    assert profile.languages == ["eng:b2"]
    assert profile.skills == ["Facebook Ads", "Keitaro", "PWA"]


def test_normalize_builds_text_blob_for_keyword_scoring():
    profile = normalize_resume(RESUME_FIXTURE)

    assert "iGaming" in profile.text_blob
    assert "Keitaro" in profile.text_blob
    assert "Facebook Ads" in profile.text_blob


def test_normalize_treats_ongoing_role_as_zero_months_ago():
    profile = normalize_resume(RESUME_FIXTURE)

    assert profile.last_experience_ended_months_ago == 0


def test_normalize_computes_months_since_last_role_ended():
    ended_resume = dict(RESUME_FIXTURE)
    ended_resume["experience"] = [
        {**RESUME_FIXTURE["experience"][0], "end": "2024-01-01"},
    ]

    profile = normalize_resume(ended_resume)

    expected_months = (date.today().year - 2024) * 12 + (date.today().month - 1)
    assert profile.last_experience_ended_months_ago == max(0, expected_months)


def test_normalize_leaves_unmappable_employment_and_schedule_as_none():
    resume = {"employment": {"id": "project"}, "schedule": {"id": "shift"}}

    profile = normalize_resume(resume)

    assert profile.employment_type is None
    assert profile.work_format is None


def test_normalize_handles_missing_optional_fields():
    profile = normalize_resume({"title": "Just a title"})

    assert profile.full_name is None
    assert profile.geo is None
    assert profile.skills == []
    assert profile.languages == []
    assert profile.last_experience_ended_months_ago is None


def test_normalize_ignores_unparseable_experience_end_date():
    resume = {"experience": [{"position": "X", "end": "not-a-date"}]}

    profile = normalize_resume(resume)

    assert profile.last_experience_ended_months_ago is None
