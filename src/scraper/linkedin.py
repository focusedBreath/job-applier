import asyncio
import random
import structlog
from urllib.parse import quote_plus

from playwright.async_api import Page, TimeoutError as PWTimeout

from src.queue.models import JobListing, Platform
from src.scraper.base import BaseScraper
from src.utils.browser import BrowserManager

log = structlog.get_logger()

_DATE_FILTER = {1: "r86400", 7: "r604800", 14: "r1209600", 30: "r2592000"}


class LinkedInScraper(BaseScraper):
    platform = Platform.LINKEDIN

    async def scrape(
        self,
        keywords: list[str],
        locations: list[str],
        days_back: int,
    ) -> list[JobListing]:
        jobs: list[JobListing] = []
        date_param = _DATE_FILTER.get(days_back, "r604800")

        async with self.browser.page("linkedin") as page:
            if not await self._is_logged_in(page):
                await self._login(page)

            for keyword in keywords:
                for location in locations:
                    found = await self._search(page, keyword, location, date_param)
                    jobs.extend(found)
                    await asyncio.sleep(random.uniform(3, 6))

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[JobListing] = []
        for job in jobs:
            if job.url not in seen:
                seen.add(job.url)
                unique.append(job)

        log.info("linkedin.scrape.done", found=len(unique))
        return unique

    async def _is_logged_in(self, page: Page) -> bool:
        try:
            await page.goto("https://www.linkedin.com/feed/", timeout=15000)
            await page.wait_for_selector("div.feed-identity-module", timeout=5000)
            return True
        except PWTimeout:
            return False

    async def _login(self, page: Page) -> None:
        log.info("linkedin.logging_in")
        await page.goto("https://www.linkedin.com/login")
        await page.fill("#username", self.email)
        await page.fill("#password", self.password)
        await page.click('button[type="submit"]')
        try:
            await page.wait_for_selector("div.feed-identity-module", timeout=30000)
            log.info("linkedin.logged_in")
        except PWTimeout:
            log.warning("linkedin.login_timeout — may need manual verification")

    async def _search(
        self, page: Page, keyword: str, location: str, date_param: str
    ) -> list[JobListing]:
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(keyword)}"
            f"&location={quote_plus(location)}"
            f"&f_TPR={date_param}"
            f"&f_LF=f_AL"  # Easy Apply filter
        )
        log.info("linkedin.searching", keyword=keyword, location=location)

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector(".jobs-search-results__list", timeout=15000)
        except PWTimeout:
            log.warning("linkedin.search_timeout", keyword=keyword, location=location)
            return []

        jobs: list[JobListing] = []
        processed: set[str] = set()

        for _ in range(3):  # scroll up to 3 pages worth
            cards = await page.query_selector_all(".job-card-container")
            for card in cards:
                try:
                    link_el = await card.query_selector("a.job-card-list__title")
                    if not link_el:
                        continue
                    href = await link_el.get_attribute("href") or ""
                    if not href or href in processed:
                        continue
                    processed.add(href)

                    title = (await link_el.inner_text()).strip()
                    company_el = await card.query_selector(".job-card-container__company-name")
                    company = (await company_el.inner_text()).strip() if company_el else ""
                    loc_el = await card.query_selector(".job-card-container__metadata-item")
                    location_text = (await loc_el.inner_text()).strip() if loc_el else location

                    # Normalize URL
                    job_url = href.split("?")[0]
                    if job_url.startswith("/"):
                        job_url = f"https://www.linkedin.com{job_url}"

                    jobs.append(
                        self._make_job(
                            title=title,
                            company=company,
                            location=location_text,
                            url=job_url,
                        )
                    )
                except Exception as e:
                    log.debug("linkedin.card_parse_error", error=str(e))

            # Scroll to load more
            await page.evaluate("window.scrollBy(0, 1500)")
            await asyncio.sleep(random.uniform(1.5, 3))

        return jobs
