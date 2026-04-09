import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fake_useragent import UserAgent
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

log = structlog.get_logger()
_ua = UserAgent()


class BrowserManager:
    def __init__(self, sessions_dir: str) -> None:
        self._sessions_dir = Path(sessions_dir)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,  # Xvfb provides virtual display in Docker
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        log.info("browser.started")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("browser.stopped")

    @asynccontextmanager
    async def context(self, platform: str) -> AsyncGenerator[BrowserContext, None]:
        assert self._browser, "Call start() first"
        state_path = self._sessions_dir / f"{platform}_session.json"
        storage_state = str(state_path) if state_path.exists() else None

        ctx = await self._browser.new_context(
            user_agent=_ua.random,
            viewport={"width": 1280, "height": 900},
            storage_state=storage_state,
            locale="en-US",
            timezone_id="America/New_York",
        )
        # Mask webdriver flag
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        try:
            yield ctx
        finally:
            # Persist session cookies
            await ctx.storage_state(path=str(state_path))
            await ctx.close()

    @asynccontextmanager
    async def page(self, platform: str) -> AsyncGenerator[Page, None]:
        async with self.context(platform) as ctx:
            p = await ctx.new_page()
            try:
                yield p
            finally:
                await p.close()
