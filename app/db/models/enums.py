import enum


class CriterionMode(str, enum.Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    IGNORE = "ignore"


class SearchRunTrigger(str, enum.Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class SearchRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, enum.Enum):
    HH = "hh"
    TELEGRAM = "telegram"


class ScoreTier(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HOT = "hot"


class TelegramSyncStatus(str, enum.Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


class ProviderType(str, enum.Enum):
    HH = "hh"


class ProviderAccountStatus(str, enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ReviewStatus(str, enum.Enum):
    """HR's triage decision on a raw finding (search result or inbound
    response) — NOT the hiring pipeline itself, which stays entirely in CRM
    once a candidate is ADDED. See docs/API_INTEGRATION.md."""

    PENDING = "pending"
    ADDED = "added"
    SKIPPED = "skipped"
