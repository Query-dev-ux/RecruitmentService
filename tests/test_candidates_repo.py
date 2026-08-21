import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.enums import ScoreTier, SourceType
from app.repositories import candidates as repo


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_get_or_create_candidate_creates_new(db_session: AsyncSession):
    candidate, is_new = await repo.get_or_create_candidate(
        db_session,
        source=SourceType.HH,
        external_id="resume-1",
        external_url="https://hh.ru/resume/1",
        raw_data={"id": "resume-1"},
        parsed_profile={"position_title": "Media Buyer"},
    )

    assert is_new is True
    assert candidate.parsed_profile == {"position_title": "Media Buyer"}


async def test_get_or_create_candidate_dedupes_by_source_and_external_id(db_session: AsyncSession):
    first, first_is_new = await repo.get_or_create_candidate(
        db_session,
        source=SourceType.HH,
        external_id="resume-1",
        external_url="https://hh.ru/resume/1",
        raw_data={"id": "resume-1", "title": "v1"},
        parsed_profile={"position_title": "v1"},
    )

    second, second_is_new = await repo.get_or_create_candidate(
        db_session,
        source=SourceType.HH,
        external_id="resume-1",
        external_url="https://hh.ru/resume/1",
        raw_data={"id": "resume-1", "title": "v2"},
        parsed_profile={"position_title": "v2"},
    )

    assert first_is_new is True
    assert second_is_new is False
    assert second.id == first.id
    assert second.parsed_profile == {"position_title": "v2"}  # snapshot refreshed, not duplicated


async def test_different_sources_with_same_external_id_are_distinct_candidates(db_session: AsyncSession):
    hh_candidate, _ = await repo.get_or_create_candidate(
        db_session, source=SourceType.HH, external_id="123", external_url=None, raw_data={}, parsed_profile={}
    )
    tg_candidate, _ = await repo.get_or_create_candidate(
        db_session, source=SourceType.TELEGRAM, external_id="123", external_url=None, raw_data={}, parsed_profile={}
    )

    assert hh_candidate.id != tg_candidate.id


async def test_upsert_candidate_score_creates_then_updates(db_session: AsyncSession):
    candidate, _ = await repo.get_or_create_candidate(
        db_session, source=SourceType.HH, external_id="resume-1", external_url=None, raw_data={}, parsed_profile={}
    )
    template_id = uuid.uuid4()

    created = await repo.upsert_candidate_score(
        db_session,
        external_candidate_id=candidate.id,
        search_template_id=template_id,
        score=40,
        tier=ScoreTier.LOW,
        breakdown={"a": 1},
        hard_filters_passed=True,
    )
    updated = await repo.upsert_candidate_score(
        db_session,
        external_candidate_id=candidate.id,
        search_template_id=template_id,
        score=90,
        tier=ScoreTier.HOT,
        breakdown={"a": 2},
        hard_filters_passed=True,
    )

    assert updated.id == created.id  # same row replaced, not duplicated
    assert updated.score == 90
    assert updated.tier == ScoreTier.HOT
