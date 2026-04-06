import time
import random
from urllib.parse import quote_plus
from typing import Optional

from playwright.sync_api import Page

from .base_scraper import BaseScraper, JobListing
from ..browser.browser_manager import BrowserManager, human_like_scroll
from ..utils.logger import log


class MonsterScraper(BaseScraper):
    BASE_URL = "https://www.monster.com"
    JOBS_URL = "https://www.monster.com/jobs/search"

    JOB_SELECTORS = [
        "div.card-content",
        "div[data-testid='srp-job-card']",
        "article.job-card",
        "div.job-card",
        "div[data-cy='job-card']",
    ]

    def __init__(self, browser_manager: BrowserManager, delay_range: tuple = (10, 20)):
        super().__init__("Monster")
        self.browser = browser_manager
        self.page: Optional[Page] = None
        self.delay_min, self.delay_max = delay_range

    def _delay(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        log.debug(f"Sleeping {delay:.1f}s")
        time.sleep(delay)

    def _check_cloudflare(self) -> bool:
        cloudflare_indicators = [
            "checking your browser",
            "verifying you are human",
            "cloudflare",
            "ray id:",
            "ddos protection",
        ]
        page_text = self.page.content() if self.page else ""
        page_text_lower = page_text.lower()

        for indicator in cloudflare_indicators:
            if indicator in page_text_lower:
                log.warning(f"Cloudflare challenge detected on Monster")
                return True
        return False

    def _wait_for_page_ready(self, max_attempts: int = 3) -> bool:
        for attempt in range(max_attempts):
            if self._check_cloudflare():
                log.info(
                    f"Waiting for Cloudflare challenge (attempt {attempt + 1}/{max_attempts})"
                )
                self._delay()
                self.page.reload(wait_until="networkidle")
                continue

            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
                self.page.wait_for_load_state("domcontentloaded")
                time.sleep(random.uniform(1, 2))
                return True
            except Exception as e:
                log.warning(
                    f"Page not ready (attempt {attempt + 1}/{max_attempts}): {e}"
                )
                self._delay()

        return False

    def login(self, email: str, password: str) -> bool:
        log.info("Monster login not implemented")
        return True

    def is_logged_in(self) -> bool:
        return True

    def _find_job_cards(self) -> list:
        for selector in self.JOB_SELECTORS:
            try:
                cards = self.page.query_selector_all(selector)
                if cards:
                    log.info(f"Found {len(cards)} job cards using selector: {selector}")
                    return cards
            except Exception:
                continue

        log.warning("No job cards found with any selector")
        return []

    def search(
        self, keywords: list[str], location: str = "Remote", days_back: int = 7
    ) -> list[JobListing]:
        if not self.page:
            self.page = self.browser.get_page("monster")

        all_jobs = []

        for keyword in keywords:
            log.info(f"Searching Monster for: {keyword}")

            encoded_keyword = quote_plus(keyword)

            search_url = (
                f"{self.JOBS_URL}?q={encoded_keyword}&where={quote_plus(location)}"
            )

            try:
                self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                if not self._wait_for_page_ready():
                    log.warning(
                        f"Failed to load Monster page for '{keyword}' - possible Cloudflare block"
                    )
                    continue

                human_like_scroll(self.page, 3)

                job_cards = self._find_job_cards()
                log.info(f"Found {len(job_cards)} jobs on Monster")

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card, keyword)
                        if job:
                            all_jobs.append(job)
                    except Exception as e:
                        log.debug(f"Error parsing Monster job: {e}")
                        continue

                next_button = self.page.query_selector('a[data-testid="next-page"]')
                page_count = 0
                while next_button and page_count < 3:
                    next_button.click()
                    self._delay()

                    human_like_scroll(self.page, 2)

                    job_cards = self._find_job_cards()
                    for card in job_cards:
                        try:
                            job = self._parse_job_card(card, keyword)
                            if job:
                                all_jobs.append(job)
                        except:
                            continue

                    next_button = self.page.query_selector('a[data-testid="next-page"]')
                    page_count += 1

            except Exception as e:
                log.error(f"Error searching Monster for '{keyword}': {e}")

        self.jobs = all_jobs
        log.info(f"Total Monster jobs found: {len(self.jobs)}")
        return all_jobs

    def _parse_job_card(self, card, search_keyword: str) -> Optional[JobListing]:
        try:
            title_elem = (
                card.query_selector("a.card-title")
                or card.query_selector("h2 a")
                or card.query_selector("a[data-cy='job-title']")
            )
            title = title_elem.inner_text().strip() if title_elem else ""

            company_elem = (
                card.query_selector("div.company-name")
                or card.query_selector("span.company")
                or card.query_selector("a[data-cy='company-name']")
            )
            company = company_elem.inner_text().strip() if company_elem else ""

            location_elem = (
                card.query_selector("div.location")
                or card.query_selector("span.location")
                or card.query_selector("div[data-cy='job-location']")
            )
            location = location_elem.inner_text().strip() if location_elem else ""

            salary_elem = (
                card.query_selector("div.salary")
                or card.query_selector("span.salary")
                or card.query_selector("div[data-cy='job-salary']")
            )
            salary = salary_elem.inner_text().strip() if salary_elem else None

            link_elem = card.query_selector("a.card-title") or card.query_selector(
                "h2 a"
            )
            url = link_elem.get_attribute("href") if link_elem else ""
            if url and not url.startswith("http"):
                url = self.BASE_URL + url

            posted_elem = (
                card.query_selector("div.posted-date")
                or card.query_selector("span.date")
                or card.query_selector("div[data-cy='job-date']")
            )
            posted_date = posted_elem.inner_text().strip() if posted_elem else None

            job_id = str(hash(url))

            if not title and not company:
                log.debug("Skipping card with no title or company")
                return None

            return JobListing(
                id=job_id,
                title=title,
                company=company,
                location=location,
                url=url,
                posted_date=posted_date,
                salary=salary,
                platform="Monster",
            )

        except Exception as e:
            log.debug(f"Error parsing Monster job card: {e}")
            return None
