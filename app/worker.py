"""Combined worker + scheduler process.

Two loops run side by side:
- `_poll_loop` claims queued search_runs (SELECT ... FOR UPDATE SKIP
  LOCKED — safe under multiple worker replicas) and drives them through
  services.search_execution.execute_search_run against a real HH connection.
- `_scheduler_loop` periodically enqueues a new (trigger=SCHEDULED)
  search_run for every active template with auto_search_enabled=True whose
  next_run_at has arrived, unless it already has one in flight.

NOT exercised against a live HH account or Postgres in this environment —
`process_one_run`'s guard clauses and `schedule_due_templates` are
unit-tested against SQLite; the outer signal-driven loops (poll interval
timing, mid-run-cancellation-on-shutdown) are not, since that needs a real
multi-run deployment to meaningfully verify.
"""

import asyncio
import signal
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.base import SessionLocal
from app.db.models import ProviderAccount, ProviderToken, SearchRun, SearchTemplate
from app.db.models.enums import ProviderAccountStatus, ProviderType, SearchRunStatus, SearchRunTrigger
from app.logging_config import configure_logging, get_logger, log_event
from app.providers.hh.client import HHClient
from app.providers.hh.resumes import iter_all_resumes
from app.repositories import search_runs as search_runs_repo
from app.services.search_execution import execute_search_run

configure_logging()
logger = get_logger(__name__)

POLL_INTERVAL_SECONDS = 5.0
SCHEDULER_INTERVAL_SECONDS = 30.0
DEFAULT_INTERVAL_MINUTES = 60


async def get_connected_hh_access_token(db) -> Optional[str]:
    result = await db.execute(
        select(ProviderToken)
        .join(ProviderAccount, ProviderToken.provider_account_id == ProviderAccount.id)
        .where(
            ProviderAccount.provider == ProviderType.HH,
            ProviderAccount.status == ProviderAccountStatus.CONNECTED,
        )
        .order_by(ProviderToken.created_at.desc())
        .limit(1)
    )
    token = result.scalar_one_or_none()
    return token.access_token if token else None


async def process_one_run(db, run_id: uuid.UUID) -> None:
    run = await search_runs_repo.get_search_run(db, run_id)
    if run is None:
        return

    template_result = await db.execute(
        select(SearchTemplate)
        .options(selectinload(SearchTemplate.criteria))
        .where(SearchTemplate.id == run.search_template_id)
    )
    template = template_result.scalar_one_or_none()
    if template is None:
        await search_runs_repo.mark_failed(db, run, error_message="search_template no longer exists")
        log_event(logger, "SEARCH_FAILED", level="error", search_run_id=str(run.id), error="template_missing")
        return

    access_token = await get_connected_hh_access_token(db)
    if access_token is None:
        await search_runs_repo.mark_failed(
            db, run, error_message="No connected HH account — see GET /providers/hh/status"
        )
        log_event(logger, "SEARCH_FAILED", level="error", search_run_id=str(run.id), error="no_connected_hh_account")
        return

    async with HHClient(access_token) as client:

        async def fetch_resumes(params: dict):
            async for resume_summary in iter_all_resumes(client, params):
                yield resume_summary

        await execute_search_run(db, run, template, fetch_resumes)


async def _has_pending_run(db, search_template_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(SearchRun.id)
        .where(
            SearchRun.search_template_id == search_template_id,
            SearchRun.status.in_([SearchRunStatus.QUEUED, SearchRunStatus.RUNNING]),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def schedule_due_templates(db) -> list[uuid.UUID]:
    """Enqueues a SCHEDULED search_run for every active,
    auto_search_enabled template whose next_run_at has arrived (or was
    never set) and that has no run already queued/running. Returns the ids
    it enqueued for — used directly by tests and by the scheduler loop."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SearchTemplate).where(
            SearchTemplate.is_active.is_(True), SearchTemplate.auto_search_enabled.is_(True)
        )
    )
    enqueued: list[uuid.UUID] = []

    for template in result.scalars().all():
        if template.next_run_at is not None and template.next_run_at > now:
            continue
        if await _has_pending_run(db, template.id):
            continue

        await search_runs_repo.create_search_run(
            db, search_template_id=template.id, trigger=SearchRunTrigger.SCHEDULED
        )
        template.next_run_at = now + timedelta(minutes=template.interval_minutes or DEFAULT_INTERVAL_MINUTES)
        await db.commit()
        enqueued.append(template.id)
        log_event(logger, "SCHEDULED_SEARCH_ENQUEUED", search_template_id=str(template.id))

    return enqueued


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with SessionLocal() as db:
                await schedule_due_templates(db)
        except Exception as exc:
            log_event(logger, "SCHEDULER_TICK_FAILED", level="error", error=str(exc))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=SCHEDULER_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass


async def _poll_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        async with SessionLocal() as claim_db:
            claimed = await search_runs_repo.claim_next_queued(claim_db)

        if claimed is None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
            continue

        run_id = claimed.id

        async def _run() -> None:
            async with SessionLocal() as db:
                await process_one_run(db, run_id)

        task = asyncio.ensure_future(_run())
        stop_wait = asyncio.ensure_future(stop_event.wait())
        done, _pending = await asyncio.wait({task, stop_wait}, return_when=asyncio.FIRST_COMPLETED)

        if task in done:
            stop_wait.cancel()
            exc = task.exception()
            if exc is not None:
                log_event(logger, "SEARCH_FAILED", level="error", search_run_id=str(run_id), error=str(exc))
            continue

        # Shutdown requested mid-run: cancel it and put the run back to
        # queued (not failed) so it gets retried on next startup.
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        async with SessionLocal() as reset_db:
            reset_run = await search_runs_repo.get_search_run(reset_db, run_id)
            if reset_run is not None:
                await search_runs_repo.reset_to_queued(reset_db, reset_run)
        log_event(logger, "SEARCH_RUN_RESET_ON_SHUTDOWN", search_run_id=str(run_id))


async def main() -> None:
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    log_event(logger, "WORKER_STARTED")
    try:
        await asyncio.gather(_poll_loop(stop_event), _scheduler_loop(stop_event))
    finally:
        log_event(logger, "WORKER_STOPPED")


if __name__ == "__main__":
    asyncio.run(main())
