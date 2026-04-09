import asyncio
import random
import structlog
from urllib.parse import quote_plus

from playwright.async_api import Page, TimeoutError as PWTimeout

from src.queue.models import JobListing, Platform
from src.scraper.base import BaseScraper

log = structlog.get_logger()


class MonsterScraper(BaseScraper):
    platform = Platform.MONSTER

    async def scrape(
        self,
        keywords: list[str],
        locations: list[str],
        days_back: int,
    ) -> list[JobListing]:
        jobs: list[JobListing] = []

        async with self.browser.page("monster") as page:
            for keyword in keywords:
                for location in locations:
                    found = await self._search(page, keyword, location)
                    jobs.extend(found)
                    await asyncio.sleep(random.uniform(3, 6))

        seen: set[str] = set()
        unique = [j for j in jobs if not (j.url in seen or seen.add(j.url))]  # type: ignore[func-returns-value]
        log.info("monster.scrape.done", found=len(unique))
        return unique

    async def _search(self, page: Page, keyword: str, location: str) -> list[JobListing]:
        url = (
            f"https://www.monster.com/jobs/search"
            f"?q={quote_plus(keyword)}"
            f"&where={quote_plus(location)}"
        )
        log.info("monster.searching", keyword=keyword, location=location)

        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_selector("section.results-page", timeout=15000)
        except PWTimeout:
            log.warning("monster.search_timeout", keyword=keyword)
            return []

        jobs: list[JobListing] = []
        cards = await page.query_selector_all("div.job-cardstyle__JobCardComponent")

        for card in cards:
            try:
                title_el = await card.query_selector("h2.job-cardstyle__JobTitle a")
                if not title_el:
                    continue
                href = await title_el.get_attribute("href") or ""
                title = (await title_el.inner_text()).strip()

                company_el = await card.query_selector("span.job-cardstyle__CompanyNameLink")
                company = (await company_el.inner_text()).strip() if company_el else ""

                loc_el = await card.query_selector("span.job-cardstyle__Location")
                loc_text = (await loc_el.inner_text()).strip() if loc_el else location

                job_url = href if href.startswith("http") else f"https://www.monster.com{href}"

                jobs.append(
                    self._make_job(title=title, company=company, location=loc_text, url=job_url)
                )
            except Exception as e:
                log.debug("monster.card_parse_error", error=str(e))

        return jobs
