import time
import random
from typing import Optional, Dict, Any
from datetime import datetime
from playwright.sync_api import Page

from .base_applier import BaseApplier, ApplicationResult
from ..scrapers.base_scraper import JobListing
from ..parser.resume_parser import ResumeData
from ..browser.browser_manager import BrowserManager, human_like_scroll
from ..ai.ai_overseer import AIOversight
from ..utils.logger import log


class WorkdayApplier(BaseApplier):
    WORKDAY_INDICATORS = ["workday.com", "myworkday.com", "/workday/"]

    def __init__(self, browser_manager: BrowserManager, ai_overseer: AIOversight):
        super().__init__("Workday")
        self.browser = browser_manager
        self.page: Optional[Page] = None
        self.ai = ai_overseer

    def is_workday_url(self, url: str) -> bool:
        return any(indicator in url.lower() for indicator in self.WORKDAY_INDICATORS)

    def _ensure_page(self):
        if not self.page:
            self.page = self.browser.get_page("workday_apply")

    def apply(self, job: JobListing, resume: ResumeData) -> ApplicationResult:
        self._ensure_page()

        try:
            decision = self.ai.should_apply_to_job(job.to_dict())
            if decision.get("action") == "skip":
                return ApplicationResult(
                    success=False,
                    job_listing=job,
                    timestamp=datetime.now().isoformat(),
                    message="Skipped by AI oversight",
                )

            log.info(f"Applying to Workday job: {job.title} at {job.company}")
            self.page.goto(job.url, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))

            form_data = {}

            steps = 0
            max_steps = 10

            while steps < max_steps:
                step_data = self._process_current_step(resume)
                form_data.update(step_data)

                next_button = self._find_next_button()
                if not next_button:
                    break

                next_button.click()
                time.sleep(random.uniform(1, 3))
                steps += 1

            submit_button = self._find_submit_button()
            if submit_button:
                confirmation = self.ai.confirm_application(
                    {
                        "title": job.title,
                        "company": job.company,
                        "platform": "Workday",
                        "form_data": form_data,
                    }
                )

                if confirmation.get("action") == "submit":
                    submit_button.click()
                    time.sleep(random.uniform(2, 4))

                    return ApplicationResult(
                        success=True,
                        job_listing=job,
                        timestamp=datetime.now().isoformat(),
                        message="Workday application submitted",
                        form_filled=form_data,
                    )

            return ApplicationResult(
                success=True,
                job_listing=job,
                timestamp=datetime.now().isoformat(),
                message="Application form completed (submit manually if needed)",
                form_filled=form_data,
            )

        except Exception as e:
            log.error(f"Error applying to Workday job: {e}")
            return ApplicationResult(
                success=False,
                job_listing=job,
                timestamp=datetime.now().isoformat(),
                error=str(e),
            )

    def _process_current_step(self, resume: ResumeData) -> dict:
        form_data = {}

        text_fields = self.page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset'])"
        )

        for field in text_fields:
            try:
                field_id = (
                    field.get_attribute("id") or field.get_attribute("name") or ""
                )
                label = self._find_label_for_field(field)
                value = self._map_field_to_resume(label, field_id, resume)

                if value:
                    field.fill(value)
                    form_data[label or field_id] = value
            except:
                continue

        textareas = self.page.query_selector_all("textarea")
        for ta in textareas:
            try:
                label = self._find_label_for_field(ta)
                if any(
                    x in label.lower()
                    for x in ["cover", "additional", "comments", "experience"]
                ):
                    decision = self.ai.answer_custom_question(
                        f"{label}",
                        {"title": "Job Application"},
                        resume.to_dict() if hasattr(resume, "to_dict") else {},
                    )
                    if decision.get("action") == "generate":
                        text = f"I am excited to apply for this position... "
                        ta.fill(text)
                        form_data[label] = "[AI Generated]"
            except:
                continue

        dropdowns = self.page.query_selector_all("select")
        for dropdown in dropdowns:
            try:
                options = dropdown.query_selector_all("option")
                if len(options) > 1:
                    dropdown.select_option(index=1)
            except:
                continue

        checkboxes = self.page.query_selector_all("input[type='checkbox']")
        for cb in checkboxes:
            try:
                label = self._find_label_for_field(cb)
                if "legal" in label.lower() or "authorized" in label.lower():
                    if not cb.is_checked():
                        cb.check()
            except:
                continue

        return form_data

    def _find_label_for_field(self, field) -> str:
        field_id = field.get_attribute("id")
        if field_id:
            label = self.page.query_selector(f"label[for='{field_id}']")
            if label:
                return label.inner_text().strip()

        container = field.query_selector(
            "xpath=ancestor::div[contains(@class, 'field')]"
        )
        if container:
            label_elem = container.query_selector("label")
            if label_elem:
                return label_elem.inner_text().strip()

        return ""

    def _map_field_to_resume(
        self, label: str, field_id: str, resume: ResumeData
    ) -> Optional[str]:
        label_lower = (label + " " + field_id).lower()

        mappings = {
            "first name": resume.personal.name.split()[0]
            if resume.personal.name
            else None,
            "last name": " ".join(resume.personal.name.split()[1:])
            if resume.personal.name
            else None,
            "email": resume.personal.email,
            "phone": resume.personal.phone,
            "location": resume.personal.location,
            "linkedin": resume.personal.linkedin,
        }

        for key, value in mappings.items():
            if key in label_lower and value:
                return value

        return None

    def _find_next_button(self):
        selectors = [
            "button[data-automation-id='nextButton']",
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "a:has-text('Next')",
            "[data-automation-id='nextButton']",
        ]

        for selector in selectors:
            try:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    return btn
            except:
                continue

        return None

    def _find_submit_button(self):
        selectors = [
            "button[data-automation-id='submitButton']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "a:has-text('Submit')",
            "[data-automation-id='submitButton']",
        ]

        for selector in selectors:
            try:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    return btn
            except:
                continue

        return None
