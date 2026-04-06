from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from ..scrapers.base_scraper import JobListing
from ..parser.resume_parser import ResumeData
from ..utils.logger import log


@dataclass
class ApplicationResult:
    success: bool
    job_listing: JobListing
    timestamp: str
    message: str = ""
    form_filled: dict = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.form_filled is None:
            self.form_filled = {}


class BaseApplier(ABC):
    def __init__(self, name: str):
        self.name = name
        self.results: list[ApplicationResult] = []

    @abstractmethod
    def apply(self, job: JobListing, resume: ResumeData) -> ApplicationResult:
        pass

    def record_result(self, result: ApplicationResult):
        self.results.append(result)
        if result.success:
            log.info(
                f"Application submitted: {result.job_listing.title} at {result.job_listing.company}"
            )
        else:
            log.warning(
                f"Application failed: {result.job_listing.title} - {result.error}"
            )

    def get_results(self) -> list[ApplicationResult]:
        return self.results

    def get_success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    def get_failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)
