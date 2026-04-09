from abc import ABC, abstractmethod

import structlog

from src.queue.models import JobListing, Platform
from src.utils.browser import BrowserManager

log = structlog.get_logger()


class BaseScraper(ABC):
    platform: Platform

    def __init__(self, browser: BrowserManager, email: str, password: str) -> None:
        self.browser = browser
        self.email = email
        self.password = password

    @abstractmethod
    async def scrape(
        self,
        keywords: list[str],
        locations: list[str],
        days_back: int,
    ) -> list[JobListing]:
        ...

    def _make_job(self, **kwargs) -> JobListing:
        return JobListing(platform=self.platform, **kwargs)
