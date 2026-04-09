import asyncio
import random
import structlog
from urllib.parse import quote_plus

from playwright.async_api import Page, TimeoutError as PWTimeout

from src.queue.models import JobListing, Platform
from src.scraper.base import BaseScraper

log = structlog.get_logger()


class DiceScraper(BaseScraper):
    platform = Platform.DICE

    async def scrape(
        self,
        keywords: list[str],
        locations: list[str],
        days_back: int,
    ) -> list[JobListing]:
        jobs: list[JobListing] = []

        async with self.browser.page("dice") as page:
            for keyword in keywords:
                for location in locations:
                    found = await self._search(page, keyword, location, days_back)
                    jobs.extend(found)
                    await asyncio.sleep(random.uniform(3, 6))

        seen: set[str] = set()
        unique = [j for j in jobs if not (j.url in seen or seen.add(j.url))]  # type: ignore[func-returns-value]
        log.info("dice.scrape.done", found=len(unique))
        return unique

    async def _search(
        self, page: Page, keyword: str, location: str, days_back: int
    ) -> list[JobListing]:
        age_map = {1: "ONE", 7: "SEVEN", 14: "FOURTEEN", 30: "THIRTY"}
        age = age_map.get(days_back, "SEVEN")

        url = (
            f"https://www.dice.com/jobs"
            f"?q={quote_plus(keyword)}"
            f"&location={quote_plus(location)}"
            f"&radius=30&radiusUnit=mi"
            f"&pageSize=20&filters.postedDate={age}"
        )
        log.info("dice.searching", keyword=keyword, location=location)

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("dhi-search-cards-widget", timeout=15000)
        except PWTimeout:
            log.warning("dice.search_timeout", keyword=keyword)
            return []

        jobs: list[JobListing] = []
        cards = await page.query_selector_all("div.card")

        for card in cards:
            try:
                title_el = await card.query_selector("a.card-title-link")
                if not title_el:
                    continue
                href = await title_el.get_attribute("href") or ""
                title = (await title_el.inner_text()).strip()

                company_el = await card.query_selector("a.employer-name")
                company = (await company_el.inner_text()).strip() if company_el else ""

                loc_el = await card.query_selector("span.search-result-location")
                loc_text = (await loc_el.inner_text()).strip() if loc_el else location

                job_url = f"https://www.dice.com{href}" if href.startswith("/") else href

                jobs.append(
                    self._make_job(title=title, company=company, location=loc_text, url=job_url)
                )
            except Exception as e:
                log.debug("dice.card_parse_error", error=str(e))

        return jobs
