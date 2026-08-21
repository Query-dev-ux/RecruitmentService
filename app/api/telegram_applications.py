from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_service_token
from app.db.base import get_db
from app.schemas.telegram_application import TelegramApplicationIn, TelegramApplicationOut
from app.services.telegram_intake import handle_telegram_application

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/applications", response_model=TelegramApplicationOut, status_code=status.HTTP_201_CREATED)
async def submit_telegram_application(
    payload: TelegramApplicationIn,
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    application, scored_count = await handle_telegram_application(
        db,
        telegram_user_id=payload.telegram_user_id,
        vacancy_ref=payload.vacancy_ref,
        candidate_text=payload.candidate_text,
        resume_file_ref=payload.resume_file_ref,
    )
    return TelegramApplicationOut(
        telegram_application_id=application.id,
        external_candidate_id=application.external_candidate_id,
        scored_against_templates=scored_count,
    )
