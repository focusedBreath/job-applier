import time
import random
from urllib.parse import quote_plus
from typing import Optional, Callable

from playwright.sync_api import Page

from .base_scraper import BaseScraper, JobListing
from ..browser.browser_manager import BrowserManager, human_like_scroll
from ..utils.logger import log


class IndeedScraper(BaseScraper):
    BASE_URL = "https://www.indeed.com"
    JOBS_URL = "https://www.indeed.com/jobs"

    JOB_SELECTORS = [
        "div.job_seen_behind_container",
        "div[data-jk]",
        "div.jobsearch-ResultsItem",
        "a.tapItem",
        "div[id^='job_']",
    ]

    def __init__(self, browser_manager: BrowserManager, delay_range: tuple = (10, 20)):
        super().__init__("Indeed")
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
        ]
        page_text = self.page.content() if self.page else ""
        page_text_lower = page_text.lower()

        for indicator in cloudflare_indicators:
            if indicator in page_text_lower:
                log.warning(f"Cloudflare challenge detected on Indeed")
                return True
        return False

    def _wait_for_page_ready(self, max_attempts: int = 3) -> bool:
        for attempt in range(max_attempts):
            if self._check_cloudflare():
                log.info(
                    f"Waiting for Cloudflare challenge (attempt {attempt + 1}/{max_attempts})"
                )
                self._delay()
                try:
                    self.page.goto(
                        self.page.url, wait_until="domcontentloaded", timeout=60000
                    )
                except:
                    pass
                continue

            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(random.uniform(2, 4))
                return True
            except Exception as e:
                log.warning(
                    f"Page not ready (attempt {attempt + 1}/{max_attempts}): {e}"
                )
                self._delay()

        return False

    def login(self, email: str, password: str) -> bool:
        log.info("Attempting Indeed login...")

        if self.browser.load_session("indeed"):
            log.info("Loaded existing Indeed session")
            return True

        self.page = self.browser.get_page("indeed")

        try:
            self.page.goto("https://www.indeed.com/auth", wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 3))

            google_btn = self.page.query_selector('button[aria-label*="Google"]')
            if not google_btn:
                google_btn = self.page.query_selector('a[href*="google"]')
            if not google_btn:
                google_btn = self.page.query_selector('button:has-text("Google")')

            if google_btn:
                log.info("Found Google sign-in button")
                google_btn.click()
                time.sleep(random.uniform(2, 3))

                windows = self.page.context.browser.contexts[0].pages
                for w in windows:
                    if "accounts.google.com" in w.url:
                        log.info("Google OAuth window detected")

                        email_input = w.query_selector('input[type="email"]')
                        if email_input:
                            email_input.fill(email)
                            time.sleep(random.uniform(1, 2))

                            next_btn = w.query_selector("#identifierNext button")
                            if next_btn:
                                next_btn.click()
                                time.sleep(random.uniform(2, 3))

                            password_input = w.query_selector('input[type="password"]')
                            if password_input:
                                password_input.fill(password)
                                time.sleep(random.uniform(1, 2))

                                next_btn = w.query_selector("#passwordNext button")
                                if next_btn:
                                    next_btn.click()
                                    time.sleep(random.uniform(3, 5))

                        break

                self.browser.save_session("indeed")
                log.info("Indeed login successful")
                return True

            log.warning("Google sign-in button not found")
            return True

        except Exception as e:
            log.error(f"Indeed login error: {e}")
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
            self.page = self.browser.get_page("indeed")

        all_jobs = []

        for keyword in keywords:
            log.info(f"Searching Indeed for: {keyword}")

            encoded_keyword = quote_plus(keyword)
            encoded_location = quote_plus(location)

            if days_back <= 1:
                fromage = "today"
            elif days_back <= 3:
                fromage = "3days"
            elif days_back <= 7:
                fromage = "7days"
            else:
                fromage = "14days"

            search_url = f"{self.JOBS_URL}?q={encoded_keyword}&l={encoded_location}&fromage={fromage}"

            try:
                self.page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

                time.sleep(random.uniform(3, 5))

                if self._check_cloudflare():
                    log.warning(
                        f"Indeed blocked by Cloudflare for '{keyword}' - skipping"
                    )
                    continue

                human_like_scroll(self.page, 3)

                job_cards = self._find_job_cards()
                log.info(f"Found {len(job_cards)} jobs on Indeed")

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card, keyword)
                        if job:
                            all_jobs.append(job)
                    except Exception as e:
                        log.debug(f"Error parsing Indeed job: {e}")
                        continue

                next_button = self.page.query_selector(
                    'a[data-testid="pagination-page-next"]'
                )
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

                    next_button = self.page.query_selector(
                        'a[data-testid="pagination-page-next"]'
                    )
                    page_count += 1

            except Exception as e:
                log.error(f"Error searching Indeed for '{keyword}': {e}")

        self.jobs = all_jobs
        log.info(f"Total Indeed jobs found: {len(all_jobs)}")
        return all_jobs

    def _parse_job_card(self, card, search_keyword: str) -> Optional[JobListing]:
        try:
            title_elem = card.query_selector("h2.jobTitle a") or card.query_selector(
                "a.jobtitle"
            )
            title = title_elem.inner_text().strip() if title_elem else ""

            company_elem = card.query_selector(
                "span.companyName"
            ) or card.query_selector("span.company")
            company = company_elem.inner_text().strip() if company_elem else ""

            location_elem = card.query_selector(
                "div.companyLocation"
            ) or card.query_selector("div.location")
            location = location_elem.inner_text().strip() if location_elem else ""

            salary_elem = card.query_selector(
                "div.salary-snippet-container span"
            ) or card.query_selector("span.salary")
            salary = salary_elem.inner_text().strip() if salary_elem else None

            date_elem = card.query_selector("span.date") or card.query_selector(
                "span[data-testid='myJobsChangedDate']"
            )
            posted_date = date_elem.inner_text().strip() if date_elem else None

            link_elem = card.query_selector("h2.jobTitle a") or card.query_selector(
                "a.jobtitle"
            )
            url = link_elem.get_attribute("href") if link_elem else ""
            if url and not url.startswith("http"):
                url = self.BASE_URL + url

            job_id = card.get_attribute("data-jk") or str(hash(url))

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
                platform="Indeed",
            )

        except Exception as e:
            log.debug(f"Error parsing Indeed job card: {e}")
            return None
