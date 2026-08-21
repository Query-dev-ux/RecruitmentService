import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchRun
from app.db.models.enums import SearchRunStatus, SearchRunTrigger


async def create_search_run(db: AsyncSession, *, search_template_id: uuid.UUID, trigger: SearchRunTrigger) -> SearchRun:
    run = SearchRun(search_template_id=search_template_id, trigger=trigger, status=SearchRunStatus.QUEUED)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def get_search_run(db: AsyncSession, run_id: uuid.UUID) -> Optional[SearchRun]:
    return await db.get(SearchRun, run_id)


async def list_search_runs(db: AsyncSession, *, search_template_id: Optional[uuid.UUID] = None) -> list[SearchRun]:
    query = select(SearchRun).order_by(SearchRun.created_at.desc())
    if search_template_id is not None:
        query = query.where(SearchRun.search_template_id == search_template_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def claim_next_queued(db: AsyncSession) -> Optional[SearchRun]:
    """Atomically claims one queued run via SELECT ... FOR UPDATE SKIP
    LOCKED, so re-triggering a search or running multiple worker replicas
    can't process the same run twice. (On SQLite, used only in tests,
    row locking is a no-op — there's no concurrent writer to race with
    there anyway; the same code path still runs Postgres-side.)
    """
    result = await db.execute(
        select(SearchRun)
        .where(SearchRun.status == SearchRunStatus.QUEUED)
        .order_by(SearchRun.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    run.status = SearchRunStatus.RUNNING
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)
    return run


async def mark_completed(db: AsyncSession, run: SearchRun, *, stats: dict) -> None:
    run.status = SearchRunStatus.COMPLETED
    run.finished_at = datetime.now(timezone.utc)
    run.stats = stats
    await db.commit()


async def mark_failed(db: AsyncSession, run: SearchRun, *, error_message: str) -> None:
    run.status = SearchRunStatus.FAILED
    run.finished_at = datetime.now(timezone.utc)
    run.error_message = error_message
    await db.commit()


async def reset_to_queued(db: AsyncSession, run: SearchRun) -> None:
    """Used on graceful worker shutdown — an interrupted RUNNING run goes
    back to queued (not failed) so it gets picked up again."""
    run.status = SearchRunStatus.QUEUED
    run.started_at = None
    await db.commit()
