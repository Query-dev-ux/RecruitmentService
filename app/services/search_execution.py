"""Executes one search_run end to end: HH search -> normalize -> dedup ->
score -> stats.

CRM does not get pushed to from here — CRM and Recruitment each keep their
own Postgres, and CRM's own backend pulls scored candidates from this
service's API (GET /external-candidates) on its own schedule. This function
only needs to leave a correct, queryable result behind.

`fetch_resumes` is injected (rather than hardcoding providers.hh.resumes
here) specifically so this can be tested against a fake async generator
instead of a live HH connection — we don't have approved HH credentials in
this environment yet (app is still under HH's review). The worker binds it
to `providers.hh.resumes.iter_all_resumes` against a real HHClient.
"""

from datetime import datetime, timezone
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SearchRun, SearchTemplate
from app.db.models.enums import SourceType
from app.logging_config import get_logger, log_event
from app.providers.hh.normalize import normalize_resume
from app.providers.hh.search import build_search_params
from app.repositories import candidates as candidates_repo
from app.repositories import search_runs as search_runs_repo
from app.scoring.engine import score_candidate

logger = get_logger(__name__)

ResumeFetcher = Callable[[dict], AsyncIterator[dict]]

DEFAULT_ABOVE_THRESHOLD_TIER = 55  # falls back to this if a template sets no score_thresholds.medium


async def execute_search_run(
    db: AsyncSession,
    search_run: SearchRun,
    template: SearchTemplate,
    fetch_resumes: ResumeFetcher,
) -> None:
    log_event(logger, "SEARCH_STARTED", search_run_id=str(search_run.id), search_template_id=str(template.id))

    stats = {"found": 0, "new": 0, "known": 0, "passed_hard_filters": 0, "above_threshold": 0}
    threshold = (template.score_thresholds or {}).get("medium", DEFAULT_ABOVE_THRESHOLD_TIER)

    try:
        params = build_search_params(template.criteria)

        async for raw_resume in fetch_resumes(params):
            external_id = raw_resume.get("id")
            if not external_id:
                continue
            external_id = str(external_id)

            stats["found"] += 1
            profile = normalize_resume(raw_resume)

            candidate, is_new = await candidates_repo.get_or_create_candidate(
                db,
                source=SourceType.HH,
                external_id=external_id,
                external_url=raw_resume.get("alternate_url"),
                raw_data=raw_resume,
                parsed_profile=profile.model_dump(),
            )
            stats["new" if is_new else "known"] += 1

            if is_new:
                log_event(logger, "CANDIDATE_FOUND", external_candidate_id=str(candidate.id), source="hh", external_id=external_id)
            else:
                log_event(logger, "CANDIDATE_DUPLICATE", external_candidate_id=str(candidate.id), source="hh", external_id=external_id)

            result = score_candidate(profile, template.criteria, template.score_thresholds)
            await candidates_repo.upsert_candidate_score(
                db,
                external_candidate_id=candidate.id,
                search_template_id=template.id,
                score=result.score,
                tier=result.tier,
                breakdown=result.breakdown,
                hard_filters_passed=result.hard_filters_passed,
            )

            if not result.hard_filters_passed:
                continue
            stats["passed_hard_filters"] += 1
            if result.score >= threshold:
                stats["above_threshold"] += 1

        now = datetime.now(timezone.utc)
        template.last_run_at = now
        template.last_success_at = now
        template.last_error = None
        await search_runs_repo.mark_completed(db, search_run, stats=stats)
        log_event(logger, "SEARCH_COMPLETED", search_run_id=str(search_run.id), **stats)

    except Exception as exc:
        template.last_run_at = datetime.now(timezone.utc)
        template.last_error = str(exc)
        await search_runs_repo.mark_failed(db, search_run, error_message=str(exc))
        log_event(logger, "SEARCH_FAILED", level="error", search_run_id=str(search_run.id), error=str(exc))
        raise
