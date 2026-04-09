import asyncio
import structlog
from playwright.async_api import Page, TimeoutError as PWTimeout

from src.ai.client import AIClient
from src.applier.base import BaseApplier
from src.queue.models import JobListing
from src.resume.models import ResumeData
from src.utils.browser import BrowserManager

log = structlog.get_logger()


class LinkedInApplier(BaseApplier):
    async def apply(self, job: JobListing) -> bool:
        async with self.browser.page("linkedin") as page:
            return await self._apply(page, job)

    async def _apply(self, page: Page, job: JobListing) -> bool:
        log.info("linkedin.apply.start", title=job.title, company=job.company)
        try:
            await page.goto(job.url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            log.warning("linkedin.apply.load_timeout", url=job.url)
            return False

        # Find Easy Apply button
        easy_apply_btn = await page.query_selector(
            'button.jobs-apply-button[aria-label*="Easy Apply"]'
        )
        if not easy_apply_btn:
            log.info("linkedin.apply.no_easy_apply", url=job.url)
            return False

        await easy_apply_btn.click()
        await asyncio.sleep(1)

        filled_fields: dict[str, str] = {}
        max_steps = 10

        for step in range(max_steps):
            modal = await page.query_selector("div.jobs-easy-apply-modal")
            if not modal:
                break

            # Fill visible form fields
            await self._fill_form_fields(page, job, filled_fields)

            # Check for submit button
            submit_btn = await page.query_selector(
                'button[aria-label="Submit application"]'
            )
            if submit_btn:
                decision = self.ai.confirm_submission(job, filled_fields)
                if decision.action == "cancel":
                    log.info("linkedin.apply.cancelled", reason=decision.reason)
                    dismiss = await page.query_selector('button[aria-label="Dismiss"]')
                    if dismiss:
                        await dismiss.click()
                    return False
                if decision.action == "review":
                    log.warning("linkedin.apply.needs_review", reason=decision.reason)
                    # Continue and submit anyway — human can check the confirmation email
                await submit_btn.click()
                log.info("linkedin.apply.submitted", title=job.title, company=job.company)
                return True

            # Next step
            next_btn = await page.query_selector('button[aria-label="Continue to next step"]')
            review_btn = await page.query_selector('button[aria-label="Review your application"]')
            btn = next_btn or review_btn
            if btn:
                await btn.click()
                await asyncio.sleep(0.8)
            else:
                log.warning("linkedin.apply.stuck", step=step)
                break

        log.warning("linkedin.apply.incomplete", title=job.title)
        return False

    async def _fill_form_fields(
        self, page: Page, job: JobListing, filled: dict[str, str]
    ) -> None:
        # Text inputs and textareas
        inputs = await page.query_selector_all(
            "div.jobs-easy-apply-form-section__grouping input:not([type=hidden]):not([type=file]),"
            "div.jobs-easy-apply-form-section__grouping textarea"
        )
        for inp in inputs:
            label_el = await inp.query_selector("xpath=ancestor::div[@class]//label")
            label = (await label_el.inner_text()).strip() if label_el else ""
            if not label:
                continue
            current_val = await inp.input_value()
            if current_val:
                filled[label] = current_val
                continue

            resume_val = self._resume_value(label)
            if resume_val:
                value = resume_val
            else:
                # Check if it's a question (longer label)
                if len(label) > 30:
                    decision = self.ai.answer_question(label, job)
                    value = decision.answer
                else:
                    decision = self.ai.fill_field(label, "text", [], resume_val, job)
                    value = decision.value

            if value:
                await inp.fill(value)
                filled[label] = value

        # Select dropdowns
        selects = await page.query_selector_all(
            "div.jobs-easy-apply-form-section__grouping select"
        )
        for sel in selects:
            label_el = await sel.query_selector("xpath=ancestor::div[@class]//label")
            label = (await label_el.inner_text()).strip() if label_el else ""
            options_els = await sel.query_selector_all("option")
            options = [await o.inner_text() for o in options_els]
            resume_val = self._resume_value(label)
            decision = self.ai.fill_field(label, "select", options, resume_val, job)
            if decision.value and decision.value in options:
                await sel.select_option(label=decision.value)
                filled[label] = decision.value
