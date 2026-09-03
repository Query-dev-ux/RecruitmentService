"""Telegram application -> ParsedProfile.

Deliberately minimal: unlike HH, we only ever get free-form candidate_text
(no structured resume) — so only full_name and text_blob are populated.
Structured criteria (experience_level, salary_from, employment_type, ...)
correctly fail closed for Telegram candidates rather than silently passing
on missing data (scoring/engine.py already treats missing profile fields as
non-matches). Extracting structured fields from free text is an
AI-assisted task, explicitly out of scope until the AI phase — see the plan.
"""

from typing import Optional

from app.providers.base import ParsedProfile


def normalize_telegram_application(candidate_text: Optional[str], full_name: Optional[str] = None) -> ParsedProfile:
    return ParsedProfile(full_name=full_name, text_blob=candidate_text or "")
