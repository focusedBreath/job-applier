import asyncio
import random
import structlog
from urllib.parse import quote_plus

from playwright.async_api import Page, TimeoutError as PWTimeout

from src.queue.models import JobListing, Platform
from src.scraper.base import BaseScraper

log = structlog.get_logger()

_DAYS_MAP = {1: "1", 7: "7", 14: "14", 30: "30"}


class IndeedScraper(BaseScraper):
    platform = Platform.INDEED

    async def scrape(
        self,
        keywords: list[str],
        locations: list[str],
        days_back: int,
    ) -> list[JobListing]:
        jobs: list[JobListing] = []
        fromage = _DAYS_MAP.get(days_back, "7")

        async with self.browser.page("indeed") as page:
            for keyword in keywords:
                for location in locations:
                    found = await self._search(page, keyword, location, fromage)
                    jobs.extend(found)
                    await asyncio.sleep(random.uniform(4, 8))

        seen: set[str] = set()
        unique = [j for j in jobs if not (j.url in seen or seen.add(j.url))]  # type: ignore[func-returns-value]
        log.info("indeed.scrape.done", found=len(unique))
        return unique

    async def _search(
        self, page: Page, keyword: str, location: str, fromage: str
    ) -> list[JobListing]:
        url = (
            f"https://www.indeed.com/jobs"
            f"?q={quote_plus(keyword)}"
            f"&l={quote_plus(location)}"
            f"&fromage={fromage}"
        )
        log.info("indeed.searching", keyword=keyword, location=location)

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("#mosaic-provider-jobcards", timeout=15000)
        except PWTimeout:
            log.warning("indeed.search_timeout", keyword=keyword)
            return []

        jobs: list[JobListing] = []
        cards = await page.query_selector_all("div.job_seen_beacon")

        for card in cards:
            try:
                title_el = await card.query_selector("h2.jobTitle a")
                if not title_el:
                    continue
                href = await title_el.get_attribute("href") or ""
                title = (await title_el.inner_text()).strip()

                company_el = await card.query_selector("span.companyName")
                company = (await company_el.inner_text()).strip() if company_el else ""

                loc_el = await card.query_selector("div.companyLocation")
                loc_text = (await loc_el.inner_text()).strip() if loc_el else location

                salary_el = await card.query_selector("div.metadata.salary-snippet-container")
                salary = (await salary_el.inner_text()).strip() if salary_el else ""

                job_url = f"https://www.indeed.com{href}" if href.startswith("/") else href

                jobs.append(
                    self._make_job(
                        title=title,
                        company=company,
                        location=loc_text,
                        url=job_url,
                        salary=salary,
                    )
                )
            except Exception as e:
                log.debug("indeed.card_parse_error", error=str(e))

        return jobs
