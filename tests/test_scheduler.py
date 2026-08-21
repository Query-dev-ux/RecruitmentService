from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import SearchTemplate
from app.db.models.enums import SearchRunTrigger
from app.repositories import search_runs as search_runs_repo
from app.worker import schedule_due_templates


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_schedules_template_with_no_next_run_at_yet(db_session: AsyncSession):
    template = SearchTemplate(name="Auto", is_active=True, auto_search_enabled=True, interval_minutes=30)
    db_session.add(template)
    await db_session.commit()

    enqueued = await schedule_due_templates(db_session)

    assert enqueued == [template.id]
    runs = await search_runs_repo.list_search_runs(db_session, search_template_id=template.id)
    assert len(runs) == 1
    assert runs[0].trigger == SearchRunTrigger.SCHEDULED
    await db_session.refresh(template)
    assert template.next_run_at is not None


async def test_does_not_schedule_when_next_run_at_in_future(db_session: AsyncSession):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    template = SearchTemplate(
        name="Auto", is_active=True, auto_search_enabled=True, interval_minutes=30, next_run_at=future
    )
    db_session.add(template)
    await db_session.commit()

    enqueued = await schedule_due_templates(db_session)

    assert enqueued == []


async def test_schedules_when_next_run_at_in_past(db_session: AsyncSession):
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    template = SearchTemplate(
        name="Auto", is_active=True, auto_search_enabled=True, interval_minutes=30, next_run_at=past
    )
    db_session.add(template)
    await db_session.commit()

    enqueued = await schedule_due_templates(db_session)

    assert enqueued == [template.id]


async def test_ignores_inactive_templates(db_session: AsyncSession):
    template = SearchTemplate(name="Auto", is_active=False, auto_search_enabled=True, interval_minutes=30)
    db_session.add(template)
    await db_session.commit()

    enqueued = await schedule_due_templates(db_session)

    assert enqueued == []


async def test_ignores_templates_with_auto_search_disabled(db_session: AsyncSession):
    template = SearchTemplate(name="Manual only", is_active=True, auto_search_enabled=False)
    db_session.add(template)
    await db_session.commit()

    enqueued = await schedule_due_templates(db_session)

    assert enqueued == []


async def test_does_not_double_schedule_while_a_run_is_pending(db_session: AsyncSession):
    template = SearchTemplate(name="Auto", is_active=True, auto_search_enabled=True, interval_minutes=30)
    db_session.add(template)
    await db_session.commit()

    first = await schedule_due_templates(db_session)
    # next_run_at was just pushed into the future, so a second tick
    # shouldn't enqueue again even without the pending-run check kicking in —
    # but force next_run_at back to "due" to specifically exercise that check.
    template.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()
    second = await schedule_due_templates(db_session)

    assert first == [template.id]
    assert second == []  # the first run is still queued, so no duplicate
    runs = await search_runs_repo.list_search_runs(db_session, search_template_id=template.id)
    assert len(runs) == 1


async def test_next_run_at_uses_default_interval_when_unset(db_session: AsyncSession):
    template = SearchTemplate(name="Auto", is_active=True, auto_search_enabled=True, interval_minutes=None)
    db_session.add(template)
    await db_session.commit()

    before = datetime.now(timezone.utc)
    await schedule_due_templates(db_session)
    await db_session.refresh(template)

    # SQLite (test-only) doesn't round-trip tzinfo on DateTime(timezone=True)
    # columns the way Postgres does — normalize before comparing.
    next_run_at = template.next_run_at
    if next_run_at.tzinfo is None:
        next_run_at = next_run_at.replace(tzinfo=timezone.utc)
    assert next_run_at > before + timedelta(minutes=59)
