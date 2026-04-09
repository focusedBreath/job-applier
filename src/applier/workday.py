import asyncio
import structlog
from playwright.async_api import Page, TimeoutError as PWTimeout

from src.applier.base import BaseApplier
from src.queue.models import JobListing

log = structlog.get_logger()


class WorkdayApplier(BaseApplier):
    async def apply(self, job: JobListing) -> bool:
        async with self.browser.page("workday") as page:
            return await self._apply(page, job)

    async def _apply(self, page: Page, job: JobListing) -> bool:
        log.info("workday.apply.start", title=job.title, company=job.company)
        try:
            await page.goto(job.url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            log.warning("workday.apply.load_timeout", url=job.url)
            return False

        apply_btn = await page.query_selector('a[data-automation-id="applyNowButton"]')
        if not apply_btn:
            log.info("workday.apply.no_button", url=job.url)
            return False

        await apply_btn.click()
        await asyncio.sleep(2)

        filled_fields: dict[str, str] = {}
        max_steps = 15

        for step in range(max_steps):
            await self._fill_workday_fields(page, job, filled_fields)

            # Submit
            submit_btn = await page.query_selector('button[data-automation-id="bottom-navigation-next-button"]:has-text("Submit")')
            if submit_btn:
                decision = self.ai.confirm_submission(job, filled_fields)
                if decision.action == "cancel":
                    log.info("workday.apply.cancelled", reason=decision.reason)
                    return False
                await submit_btn.click()
                log.info("workday.apply.submitted", title=job.title)
                return True

            next_btn = await page.query_selector(
                'button[data-automation-id="bottom-navigation-next-button"]'
            )
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(1.5)
            else:
                log.warning("workday.apply.stuck", step=step)
                break

        log.warning("workday.apply.incomplete", title=job.title)
        return False

    async def _fill_workday_fields(
        self, page: Page, job: JobListing, filled: dict[str, str]
    ) -> None:
        inputs = await page.query_selector_all(
            'input[data-automation-id]:not([type=hidden]):not([type=file]),'
            'textarea[data-automation-id]'
        )
        for inp in inputs:
            automation_id = await inp.get_attribute("data-automation-id") or ""
            current = await inp.input_value()
            if current:
                filled[automation_id] = current
                continue

            resume_val = self._resume_value(automation_id.replace("-", " "))
            if resume_val:
                await inp.fill(resume_val)
                filled[automation_id] = resume_val
            else:
                decision = self.ai.fill_field(automation_id, "text", [], "", job)
                if decision.value:
                    await inp.fill(decision.value)
                    filled[automation_id] = decision.value

        # Dropdowns
        selects = await page.query_selector_all('select[data-automation-id]')
        for sel in selects:
            automation_id = await sel.get_attribute("data-automation-id") or ""
            options_els = await sel.query_selector_all("option")
            options = [await o.inner_text() for o in options_els if await o.get_attribute("value")]
            resume_val = self._resume_value(automation_id.replace("-", " "))
            decision = self.ai.fill_field(automation_id, "select", options, resume_val, job)
            if decision.value and decision.value in options:
                await sel.select_option(label=decision.value)
                filled[automation_id] = decision.value
