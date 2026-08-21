import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.enums import SearchRunStatus, SearchRunTrigger
from app.repositories import search_runs as repo


@pytest.fixture
async def db_session(db_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_claim_next_queued_returns_none_when_empty(db_session: AsyncSession):
    run = await repo.claim_next_queued(db_session)

    assert run is None


async def test_claim_next_queued_marks_running_and_sets_started_at(db_session: AsyncSession):
    template_id = uuid.uuid4()
    created = await repo.create_search_run(db_session, search_template_id=template_id, trigger=SearchRunTrigger.MANUAL)

    claimed = await repo.claim_next_queued(db_session)

    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status == SearchRunStatus.RUNNING
    assert claimed.started_at is not None


async def test_claim_next_queued_skips_already_running_runs(db_session: AsyncSession):
    template_id = uuid.uuid4()
    await repo.create_search_run(db_session, search_template_id=template_id, trigger=SearchRunTrigger.MANUAL)
    first_claim = await repo.claim_next_queued(db_session)
    second_claim = await repo.claim_next_queued(db_session)

    assert first_claim is not None
    assert second_claim is None


async def test_mark_completed_sets_status_and_stats(db_session: AsyncSession):
    template_id = uuid.uuid4()
    created = await repo.create_search_run(db_session, search_template_id=template_id, trigger=SearchRunTrigger.MANUAL)

    await repo.mark_completed(db_session, created, stats={"found": 5})

    refreshed = await repo.get_search_run(db_session, created.id)
    assert refreshed.status == SearchRunStatus.COMPLETED
    assert refreshed.stats == {"found": 5}
    assert refreshed.finished_at is not None


async def test_mark_failed_sets_error_message(db_session: AsyncSession):
    template_id = uuid.uuid4()
    created = await repo.create_search_run(db_session, search_template_id=template_id, trigger=SearchRunTrigger.MANUAL)

    await repo.mark_failed(db_session, created, error_message="boom")

    refreshed = await repo.get_search_run(db_session, created.id)
    assert refreshed.status == SearchRunStatus.FAILED
    assert refreshed.error_message == "boom"


async def test_reset_to_queued_after_running(db_session: AsyncSession):
    template_id = uuid.uuid4()
    created = await repo.create_search_run(db_session, search_template_id=template_id, trigger=SearchRunTrigger.MANUAL)
    claimed = await repo.claim_next_queued(db_session)

    await repo.reset_to_queued(db_session, claimed)

    refreshed = await repo.get_search_run(db_session, created.id)
    assert refreshed.status == SearchRunStatus.QUEUED
    assert refreshed.started_at is None
