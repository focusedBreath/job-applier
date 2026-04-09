from abc import ABC, abstractmethod

import structlog

from src.ai.client import AIClient
from src.queue.models import JobListing
from src.resume.models import ResumeData
from src.utils.browser import BrowserManager

log = structlog.get_logger()


class BaseApplier(ABC):
    def __init__(
        self,
        browser: BrowserManager,
        ai: AIClient,
        resume: ResumeData,
    ) -> None:
        self.browser = browser
        self.ai = ai
        self.resume = resume

    @abstractmethod
    async def apply(self, job: JobListing) -> bool:
        """Submit application. Returns True on success."""
        ...

    def _resume_value(self, field_label: str) -> str:
        """Best-effort lookup of a resume field by label keyword."""
        label = field_label.lower()
        if "name" in label:
            return self.resume.name
        if "email" in label:
            return self.resume.email
        if "phone" in label:
            return self.resume.phone
        if "location" in label or "city" in label or "address" in label:
            return self.resume.location
        if "linkedin" in label:
            return self.resume.linkedin
        if "github" in label:
            return self.resume.github
        if "summary" in label or "objective" in label:
            return self.resume.summary
        return ""
