import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_config, get_store, get_browser
from src.api.tasks import TaskType, runner
from src.config import Config
from src.queue.models import Platform
from src.queue.store import JobStore
from src.scraper.linkedin import LinkedInScraper
from src.scraper.indeed import IndeedScraper
from src.scraper.dice import DiceScraper
from src.scraper.monster import MonsterScraper
from src.utils.browser import BrowserManager

log = structlog.get_logger()

router = APIRouter(prefix="/scrape", tags=["scrape"])

_SCRAPER_MAP = {
    Platform.LINKEDIN: LinkedInScraper,
    Platform.INDEED: IndeedScraper,
    Platform.DICE: DiceScraper,
    Platform.MONSTER: MonsterScraper,
}

_CRED_MAP = {
    Platform.LINKEDIN: ("linkedin_email", "linkedin_password"),
    Platform.INDEED: ("indeed_email", "indeed_password"),
    Platform.DICE: ("dice_email", "dice_password"),
    Platform.MONSTER: ("monster_email", "monster_password"),
}


class ScrapeRequest(BaseModel):
    platforms: list[Platform]
    keywords: list[str] | None = None
    locations: list[str] | None = None
    days_back: int | None = None


class ScrapeResponse(BaseModel):
    started: bool
    message: str


@router.post("", response_model=ScrapeResponse)
async def start_scrape(
    body: ScrapeRequest,
    config: Config = Depends(get_config),
    store: JobStore = Depends(get_store),
    browser: BrowserManager = Depends(get_browser),
) -> ScrapeResponse:
    if runner.is_running:
        raise HTTPException(409, f"Task already running: {runner.state.type}")

    keywords = body.keywords or config.search_keywords
    locations = body.locations or config.search_locations
    days_back = body.days_back or config.search_days_back

    async def _run() -> None:
        log.info("scrape.start", platforms=[p.value for p in body.platforms])
        all_jobs = []
        for i, platform in enumerate(body.platforms):
            runner.update_progress(i, len(body.platforms))
            scraper_cls = _SCRAPER_MAP[platform]
            cred_keys = _CRED_MAP[platform]
            email = getattr(config, cred_keys[0])
            password = getattr(config, cred_keys[1])
            extra = {}
            if platform == Platform.LINKEDIN:
                extra["manual_login"] = getattr(config, "linkedin_manual_login", False)
            scraper = scraper_cls(browser, email, password, **extra)
            jobs = await scraper.scrape(keywords, locations, days_back)
            all_jobs.extend(jobs)

        inserted = await store.add_jobs(all_jobs)
        log.info("scrape.done", found=len(all_jobs), inserted=inserted)

    await runner.run(TaskType.SCRAPING, _run())
    return ScrapeResponse(started=True, message="Scrape started")
