import time
import random
from pathlib import Path
from urllib.parse import quote_plus
from typing import Optional

from playwright.sync_api import Page

from .base_scraper import BaseScraper, JobListing
from ..browser.browser_manager import (
    BrowserManager,
    human_like_scroll,
    human_like_mouse_move,
)
from ..utils.logger import log


class LinkedInScraper(BaseScraper):
    BASE_URL = "https://www.linkedin.com"
    LOGIN_URL = "https://www.linkedin.com/login"

    def __init__(self, browser_manager: BrowserManager, delay_range: tuple = (10, 20)):
        super().__init__("LinkedIn")
        self.browser = browser_manager
        self.page: Optional[Page] = None
        self.logged_in = False
        self.delay_min, self.delay_max = delay_range

    def _delay(self):
        delay = random.uniform(self.delay_min, self.delay_max)
        log.debug(f"Sleeping {delay:.1f}s")
        time.sleep(delay)

    def _find_job_cards(self) -> list:
        log.debug(f"Page title: {self.page.title()}")
        log.debug(f"Page URL: {self.page.url}")

        for selector in self.JOB_SELECTORS:
            try:
                cards = self.page.query_selector_all(selector)
                if cards:
                    log.info(f"Found {len(cards)} jobs with selector: {selector}")
                    return cards
            except:
                continue

        log.warning("No jobs found with standard selectors. Saving debug HTML...")

        # Dump HTML for debugging
        debug_dir = Path(__file__).parent.parent.parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        import time

        html_file = debug_dir / f"linkedin_debug_{int(time.time())}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(self.page.content())
        log.info(f"Saved HTML to {html_file}")

        all_links = self.page.query_selector_all("a[href*='/jobs/view']")
        log.info(f"Found {len(all_links)} job links")

        if all_links:
            parents = []
            for link in all_links:
                parent = link.evaluate(
                    "el => el.closest('.base-card') || el.closest('li') || el.parentElement"
                )
                if parent:
                    parents.append(parent)

            if parents:
                log.info(f"Found {len(parents)} job card parents")
                return parents

        return []

    def login(self, email: str, password: str) -> bool:
        log.info("Logging into LinkedIn...")

        if self.browser.load_session("linkedin"):
            self.logged_in = True
            return True

        self.page = self.browser.get_page("linkedin")

        try:
            self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))

            self.page.fill("input#username", email)
            time.sleep(random.uniform(0.5, 1.5))

            self.page.fill("input#password", password)
            time.sleep(random.uniform(0.5, 1.5))

            self.page.click('button[type="submit"]')
            time.sleep(random.uniform(3, 5))

            if "checkpoint" in self.page.url or "challenge" in self.page.url:
                log.warning("LinkedIn requires verification - check browser")
                input("Complete verification in browser, then press Enter...")

            if "feed" in self.page.url or self.page.url == self.BASE_URL + "/":
                self.logged_in = True
                self.browser.save_session("linkedin")
                log.info("Successfully logged into LinkedIn")
                return True

            log.error("Failed to login to LinkedIn")
            return False

        except Exception as e:
            log.error(f"LinkedIn login error: {e}")
            return False

    def is_logged_in(self) -> bool:
        if not self.logged_in or not self.page:
            return False

        try:
            self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=10000)
            return "feed" in self.page.url or self.page.url == self.BASE_URL + "/"
        except:
            return False

    JOB_SELECTORS = [
        "div.base-card.job-search-card",
        "div.job-search-card",
        "li.base-card",
        "div.base-search-card",
        "a[href*='/jobs/view']",
    ]

    def search(
        self, keywords: list[str], location: str = "Remote", days_back: int = 7
    ) -> list[JobListing]:
        if not self.page:
            self.page = self.browser.get_page("linkedin")

        all_jobs = []

        for keyword in keywords:
            log.info(f"Searching LinkedIn for: {keyword}")

            encoded_keyword = quote_plus(keyword)
            encoded_location = quote_plus(location)
            search_url = f"{self.BASE_URL}/jobs/search/?keywords={encoded_keyword}&location={encoded_location}&f_TPR=r{days_back}"

            try:
                self.page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                try:
                    self.page.wait_for_selector("a[href*='/jobs/view']", timeout=10000)
                except:
                    pass
                time.sleep(2)

                for _ in range(3):
                    human_like_scroll(self.page, 2)
                    time.sleep(random.uniform(1, 2))

                job_cards = self._find_job_cards()
                log.info(f"Found {len(job_cards)} job cards")

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card, keyword)
                        if job:
                            all_jobs.append(job)
                    except Exception as e:
                        log.debug(f"Error parsing job card: {e}")
                        continue

                next_btn = self.page.query_selector(
                    "button[aria-label*='Next']"
                ) or self.page.query_selector("button[aria-label*='page']")
                page_count = 0
                while next_btn and page_count < 2:
                    try:
                        next_btn.click()
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

                        next_btn = self.page.query_selector(
                            "button[aria-label*='Next']"
                        ) or self.page.query_selector("button[aria-label*='page']")
                        page_count += 1
                    except:
                        break

            except Exception as e:
                log.error(f"Error searching LinkedIn for '{keyword}': {e}")

        self.jobs = all_jobs
        log.info(f"Total LinkedIn jobs found: {len(all_jobs)}")
        return all_jobs

    def _parse_job_card(self, card, search_keyword: str) -> Optional[JobListing]:
        try:
            tag_name = card.evaluate("el => el.tagName")

            if tag_name == "A":
                link_elem = card
                href = link_elem.get_attribute("href") or ""
                title = link_elem.inner_text().strip()
                url = href
                parent = link_elem.evaluate(
                    "el => el.closest('.base-card') || el.parentElement"
                )
                company = ""
                location = ""
                if parent:
                    company_elem = parent.query_selector(".base-search-card__subtitle")
                    company = company_elem.inner_text().strip() if company_elem else ""
            else:
                title_elem = card.query_selector("h3.base-search-card__title")
                title = title_elem.inner_text().strip() if title_elem else ""

                link_elem = card.query_selector("a.base-card__full-link")
                url = link_elem.get_attribute("href") if link_elem else ""

                company_elem = card.query_selector(".base-search-card__subtitle")
                company = company_elem.inner_text().strip() if company_elem else ""

                location_elem = card.query_selector(".job-search-card__location")
                location = location_elem.inner_text().strip() if location_elem else ""

            if url and not url.startswith("http"):
                url = self.BASE_URL + url

            job_id = card.get_attribute("data-entity-urn") or str(hash(url))

            date_elem = card.query_selector(".job-search-card__listdate")
            posted_date = date_elem.inner_text().strip() if date_elem else None

            easy_apply_elem = card.query_selector("[class*='EasyApply']")
            is_easy_apply = easy_apply_elem is not None

            if not title and not company and not url:
                return None

            return JobListing(
                id=job_id,
                title=title,
                company=company,
                location=location,
                url=url,
                posted_date=posted_date,
                platform="LinkedIn",
                is_easy_apply=is_easy_apply,
            )

        except Exception as e:
            log.debug(f"Error parsing job card: {e}")
            return None

    def get_job_details(self, job_url: str) -> dict:
        if not self.page:
            return {}

        try:
            self.page.goto(job_url, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))

            description_elem = self.page.query_selector(
                ".jobs-description-content__text"
            )
            description = description_elem.inner_text() if description_elem else ""

            criteria_items = self.page.query_selector_all(
                ".job-details-skill-match-status-list__item"
            )
            criteria = [item.inner_text() for item in criteria_items]

            return {
                "description": description,
                "criteria": criteria,
            }

        except Exception as e:
            log.error(f"Error getting job details: {e}")
            return {}
