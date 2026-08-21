from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TelegramApplicationIn(BaseModel):
    telegram_user_id: int
    vacancy_ref: Optional[str] = Field(default=None, max_length=255)
    candidate_text: Optional[str] = None
    # A reference (e.g. a Telegram file_id, or a URL) — not a binary upload.
    # Real file storage depends on CRM's own upload mechanism, which we
    # don't have visibility into yet; this field is a placeholder until
    # that's known.
    resume_file_ref: Optional[str] = Field(default=None, max_length=500)


class TelegramApplicationOut(BaseModel):
    telegram_application_id: UUID
    external_candidate_id: UUID
    scored_against_templates: int
