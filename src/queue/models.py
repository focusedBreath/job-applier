from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    DICE = "dice"
    MONSTER = "monster"


class JobListing(BaseModel):
    id: int | None = None
    title: str
    company: str
    location: str
    url: str
    platform: Platform
    description: str = ""
    salary: str = ""
    posted_date: str = ""
    status: JobStatus = JobStatus.PENDING
    added_at: datetime | None = None
    applied_at: datetime | None = None
    skip_reason: str = ""
    error: str = ""
    ai_reason: str = ""

    model_config = {"use_enum_values": True}


class JobStats(BaseModel):
    total: int
    pending: int
    applied: int
    skipped: int
    failed: int
    by_platform: dict[str, int]
