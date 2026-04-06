import argparse
import time
from pathlib import Path

from .config import load_config
from .parser.resume_parser import ResumeParser
from .browser.browser_manager import BrowserManager
from .appliers.linkedin_applier import LinkedInApplier
from .appliers.workday_applier import WorkdayApplier
from .appliers.generic_applier import GenericApplier
from .ai.ai_overseer import create_ai_overseer
from .queue.job_queue import JobQueue
from .utils.rate_limiter import AdaptiveRateLimiter
from .utils.logger import log


class ApplierCLI:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.browser_manager = BrowserManager(self.config.browser)
        self.queue = JobQueue()
        self.rate_limiter = AdaptiveRateLimiter(
            min_delay=self.config.limits.min_delay,
            max_delay=self.config.limits.max_delay,
            max_per_day=self.config.limits.applications_per_day,
        )

        resume_path = self.config.resume.docx_path
        parser = ResumeParser(resume_path)
        self.resume = parser.extract_all()

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

        self.linkedin_applier = LinkedInApplier(self.browser_manager, self.ai_overseer)
        self.workday_applier = WorkdayApplier(self.browser_manager, self.ai_overseer)
        self.generic_applier = GenericApplier(self.browser_manager, self.ai_overseer)

    def apply_job(self, job) -> bool:
        try:
            page = self.browser_manager.get_page(f"apply_{job.id[:8]}")

            if "workday" in job.url.lower():
                result = self.workday_applier.apply(job, self.resume, page=page)
            elif job.platform == "LinkedIn":
                result = self.linkedin_applier.apply(job, self.resume, page=page)
            else:
                result = self.generic_applier.apply(job, self.resume, page=page)

            self.browser_manager.close_context(f"apply_{job.id[:8]}")

            return result.success

        except Exception as e:
            log.error(f"Error applying to {job.title}: {e}")
            return False

    def run(self, limit: int = 50, platform: str = None, dry_run: bool = False):
        pending_jobs = self.queue.get_pending(limit=limit, platform=platform)

        if not pending_jobs:
            log.info("No pending jobs in queue")
            return 0

        if dry_run:
            log.info(f"[DRY RUN] Would apply to {len(pending_jobs)} jobs:")
            for job in pending_jobs[:10]:
                log.info(f"  - {job.title} @ {job.company} ({job.platform})")
            return 0

        log.info(f"Applying to {len(pending_jobs)} jobs...")

        if self.config.ai.enabled:
            log.info("Ensuring AI is ready...")
            if self.ai_overseer.ensure_ai_ready(self.resume):
                log.info("AI ready")
            else:
                log.warning("AI not available - continuing without AI oversight")

        self.browser_manager.start()

        if self.config.credentials.linkedin_email:
            linkedin_scraper = None
            from .scrapers.linkedin_scraper import LinkedInScraper

            linkedin_scraper = LinkedInScraper(self.browser_manager)
            linkedin_scraper.login(
                self.config.credentials.linkedin_email,
                self.config.credentials.linkedin_password,
            )

        applied = 0
        failed = 0

        for i, job in enumerate(pending_jobs, 1):
            log.info(f"[{i}/{len(pending_jobs)}] {job.title} @ {job.company}")

            wait_time = self.rate_limiter.wait_if_needed()
            if wait_time < 0:
                log.warning("Daily limit reached")
                break

            try:
                success = self.apply_job(job)

                if success:
                    self.queue.mark_applied(job.id)
                    self.rate_limiter.record_success()
                    applied += 1
                    log.info(f"✓ Applied to {job.title}")
                else:
                    self.queue.mark_failed(job.id, "Application failed")
                    self.rate_limiter.record_error()
                    failed += 1

            except Exception as e:
                log.error(f"✗ Failed: {e}")
                self.queue.mark_failed(job.id, str(e))
                self.rate_limiter.record_error()
                failed += 1

        self.browser_manager.close()
        self.ai_overseer.cleanup()

        log.info(f"\n=== Results ===")
        log.info(f"Applied: {applied}")
        log.info(f"Failed: {failed}")
        log.info(f"Remaining: {self.queue.count('pending')}")

        return applied


def run_applier_cli():
    parser = argparse.ArgumentParser(
        description="Job Applier - sends applications to queued jobs"
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--limit", type=int, default=50, help="Max applications to send"
    )
    parser.add_argument("--platform", help="Only apply to specific platform")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show jobs without applying"
    )
    parser.add_argument("--stats", action="store_true", help="Show queue stats")

    args = parser.parse_args()

    queue = JobQueue()

    if args.stats:
        stats = queue.get_stats()
        print("\n=== Job Queue Stats ===")
        print(f"Total: {stats['total']}")
        print(f"Pending: {stats['pending']}")
        print(f"Applied: {stats['applied']}")
        print(f"Failed: {stats['failed']}")
        print("\nBy Platform:")
        for platform, count in stats["by_platform"].items():
            print(f"  {platform}: {count}")
        return

    applier = ApplierCLI(config_path=args.config)
    applier.run(limit=args.limit, platform=args.platform, dry_run=args.dry_run)


if __name__ == "__main__":
    run_applier_cli()
