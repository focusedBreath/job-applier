import json
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from .config import Config, load_config
from .parser.resume_parser import ResumeParser, ResumeData
from .browser.browser_manager import BrowserManager
from .scrapers.linkedin_scraper import LinkedInScraper
from .scrapers.indeed_scraper import IndeedScraper
from .scrapers.monster_scraper import MonsterScraper
from .scrapers.dice_scraper import DiceScraper
from .scrapers.base_scraper import JobListing
from .appliers.linkedin_applier import LinkedInApplier
from .appliers.workday_applier import WorkdayApplier
from .appliers.generic_applier import GenericApplier
from .ai.ai_overseer import AIOversight, create_ai_overseer
from .ai.ai_handler import LMStudioManager
from .utils.rate_limiter import AdaptiveRateLimiter
from .utils.logger import log


@dataclass
class SearchResult:
    platform: str
    jobs_found: int
    jobs_filtered: int
    timestamp: str


@dataclass
class ApplicationSession:
    config: Config
    resume: ResumeData
    searches: list[SearchResult] = field(default_factory=list)
    applications: list[dict] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "config": {
                "search_keywords": self.config.search.keywords,
                "search_locations": self.config.search.locations,
            },
            "resume_name": self.resume.personal.name,
            "resume_email": self.resume.personal.email,
            "searches": [s.__dict__ for s in self.searches],
            "applications": self.applications,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class JobApplierOrchestrator:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.browser_manager: Optional[BrowserManager] = None
        self.ai_overseer: Optional[AIOversight] = None
        self.rate_limiter: Optional[AdaptiveRateLimiter] = None
        self.resume: Optional[ResumeData] = None
        self.session: Optional[ApplicationSession] = None

    def initialize(self):
        log.info("Initializing Job Applier...")

        self.browser_manager = BrowserManager(self.config.browser)

        ai_config_dict = {
            "ai": {
                "enabled": self.config.ai.enabled,
                "endpoint": self.config.ai.endpoint,
                "model": self.config.ai.model,
                "pause_for_approval": self.config.ai.pause_for_approval,
                "startup_timeout": self.config.ai.startup_timeout,
            }
        }
        self.ai_overseer = create_ai_overseer(ai_config_dict)

        self.rate_limiter = AdaptiveRateLimiter(
            min_delay=self.config.limits.min_delay,
            max_delay=self.config.limits.max_delay,
            max_per_day=self.config.limits.applications_per_day,
        )

        resume_path = self.config.resume.docx_path
        if not resume_path:
            log.error("No resume path configured")
            return False

        parser = ResumeParser(resume_path)
        self.resume = parser.extract_all()

        if not self.resume.personal.name:
            log.error("Failed to extract name from resume")
            return False

        log.info(f"Resume loaded: {self.resume.personal.name}")
        log.info(f"Email: {self.resume.personal.email}")
        log.info(f"Phone: {self.resume.personal.phone}")
        log.info(f"Skills found: {len(self.resume.skills)}")
        log.info(f"Certifications: {', '.join(self.resume.certifications[:5])}")

        self.session = ApplicationSession(
            config=self.config,
            resume=self.resume,
        )

        return True

    def search_all_platforms(self, dry_run: bool = False) -> list[JobListing]:
        all_jobs = []

        self.browser_manager.start()

        platforms = [
            ("LinkedIn", LinkedInScraper),
            ("Indeed", IndeedScraper),
            ("Monster", MonsterScraper),
            ("Dice", DiceScraper),
        ]

        delay_range = (
            self.config.limits.scraper_delay_min,
            self.config.limits.scraper_delay_max,
        )

        for platform_name, scraper_class in platforms:
            if dry_run:
                log.info(f"[DRY RUN] Would search {platform_name}")
                continue

            try:
                scraper = scraper_class(self.browser_manager, delay_range=delay_range)

                if (
                    platform_name == "LinkedIn"
                    and self.config.credentials.linkedin_email
                ):
                    scraper.login(
                        self.config.credentials.linkedin_email,
                        self.config.credentials.linkedin_password,
                    )
                elif platform_name == "Indeed" and self.config.credentials.indeed_email:
                    scraper.login(
                        self.config.credentials.indeed_email,
                        self.config.credentials.indeed_password or "",
                    )

                for location in self.config.search.locations:
                    jobs = scraper.search(
                        keywords=self.config.search.keywords,
                        location=location,
                        days_back=self.config.search.days_back,
                    )
                    all_jobs.extend(jobs)

                    self.session.searches.append(
                        SearchResult(
                            platform=platform_name,
                            jobs_found=len(jobs),
                            jobs_filtered=0,
                            timestamp=datetime.now().isoformat(),
                        )
                    )

            except Exception as e:
                log.error(f"Error searching {platform_name}: {e}")

        unique_jobs = self._deduplicate_jobs(all_jobs)
        log.info(f"Total unique jobs found: {len(unique_jobs)}")

        return unique_jobs

    def _deduplicate_jobs(self, jobs: list[JobListing]) -> list[JobListing]:
        seen_urls = set()
        unique = []

        for job in jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique.append(job)

        return unique

    def apply_to_jobs(
        self,
        jobs: list[JobListing],
        platforms: Optional[list[str]] = None,
        dry_run: bool = False,
    ):
        if dry_run:
            log.info(f"[DRY RUN] Would apply to {len(jobs)} jobs")
            for job in jobs[:5]:
                log.info(f"  - {job.title} at {job.company} ({job.platform})")
            if len(jobs) > 5:
                log.info(f"  ... and {len(jobs) - 5} more")
            return

        linkedin_applier = LinkedInApplier(self.browser_manager, self.ai_overseer)
        workday_applier = WorkdayApplier(self.browser_manager, self.ai_overseer)
        generic_applier = GenericApplier(self.browser_manager, self.ai_overseer)

        if (
            self.config.credentials.linkedin_email
            and self.config.credentials.linkedin_password
        ):
            linkedin_scraper = LinkedInScraper(self.browser_manager)
            if linkedin_scraper.login(
                self.config.credentials.linkedin_email,
                self.config.credentials.linkedin_password,
            ):
                log.info("LinkedIn login successful")
            else:
                log.warning("LinkedIn login failed - will attempt without login")

        for i, job in enumerate(jobs, 1):
            log.info(f"Processing job {i}/{len(jobs)}: {job.title}")

            wait_time = self.rate_limiter.wait_if_needed()
            if wait_time < 0:
                log.warning("Daily application limit reached")
                break

            self.ai_overseer.report_status(
                f"Applying to: {job.title} ({i}/{len(jobs)})"
            )

            try:
                if job.is_workday or "workday" in job.url.lower():
                    result = workday_applier.apply(job, self.resume)
                elif job.is_easy_apply or job.platform == "LinkedIn":
                    result = linkedin_applier.apply(job, self.resume)
                else:
                    result = generic_applier.apply(job, self.resume)

                self.session.applications.append(
                    {
                        "job_title": job.title,
                        "company": job.company,
                        "platform": job.platform,
                        "url": job.url,
                        "success": result.success,
                        "timestamp": result.timestamp,
                        "message": result.message,
                        "error": result.error,
                    }
                )

                if result.success:
                    self.rate_limiter.record_success()
                else:
                    self.rate_limiter.record_error()

            except Exception as e:
                log.error(f"Error applying to job: {e}")
                self.rate_limiter.record_error()
                self.session.applications.append(
                    {
                        "job_title": job.title,
                        "company": job.company,
                        "platform": job.platform,
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        self.session.completed_at = datetime.now().isoformat()
        self._save_session_report()

    def _save_session_report(self):
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"session_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(self.session.to_dict(), f, indent=2)

        log.info(f"Session report saved to {report_file}")

        success_count = sum(1 for a in self.session.applications if a.get("success"))
        log.info(
            f"Session summary: {success_count}/{len(self.session.applications)} applications successful"
        )

    def cleanup(self):
        if self.ai_overseer:
            self.ai_overseer.cleanup()
        if self.browser_manager:
            self.browser_manager.close()
        log.info("Cleanup complete")

    def run(
        self,
        search_only: bool = False,
        apply: bool = True,
        dry_run: bool = False,
        platforms: Optional[list[str]] = None,
    ):
        try:
            if not self.initialize():
                log.error("Initialization failed")
                return False

            if self.config.ai.enabled:
                log.info("Ensuring AI is ready...")
                try:
                    if self.ai_overseer.ensure_ai_ready(self.resume):
                        log.info("AI ready and primed")
                    else:
                        log.warning("AI not available - will continue without AI")
                except Exception as e:
                    log.warning(f"AI initialization error: {e} - continuing without AI")

            jobs = self.search_all_platforms(dry_run=dry_run)

            if search_only:
                log.info("Search complete - exiting (search_only mode)")
                return True

            if not jobs:
                log.warning("No jobs found")
                return True

            if apply and not dry_run:
                self.apply_to_jobs(jobs, platforms=platforms)

            return True

        finally:
            self.cleanup()


def run_cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="AI-Powered Job Application Automation"
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--search-only", action="store_true", help="Only search, don't apply"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually submit applications"
    )
    parser.add_argument("--platforms", nargs="+", help="Specific platforms to use")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )

    args = parser.parse_args()

    orchestrator = JobApplierOrchestrator(config_path=args.config)

    if args.headless:
        orchestrator.config.browser.headless = True

    orchestrator.run(
        search_only=args.search_only,
        apply=not args.search_only,
        dry_run=args.dry_run,
        platforms=args.platforms,
    )


if __name__ == "__main__":
    run_cli()
