from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..utils.logger import log


@dataclass
class JobListing:
    id: str
    title: str
    company: str
    location: str
    url: str
    posted_date: Optional[str] = None
    description: str = ""
    platform: str = ""
    salary: Optional[str] = None
    job_type: Optional[str] = None
    is_easy_apply: bool = False
    is_workday: bool = False
    seniority: Optional[str] = None

    def matches_keywords(self, keywords: list[str]) -> bool:
        search_text = f"{self.title} {self.description} {self.company}".lower()
        return any(kw.lower() in search_text for kw in keywords)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "posted_date": self.posted_date,
            "description": self.description[:500] + "..."
            if len(self.description) > 500
            else self.description,
            "platform": self.platform,
            "salary": self.salary,
            "job_type": self.job_type,
            "is_easy_apply": self.is_easy_apply,
            "is_workday": self.is_workday,
        }


class BaseScraper(ABC):
    def __init__(self, name: str):
        self.name = name
        self.jobs: list[JobListing] = []

    @abstractmethod
    def search(
        self, keywords: list[str], location: str, days_back: int = 7
    ) -> list[JobListing]:
        pass

    @abstractmethod
    def login(self, email: str, password: str) -> bool:
        pass

    def is_logged_in(self) -> bool:
        return False

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        try:
            from datetime import timedelta

            date_str_lower = date_str.lower().strip()

            if "today" in date_str_lower or "just posted" in date_str_lower:
                return datetime.now()
            if "yesterday" in date_str_lower:
                return datetime.now() - timedelta(days=1)

            days_match = None
            for suffix in ["d ago", " days ago", "day ago"]:
                if suffix in date_str_lower:
                    try:
                        days = int(
                            date_str_lower.replace(suffix, "").strip().split()[-1]
                        )
                        days_match = datetime.now() - timedelta(days=days)
                        break
                    except:
                        pass

            if days_match:
                return days_match

            hours_match = None
            for suffix in ["h ago", " hour ago", "hours ago"]:
                if suffix in date_str_lower:
                    try:
                        hours = int(
                            date_str_lower.replace(suffix, "").strip().split()[-1]
                        )
                        hours_match = datetime.now() - timedelta(hours=hours)
                        break
                    except:
                        pass

            return hours_match

        except Exception as e:
            log.warning(f"Failed to parse date '{date_str}': {e}")
            return None

    def _is_recent(self, date_str: Optional[str], days_back: int) -> bool:
        if not date_str:
            return True

        parsed = self._parse_date(date_str)
        if not parsed:
            return True

        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days_back)
        return parsed >= cutoff

    def get_jobs(self) -> list[JobListing]:
        return self.jobs

    def clear_jobs(self):
        self.jobs = []
