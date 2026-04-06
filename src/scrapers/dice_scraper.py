import time
import random
from urllib.parse import quote_plus
from typing import Optional

from playwright.sync_api import Page

from .base_scraper import BaseScraper, JobListing
from ..browser.browser_manager import BrowserManager, human_like_scroll
from ..utils.logger import log


class DiceScraper(BaseScraper):
    BASE_URL = "https://www.dice.com"
    JOBS_URL = "https://www.dice.com/jobs"

    def __init__(self, browser_manager: BrowserManager, delay_range: tuple = (10, 20)):
        super().__init__("Dice")
        self.browser = browser_manager
        self.page: Optional[Page] = None
        self.delay_min, self.delay_max = delay_range

    def _delay(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        log.debug(f"Sleeping {delay:.1f}s")
        time.sleep(delay)

    def login(self, email: str, password: str) -> bool:
        log.info("Dice login not implemented")
        return True

    def is_logged_in(self) -> bool:
        return True

    def search(
        self, keywords: list[str], location: str = "Remote", days_back: int = 7
    ) -> list[JobListing]:
        if not self.page:
            self.page = self.browser.get_page("dice")

        all_jobs = []

        for keyword in keywords:
            log.info(f"Searching Dice for: {keyword}")

            encoded_keyword = quote_plus(keyword)
            encoded_location = (
                quote_plus(location) if location.lower() != "remote" else "remote"
            )

            search_url = f"{self.JOBS_URL}?q={encoded_keyword}&l={encoded_location}"

            try:
                self.page.goto(search_url, wait_until="domcontentloaded")
                time.sleep(random.uniform(2, 4))

                human_like_scroll(self.page, 3)

                job_cards = self.page.query_selector_all("dhi-search-card")
                if not job_cards:
                    job_cards = self.page.query_selector_all("div.card")

                log.info(f"Found {len(job_cards)} jobs on Dice")

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card, keyword)
                        if job:
                            all_jobs.append(job)
                    except Exception as e:
                        log.debug(f"Error parsing Dice job: {e}")
                        continue

                next_button = self.page.query_selector(
                    'button[data-testid="pagination-next"]'
                )
                if not next_button:
                    next_button = self.page.query_selector('a[rel="next"]')

                page_count = 0
                while next_button and page_count < 3:
                    next_button.click()
                    time.sleep(random.uniform(2, 4))

                    human_like_scroll(self.page, 2)

                    job_cards = self.page.query_selector_all("dhi-search-card")
                    if not job_cards:
                        job_cards = self.page.query_selector_all("div.card")

                    for card in job_cards:
                        try:
                            job = self._parse_job_card(card, keyword)
                            if job:
                                all_jobs.append(job)
                        except:
                            continue

                    next_button = self.page.query_selector(
                        'button[data-testid="pagination-next"]'
                    )
                    if not next_button:
                        next_button = self.page.query_selector('a[rel="next"]')
                    page_count += 1

            except Exception as e:
                log.error(f"Error searching Dice for '{keyword}': {e}")

        self.jobs = all_jobs
        log.info(f"Total Dice jobs found: {len(self.jobs)}")
        return all_jobs

    def _parse_job_card(self, card, search_keyword: str) -> Optional[JobListing]:
        try:
            title_elem = card.query_selector("h3")
            if not title_elem:
                title_elem = card.query_selector("a")
            title = title_elem.inner_text().strip() if title_elem else ""

            company_elem = card.query_selector("span[data-testid='company-name']")
            if not company_elem:
                company_elem = card.query_selector(".company")
            company = company_elem.inner_text().strip() if company_elem else ""

            location_elem = card.query_selector(
                "span[data-testid='searchResultLocation']"
            )
            if not location_elem:
                location_elem = card.query_selector(".location")
            location = location_elem.inner_text().strip() if location_elem else ""

            salary_elem = card.query_selector("span[data-testid='searchResultSalary']")
            if not salary_elem:
                salary_elem = card.query_selector(".salary")
            salary = salary_elem.inner_text().strip() if salary_elem else None

            link_elem = card.query_selector("a")
            url = link_elem.get_attribute("href") if link_elem else ""
            if url and not url.startswith("http"):
                url = self.BASE_URL + url

            posted_elem = card.query_selector("span[data-testid='searchResultDate']")
            posted_date = posted_elem.inner_text().strip() if posted_elem else None

            job_id = str(hash(url))

            return JobListing(
                id=job_id,
                title=title,
                company=company,
                location=location,
                url=url,
                posted_date=posted_date,
                salary=salary,
                platform="Dice",
            )

        except Exception as e:
            log.debug(f"Error parsing Dice job card: {e}")
            return None
