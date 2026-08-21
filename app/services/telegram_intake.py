"""Handles one inbound Telegram application: dedup -> stage it -> score
against any search_template(s) scoped to the same vacancy.

This is the Recruitment Service side of the intake contract only — CGBot
(the existing Telegram bot) is NOT wired to call this yet, by explicit
earlier decision. Nothing calls this endpoint in production today; it
exists so the contract is built and tested ahead of that integration phase.

CRM does not get pushed to from here — see search_execution.py's docstring;
this candidate becomes visible to CRM the same way an HH-sourced one does,
via GET /external-candidates.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import SearchTemplate, TelegramApplication
from app.db.models.enums import SourceType, TelegramSyncStatus
from app.logging_config import get_logger, log_event
from app.providers.telegram.normalize import normalize_telegram_application
from app.repositories import candidates as candidates_repo
from app.scoring.engine import score_candidate

logger = get_logger(__name__)


async def handle_telegram_application(
    db: AsyncSession,
    *,
    telegram_user_id: int,
    vacancy_ref: Optional[str],
    candidate_text: Optional[str],
    resume_file_ref: Optional[str],
) -> tuple[TelegramApplication, int]:
    log_event(logger, "TELEGRAM_APPLICATION_RECEIVED", telegram_user_id=telegram_user_id, vacancy_ref=vacancy_ref)

    profile = normalize_telegram_application(candidate_text)

    candidate, is_new = await candidates_repo.get_or_create_candidate(
        db,
        source=SourceType.TELEGRAM,
        external_id=str(telegram_user_id),
        external_url=None,
        raw_data={"candidate_text": candidate_text, "resume_file_ref": resume_file_ref},
        parsed_profile=profile.model_dump(),
    )
    log_event(
        logger,
        "CANDIDATE_FOUND" if is_new else "CANDIDATE_DUPLICATE",
        external_candidate_id=str(candidate.id),
        source="telegram",
        external_id=str(telegram_user_id),
    )

    application = TelegramApplication(
        telegram_user_id=telegram_user_id,
        vacancy_ref=vacancy_ref,
        candidate_text=candidate_text,
        resume_file_ref=resume_file_ref,
        external_candidate_id=candidate.id,
        sync_status=TelegramSyncStatus.PENDING,
    )
    db.add(application)

    # Score against whichever search_template(s) target this same vacancy,
    # if any — a vacancy can have zero, one, or (in principle) more than one
    # template pointed at it; we score against all of them, same as an
    # HH-sourced candidate would be scored once per template that found it.
    scored_count = 0
    if vacancy_ref:
        result = await db.execute(
            select(SearchTemplate)
            .options(selectinload(SearchTemplate.criteria))
            .where(SearchTemplate.crm_vacancy_id == vacancy_ref)
        )
        for template in result.scalars().all():
            score_result = score_candidate(profile, template.criteria, template.score_thresholds)
            await candidates_repo.upsert_candidate_score(
                db,
                external_candidate_id=candidate.id,
                search_template_id=template.id,
                score=score_result.score,
                tier=score_result.tier,
                breakdown=score_result.breakdown,
                hard_filters_passed=score_result.hard_filters_passed,
            )
            scored_count += 1

    await db.commit()
    await db.refresh(application)

    return application, scored_count
