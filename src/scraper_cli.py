import argparse
from pathlib import Path

from .config import load_config
from .browser.browser_manager import BrowserManager
from .scrapers.linkedin_scraper import LinkedInScraper
from .scrapers.indeed_scraper import IndeedScraper
from .scrapers.monster_scraper import MonsterScraper
from .scrapers.dice_scraper import DiceScraper
from .scrapers.base_scraper import JobListing
from .queue.job_queue import JobQueue, QueuedJob
from .utils.logger import log


class ScraperCLI:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.browser_manager = BrowserManager(self.config.browser)
        self.queue = JobQueue()

    def run(self, platforms: list[str] = None, locations: list[str] = None):
        if platforms is None:
            platforms = ["linkedin", "indeed", "monster", "dice"]

        if locations is None:
            locations = self.config.search.locations

        self.browser_manager.start()

        scrapers_map = {
            "linkedin": LinkedInScraper,
            "indeed": IndeedScraper,
            "monster": MonsterScraper,
            "dice": DiceScraper,
        }

        delay_range = (
            self.config.limits.scraper_delay_min,
            self.config.limits.scraper_delay_max,
        )

        total_added = 0

        for platform in platforms:
            if platform.lower() not in scrapers_map:
                log.warning(f"Unknown platform: {platform}")
                continue

            scraper_class = scrapers_map[platform.lower()]
            scraper = scraper_class(self.browser_manager, delay_range=delay_range)

            if platform == "linkedin" and self.config.credentials.linkedin_email:
                log.info("Attempting LinkedIn login...")
                scraper.login(
                    self.config.credentials.linkedin_email,
                    self.config.credentials.linkedin_password,
                )

            if platform == "indeed" and self.config.credentials.indeed_email:
                log.info("Attempting Indeed login...")
                scraper.login(
                    self.config.credentials.indeed_email,
                    self.config.credentials.indeed_password or "",
                )

            for location in locations:
                log.info(f"Scraping {platform} for '{location}'...")

                try:
                    jobs = scraper.search(
                        keywords=self.config.search.keywords,
                        location=location,
                        days_back=self.config.search.days_back,
                    )

                    queued_jobs = [
                        QueuedJob(
                            id=job.id,
                            title=job.title,
                            company=job.company,
                            location=job.location,
                            url=job.url,
                            platform=job.platform,
                            posted_date=job.posted_date,
                            salary=job.salary,
                        )
                        for job in jobs
                    ]

                    added = self.queue.add_jobs(queued_jobs)
                    total_added += added

                    log.info(f"Found {len(jobs)} jobs, added {added} new")

                except Exception as e:
                    log.error(f"Error scraping {platform}: {e}")

        self.browser_manager.close()

        stats = self.queue.get_stats()
        log.info(
            f"Queue stats: {stats['pending']} pending, {stats['applied']} applied, {stats['failed']} failed"
        )
        log.info(f"Total jobs in queue: {stats['total']}")

        return total_added


def run_scraper_cli():
    parser = argparse.ArgumentParser(
        description="Job Scraper - aggregates job listings"
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--platforms",
        nargs="+",
        help="Platforms to scrape (linkedin indeed monster dice)",
    )
    parser.add_argument("--locations", nargs="+", help="Locations to search")
    parser.add_argument("--stats", action="store_true", help="Show queue stats only")
    parser.add_argument(
        "--clear", action="store_true", help="Clear applied jobs from queue"
    )

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

    if args.clear:
        queue.clear_applied()
        return

    scraper = ScraperCLI(config_path=args.config)
    scraper.run(platforms=args.platforms, locations=args.locations)


if __name__ == "__main__":
    run_scraper_cli()
