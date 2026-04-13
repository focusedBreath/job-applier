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

_FEED_SELECTORS = [
    "div.feed-identity-module",
    "div[data-view-name='feed-identity-module']",
    "nav.global-nav",
    "div.scaffold-layout",
    "div[data-test-id='nav-settings__account-type-label']",
    "img.global-nav__me-photo",
]

_RESULTS_SELECTORS = [
    ".jobs-search-results__list",
    ".jobs-search-results-grid",
    "ul.scaffold-layout__list-container",
    "div.jobs-job-board-list",
]

_CARD_SELECTORS = [
    ".job-card-container",
    ".job-card-list",
    "[data-job-id]",
    ".jobs-search-results__list-item",
]

_TITLE_SELECTORS = [
    "a.job-card-list__title",
    "a.job-card-container__link",
    "a[data-control-name='jobcard_title']",
    ".job-card-list__title--link",
]

_COMPANY_SELECTORS = [
    ".job-card-container__company-name",
    ".job-card-container__primary-description",
    ".artdeco-entity-lockup__subtitle span",
]

_LOCATION_SELECTORS = [
    ".job-card-container__metadata-item",
    ".job-card-container__metadata-wrapper li",
    ".artdeco-entity-lockup__caption li",
]

_EMAIL_SELECTORS = [
    "#userName",
    "#username",
    'input[id="userName"]',
    'input[name="session_key"]',
    'input[type="email"]',
    'input[autocomplete="username"]',
    'input[data-testid="username-input"]',
    'input[id="session_key"]',
]

_PASSWORD_SELECTORS = [
    "#password",
    "#userPassword",
    'input[id="password"]',
    'input[id="userPassword"]',
    'input[name="session_password"]',
    'input[type="password"]',
    'input[autocomplete="current-password"]',
    'input[data-testid="password-input"]',
    'input[id="session_password"]',
    'input[placeholder="password"]',
    'input[aria-label="Password"]',
    'input[name="password"]',
    "#form-password",
]


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
        manual_login = self.extra.get("manual_login", False)

        async with self.browser.page("linkedin") as page:
            logged_in = await self._is_logged_in(page)
            if not logged_in:
                if manual_login:
                    log.warning(
                        "linkedin.login.manual_required",
                        hint="Open noVNC at localhost:6080 to login manually",
                    )
                    log.info(
                        "linkedin.login.waiting_for_manual",
                        hint="Will check for login every 10s. After logging in via noVNC, the scrape will continue automatically.",
                    )
                    for _ in range(30):
                        await asyncio.sleep(10)
                        logged_in = await self._is_logged_in(page)
                        if logged_in:
                            log.info("linkedin.login.manual_success")
                            break
                    if not logged_in:
                        log.error(
                            "linkedin.login.manual_timeout",
                            hint="No manual login detected after 5 minutes",
                        )
                        return []
                else:
                    logged_in = await self._login(page)
            if not logged_in:
                log.error("linkedin.scrape.aborted", reason="Could not log in")
                return []

            for keyword in keywords:
                for location in locations:
                    found = await self._search(page, keyword, location, date_param)
                    log.info(
                        "linkedin.search.result",
                        keyword=keyword,
                        location=location,
                        found=len(found),
                    )
                    jobs.extend(found)
                    await asyncio.sleep(random.uniform(3, 6))

        seen: set[str] = set()
        unique: list[JobListing] = []
        for job in jobs:
            if job.url not in seen:
                seen.add(job.url)
                unique.append(job)

        log.info("linkedin.scrape.done", found=len(unique))
        return unique

    async def _is_logged_in(self, page: Page) -> bool:
        log.info("linkedin.checking_session")
        try:
            await page.goto("https://www.linkedin.com/feed/", timeout=20000)
        except PWTimeout:
            log.warning("linkedin.feed_load_timeout")
            return False

        current_url = page.url
        log.info("linkedin.feed_url", url=current_url)

        if "/login" in current_url or "/authwall" in current_url or "/checkpoint" in current_url:
            log.info("linkedin.not_logged_in", reason="redirected", url=current_url)
            return False

        for sel in _FEED_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el:
                    log.info("linkedin.session_valid", selector=sel)
                    return True
            except Exception:
                continue

        log.warning("linkedin.session_uncertain", url=current_url, title=await page.title())
        return "/feed" in current_url

    async def _login(self, page: Page) -> bool:
        if not self.email or not self.password:
            log.error(
                "linkedin.login.no_credentials",
                reason="LINKEDIN_EMAIL or LINKEDIN_PASSWORD is empty in .env",
            )
            return False

        log.info("linkedin.logging_in", email=self.email)

        try:
            await page.goto("https://www.linkedin.com/login", timeout=20000)
        except PWTimeout:
            log.error("linkedin.login.page_timeout")
            return False

        # networkidle waits for JS to finish rendering — domcontentloaded is too
        # early for LinkedIn's SPA login page, the form fields won't exist yet
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            log.warning("linkedin.login.networkidle_timeout — continuing anytime")

        log.info("linkedin.login.page_loaded", url=page.url, title=await page.title())

        # Check for checkpoint/verification page - wait for the submit button
        # which appears AFTER the checkpoint clears. This is more reliable than
        # waiting for input fields which may be hidden until verification passes.
        form_ready_selectors = [
            "button[type='submit']",
            "button.btn-primary",
            "button.login-form__submit-btn",
            ".artdeco-button[type='submit']",
        ]

        form_ready = False
        for sel in form_ready_selectors:
            try:
                await page.wait_for_selector(sel, timeout=10000)
                log.info("linkedin.login.form_ready", selector=sel)
                form_ready = True
                break
            except PWTimeout:
                continue

        if not form_ready:
            log.warning(
                "linkedin.login.checkpoint_waiting",
                url=page.url,
                hint="Waiting for checkpoint verification to complete...",
            )
            for sel in form_ready_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=90000)
                    log.info("linkedin.login.form_ready_after_checkpoint", selector=sel)
                    form_ready = True
                    break
                except PWTimeout:
                    continue

        if not form_ready:
            html = await page.content()
            log.error(
                "linkedin.login.checkpoint_failed",
                url=page.url,
                page_html=html[:5000],
            )
            return False

        # ── Step 1: Email ────────────────────────────────────────────────────
        email_sel = None
        for sel in _EMAIL_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=10000)
                email_sel = sel
                log.info("linkedin.login.email_field_found", selector=sel)
                break
            except PWTimeout:
                continue

        if not email_sel:
            html = await page.content()
            log.error(
                "linkedin.login.email_field_not_found",
                tried=_EMAIL_SELECTORS,
                url=page.url,
                title=await page.title(),
                page_html=html[:5000],
                hint="Check noVNC at localhost:6080 to see what the page looks like",
            )
            return False

        await page.fill(email_sel, self.email)

        # Check if password is already on this page (single-page flow)
        # or if we need to submit email first (two-step flow)
        password_sel = None
        for sel in _PASSWORD_SELECTORS:
            el = await page.query_selector(sel)
            if el:
                password_sel = sel
                log.info("linkedin.login.single_page_flow", password_sel=password_sel)
                break

        if not password_sel:
            log.info("linkedin.login.submitting_email")
            await page.click('button[type="submit"]')

            # Wait a bit for the page to transition
            await asyncio.sleep(3)

            # Check URL first
            current_url = page.url
            log.info("linkedin.login.after_email_submit", url=current_url)

            if "checkpoint" in current_url or "challenge" in current_url or "verify" in current_url:
                log.warning("linkedin.login.checkpoint_after_email", url=current_url)
                await asyncio.sleep(60)

            # Wait for the login form to be visible and ready
            try:
                await page.wait_for_selector("form.login__form", timeout=10000)
                log.info("linkedin.login.form_visible")
            except PWTimeout:
                log.warning("linkedin.login.form_not_visible")

            # Now find the password field - get all password inputs and use the first visible one
            password_inputs = await page.query_selector_all('input[type="password"]')
            log.info("linkedin.login.password_inputs_found", count=len(password_inputs))

            for i, inp in enumerate(password_inputs):
                is_visible = await inp.is_visible()
                log.info("linkedin.login.password_input_check", index=i, visible=is_visible)
                if is_visible:
                    password_sel = 'input[type="password"]'
                    log.info("linkedin.login.password_field_found", index=i)
                    break

        if not password_sel:
            html = await page.content()
            log.error(
                "linkedin.login.password_field_not_found",
                url=page.url,
                title=await page.title(),
                page_html=html[:5000],
                hint="Check noVNC at localhost:6080 to see what the page looks like",
            )
            return False

        # ── Step 2: Password ─────────────────────────────────────────────────
        log.info("linkedin.login.filling_password", selector=password_sel)
        await page.fill(password_sel, self.password)
        await page.click('button[type="submit"]')

        await asyncio.sleep(4)
        post_url = page.url
        log.info("linkedin.login.post_submit_url", url=post_url)

        if "checkpoint" in post_url or "challenge" in post_url:
            log.warning(
                "linkedin.login.checkpoint",
                url=post_url,
                hint="LinkedIn requires human verification — complete it via noVNC at localhost:6080",
            )
            for _ in range(12):
                await asyncio.sleep(5)
                if "/feed" in page.url or "mynetwork" in page.url:
                    log.info("linkedin.login.checkpoint_cleared")
                    return True
            log.error("linkedin.login.checkpoint_timeout")
            return False

        if "/login" in post_url:
            for err_sel in [
                "div.alert-content",
                "#error-for-username",
                "#error-for-password",
                "p.body-small.form__label--feedback",
                "span.form__label--feedback",
            ]:
                el = await page.query_selector(err_sel)
                if el:
                    msg = await el.inner_text()
                    log.error("linkedin.login.credential_error", error_text=msg.strip())
                    return False
            log.error("linkedin.login.still_on_login_page", url=post_url)
            return False

        for sel in _FEED_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=8000)
                log.info("linkedin.logged_in", selector=sel)
                return True
            except PWTimeout:
                continue

        if "/feed" in page.url or "mynetwork" in page.url:
            log.info("linkedin.logged_in", method="url_check", url=page.url)
            return True

        log.error("linkedin.login.unconfirmed", url=page.url, title=await page.title())
        return False

    async def _search(
        self, page: Page, keyword: str, location: str, date_param: str
    ) -> list[JobListing]:
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(keyword)}"
            f"&location={quote_plus(location)}"
            f"&f_TPR={date_param}"
        )
        log.info("linkedin.searching", keyword=keyword, location=location, url=url)

        try:
            await page.goto(url, timeout=30000)
        except PWTimeout:
            log.warning("linkedin.search.goto_timeout", keyword=keyword, location=location)
            return []

        results_sel = None
        for sel in _RESULTS_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=10000)
                results_sel = sel
                log.info("linkedin.results_container_found", selector=sel)
                break
            except PWTimeout:
                continue

        if not results_sel:
            log.warning(
                "linkedin.search.no_results_container",
                keyword=keyword,
                location=location,
                url=page.url,
                title=await page.title(),
                hint="All results selectors timed out — LinkedIn may have changed markup or returned no results",
            )
            return []

        jobs: list[JobListing] = []
        processed: set[str] = set()

        for scroll_pass in range(3):
            cards = []
            for card_sel in _CARD_SELECTORS:
                cards = await page.query_selector_all(card_sel)
                if cards:
                    log.debug("linkedin.card_selector_used", selector=card_sel, count=len(cards))
                    break

            if not cards:
                log.warning("linkedin.search.no_cards", scroll_pass=scroll_pass)
                break

            for card in cards:
                try:
                    link_el = None
                    for title_sel in _TITLE_SELECTORS:
                        link_el = await card.query_selector(title_sel)
                        if link_el:
                            break

                    if not link_el:
                        continue

                    href = await link_el.get_attribute("href") or ""
                    if not href or href in processed:
                        continue
                    processed.add(href)

                    title = (await link_el.inner_text()).strip()

                    company = ""
                    for comp_sel in _COMPANY_SELECTORS:
                        el = await card.query_selector(comp_sel)
                        if el:
                            company = (await el.inner_text()).strip()
                            break

                    location_text = location
                    for loc_sel in _LOCATION_SELECTORS:
                        el = await card.query_selector(loc_sel)
                        if el:
                            location_text = (await el.inner_text()).strip()
                            break

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

            log.debug("linkedin.scroll", pass_num=scroll_pass + 1, jobs_so_far=len(jobs))
            await page.evaluate("window.scrollBy(0, 1500)")
            await asyncio.sleep(random.uniform(1.5, 3))

        return jobs
