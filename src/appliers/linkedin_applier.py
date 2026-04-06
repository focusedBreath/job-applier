import time
import random
from typing import Optional
from datetime import datetime
from playwright.sync_api import Page

from .base_applier import BaseApplier, ApplicationResult
from ..scrapers.base_scraper import JobListing
from ..parser.resume_parser import ResumeData
from ..browser.browser_manager import (
    BrowserManager,
    human_like_scroll,
    human_like_mouse_move,
)
from ..ai.ai_overseer import AIOversight
from ..utils.logger import log


class LinkedInApplier(BaseApplier):
    def __init__(self, browser_manager: BrowserManager, ai_overseer: AIOversight):
        super().__init__("LinkedIn Easy Apply")
        self.browser = browser_manager
        self.page: Optional[Page] = None
        self.ai = ai_overseer

    def _ensure_page(self):
        if not self.page:
            self.page = self.browser.get_page("linkedin_apply")

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

            log.info(f"Applying to: {job.title} at {job.company}")
            self.page.goto(job.url, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))

            apply_button = self.page.query_selector("button.jobs-apply-button")
            if not apply_button:
                log.warning("No Easy Apply button found")
                return ApplicationResult(
                    success=False,
                    job_listing=job,
                    timestamp=datetime.now().isoformat(),
                    error="No apply button found",
                )

            apply_button.click()
            time.sleep(random.uniform(1, 3))

            form_data = {}

            while True:
                form_data = self._fill_current_step(form_data, resume)

                next_button = self.page.query_selector(
                    "button[aria-label='Continue to next step']"
                )
                submit_button = self.page.query_selector(
                    "button[aria-label='Submit application']"
                )

                if submit_button:
                    submit_button.click()
                    time.sleep(random.uniform(2, 4))

                    confirmation = self.ai.confirm_application(
                        {
                            "title": job.title,
                            "company": job.company,
                            "platform": "LinkedIn",
                            "form_data": form_data,
                        }
                    )

                    if confirmation.get("action") == "cancel":
                        return ApplicationResult(
                            success=False,
                            job_listing=job,
                            timestamp=datetime.now().isoformat(),
                            message="Cancelled by user",
                            form_filled=form_data,
                        )

                    return ApplicationResult(
                        success=True,
                        job_listing=job,
                        timestamp=datetime.now().isoformat(),
                        message="Application submitted successfully",
                        form_filled=form_data,
                    )

                if next_button:
                    next_button.click()
                    time.sleep(random.uniform(1, 2))
                else:
                    break

            return ApplicationResult(
                success=True,
                job_listing=job,
                timestamp=datetime.now().isoformat(),
                message="Application flow completed",
                form_filled=form_data,
            )

        except Exception as e:
            log.error(f"Error applying to LinkedIn job: {e}")
            return ApplicationResult(
                success=False,
                job_listing=job,
                timestamp=datetime.now().isoformat(),
                error=str(e),
            )

    def _fill_current_step(self, form_data: dict, resume: ResumeData) -> dict:
        text_inputs = self.page.query_selector_all("input[type='text']")
        for inp in text_inputs:
            try:
                label = self._get_input_label(inp)
                field_value = self._get_resume_field(label, resume)

                if field_value:
                    inp.fill(field_value)
                    form_data[label] = field_value
            except:
                continue

        textareas = self.page.query_selector_all("textarea")
        for ta in textareas:
            try:
                label = self._get_input_label(ta)
                if "cover" in label.lower() or "additional" in label.lower():
                    decision = self.ai.answer_custom_question(
                        f"Cover letter prompt: {label}",
                        {"title": "Job Application"},
                        resume.to_dict() if hasattr(resume, "to_dict") else {},
                    )
                    if decision.get("action") == "generate":
                        ta.fill(f"Based on my experience and skills...")
            except:
                continue

        dropdowns = self.page.query_selector_all("select")
        for dropdown in dropdowns:
            try:
                dropdown.select_option(
                    index=1 if dropdown.query_selector_all("option") else 0
                )
            except:
                continue

        checkboxes = self.page.query_selector_all("input[type='checkbox']")
        for cb in checkboxes:
            try:
                if not cb.is_checked():
                    cb.check()
            except:
                continue

        return form_data

    def _get_input_label(self, element) -> str:
        container = element.query_selector(
            "xpath=ancestor::div[contains(@class, 'fb-form-element')]"
        )
        if container:
            label_elem = container.query_selector("label")
            if label_elem:
                return label_elem.inner_text().strip()

        parent = element.query_selector("xpath=ancestor::div[1]")
        if parent:
            prev = parent.query_selector("xpath=preceding-sibling::div[1]")
            if prev:
                return prev.inner_text().strip()

        name = element.get_attribute("name") or element.get_attribute("id") or ""
        return name

    def _get_resume_field(self, label: str, resume: ResumeData) -> Optional[str]:
        label_lower = label.lower()

        field_mapping = {
            "phone": resume.personal.phone,
            "email": resume.personal.email,
            "name": resume.personal.name,
            "location": resume.personal.location,
            "city": resume.personal.location.split(",")[0]
            if resume.personal.location
            else "",
            "state": resume.personal.location.split(",")[-1].strip()
            if resume.personal.location
            else "",
            "linkedin": resume.personal.linkedin,
            "github": resume.personal.github,
        }

        for key, value in field_mapping.items():
            if key in label_lower and value:
                return value

        return None
