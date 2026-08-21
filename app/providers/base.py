"""Provider-agnostic candidate shapes.

Every source (HH now, Telegram/others later) normalizes into ParsedProfile,
so the scoring engine never has to know where a candidate came from —
see the plan's "Scoring engine" section.
"""

from typing import Optional, Protocol

from pydantic import BaseModel, Field


class ParsedProfile(BaseModel):
    full_name: Optional[str] = None
    position_title: Optional[str] = None
    total_experience_months: Optional[int] = None
    geo: Optional[str] = None
    employment_type: Optional[str] = None  # full/part/project/... (HH: employment.id)
    work_format: Optional[str] = None  # remote/office/hybrid/... (HH: schedule.id)
    salary_expectation: Optional[int] = None
    salary_currency: Optional[str] = None
    job_search_status: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    last_experience_ended_months_ago: Optional[int] = None

    # Concatenated free text (title, skills, experience descriptions) — used
    # for keyword-style criteria the brief lists (iGaming, Facebook, Keitaro,
    # PWA, ...) that aren't structured HH fields, so scoring can match them
    # regardless of which provider the candidate came from.
    text_blob: str = ""


class RawCandidate(BaseModel):
    source: str  # "hh" | "telegram"
    external_id: str
    external_url: Optional[str] = None
    raw_data: dict


class CandidateSourceProvider(Protocol):
    async def search(self, criteria: list) -> list[RawCandidate]: ...

    def normalize(self, raw: RawCandidate) -> ParsedProfile: ...
