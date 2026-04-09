import asyncio
import structlog
from playwright.async_api import Page, TimeoutError as PWTimeout

from src.applier.base import BaseApplier
from src.queue.models import JobListing

log = structlog.get_logger()

_APPLY_SELECTORS = [
    'a:has-text("Apply Now")',
    'a:has-text("Apply")',
    'button:has-text("Apply Now")',
    'button:has-text("Apply")',
    'a[href*="apply"]',
]

_SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'button:has-text("Submit")',
    'input[type="submit"]',
]


class GenericApplier(BaseApplier):
    async def apply(self, job: JobListing) -> bool:
        async with self.browser.page("generic") as page:
            return await self._apply(page, job)

    async def _apply(self, page: Page, job: JobListing) -> bool:
        log.info("generic.apply.start", title=job.title, company=job.company)
        try:
            await page.goto(job.url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            log.warning("generic.apply.load_timeout", url=job.url)
            return False

        # Find and click apply button
        apply_btn = None
        for selector in _APPLY_SELECTORS:
            apply_btn = await page.query_selector(selector)
            if apply_btn:
                break

        if not apply_btn:
            log.info("generic.apply.no_button", url=job.url)
            return False

        await apply_btn.click()
        await page.wait_for_load_state("networkidle", timeout=10000)
        await asyncio.sleep(1)

        filled_fields: dict[str, str] = {}
        await self._fill_fields(page, job, filled_fields)

        submit_btn = None
        for selector in _SUBMIT_SELECTORS:
            submit_btn = await page.query_selector(selector)
            if submit_btn:
                break

        if not submit_btn:
            log.warning("generic.apply.no_submit", url=job.url)
            return False

        decision = self.ai.confirm_submission(job, filled_fields)
        if decision.action == "cancel":
            log.info("generic.apply.cancelled", reason=decision.reason)
            return False

        await submit_btn.click()
        log.info("generic.apply.submitted", title=job.title)
        return True

    async def _fill_fields(
        self, page: Page, job: JobListing, filled: dict[str, str]
    ) -> None:
        inputs = await page.query_selector_all(
            'input:not([type=hidden]):not([type=file]):not([type=submit]):not([type=checkbox]):not([type=radio]),'
            'textarea'
        )
        for inp in inputs:
            tag = await inp.evaluate("el => el.tagName.toLowerCase()")
            inp_id = await inp.get_attribute("id") or ""
            inp_name = await inp.get_attribute("name") or ""
            inp_placeholder = await inp.get_attribute("placeholder") or ""

            # Try to find an associated label
            label = ""
            if inp_id:
                label_el = await page.query_selector(f'label[for="{inp_id}"]')
                if label_el:
                    label = (await label_el.inner_text()).strip()
            label = label or inp_placeholder or inp_name

            current = await inp.input_value()
            if current:
                filled[label] = current
                continue

            resume_val = self._resume_value(label)
            if resume_val:
                await inp.fill(resume_val)
                filled[label] = resume_val
            elif label:
                if tag == "textarea" or len(label) > 30:
                    decision = self.ai.answer_question(label, job)
                    value = decision.answer
                else:
                    decision = self.ai.fill_field(label, "text", [], "", job)
                    value = decision.value
                if value:
                    await inp.fill(value)
                    filled[label] = value
