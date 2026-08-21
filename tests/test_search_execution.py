import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import SearchTemplate, SearchTemplateCriterion
from app.db.models.enums import CriterionMode, SearchRunTrigger
from app.repositories import search_runs as search_runs_repo
from app.services.search_execution import execute_search_run


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def _make_template(db_session, criteria):
    template = SearchTemplate(name="Media Buyer", criteria=criteria)
    db_session.add(template)
    await db_session.commit()
    return template


RESUME_A = {
    "id": "res-1",
    "title": "Media Buyer",
    "alternate_url": "https://hh.ru/resume/res-1",
    "skill_set": ["Facebook Ads", "iGaming", "Keitaro"],
}
RESUME_B = {
    "id": "res-2",
    "title": "SEO specialist",
    "alternate_url": "https://hh.ru/resume/res-2",
    "skill_set": ["SEO"],
}


async def fake_fetch_two(params):
    for resume in (RESUME_A, RESUME_B):
        yield resume


async def test_execute_search_run_scores_and_dedupes(db_session: AsyncSession):
    criteria = [SearchTemplateCriterion(key="vertical", value="igaming", mode=CriterionMode.PREFERRED, weight=100)]
    template = await _make_template(db_session, criteria)
    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )

    await execute_search_run(db_session, run, template, fake_fetch_two)

    refreshed_run = await search_runs_repo.get_search_run(db_session, run.id)
    assert refreshed_run.status.value == "completed"
    assert refreshed_run.stats["found"] == 2
    assert refreshed_run.stats["new"] == 2
    assert refreshed_run.stats["passed_hard_filters"] == 2  # no REQUIRED criteria here
    assert refreshed_run.stats["above_threshold"] == 1  # only RESUME_A matches "igaming"
    assert template.last_run_at is not None
    assert template.last_success_at is not None
    assert template.last_error is None


async def test_execute_search_run_marks_template_last_error_on_failure(db_session: AsyncSession):
    template = await _make_template(db_session, [])
    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )

    async def broken_fetch(params):
        raise RuntimeError("HH is down")
        yield  # pragma: no cover — keeps this an async generator function

    with pytest.raises(RuntimeError):
        await execute_search_run(db_session, run, template, broken_fetch)

    assert template.last_run_at is not None
    assert template.last_error == "HH is down"


async def test_execute_search_run_is_idempotent_on_rerun(db_session: AsyncSession):
    template = await _make_template(db_session, [])
    run1 = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )
    await execute_search_run(db_session, run1, template, fake_fetch_two)

    run2 = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )
    await execute_search_run(db_session, run2, template, fake_fetch_two)

    refreshed_run2 = await search_runs_repo.get_search_run(db_session, run2.id)
    assert refreshed_run2.stats["found"] == 2
    assert refreshed_run2.stats["new"] == 0  # both already known from run1 — no duplicate candidates created
    assert refreshed_run2.stats["known"] == 2


async def test_execute_search_run_applies_required_hard_filter(db_session: AsyncSession):
    criteria = [SearchTemplateCriterion(key="vertical", value="crypto", mode=CriterionMode.REQUIRED, weight=0)]
    template = await _make_template(db_session, criteria)
    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )

    await execute_search_run(db_session, run, template, fake_fetch_two)

    refreshed_run = await search_runs_repo.get_search_run(db_session, run.id)
    assert refreshed_run.stats["passed_hard_filters"] == 0  # neither resume mentions "crypto"


async def test_execute_search_run_marks_failed_on_provider_error(db_session: AsyncSession):
    template = await _make_template(db_session, [])
    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )

    async def broken_fetch(params):
        raise RuntimeError("HH is down")
        yield  # pragma: no cover — keeps this an async generator function

    with pytest.raises(RuntimeError):
        await execute_search_run(db_session, run, template, broken_fetch)

    refreshed_run = await search_runs_repo.get_search_run(db_session, run.id)
    assert refreshed_run.status.value == "failed"
    assert "HH is down" in refreshed_run.error_message
