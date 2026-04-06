import time
import random
from typing import Optional
from datetime import datetime

from .base_applier import BaseApplier, ApplicationResult
from ..scrapers.base_scraper import JobListing
from ..parser.resume_parser import ResumeData
from ..browser.browser_manager import BrowserManager, human_like_scroll
from ..ai.ai_overseer import AIOversight
from ..utils.logger import log


class GenericApplier(BaseApplier):
    def __init__(self, browser_manager: BrowserManager, ai_overseer: AIOversight):
        super().__init__("Generic")
        self.browser = browser_manager
        self.page: Optional[Page] = None
        self.ai = ai_overseer

    def _ensure_page(self):
        if not self.page:
            self.page = self.browser.get_page("generic_apply")

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

            human_like_scroll(self.page, 2)

            form_data = self._fill_generic_form(resume)

            submit_button = self._find_submit_button()

            if submit_button:
                confirmation = self.ai.confirm_application(
                    {
                        "title": job.title,
                        "company": job.company,
                        "platform": "Generic",
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
                        message="Application submitted",
                        form_filled=form_data,
                    )
                elif confirmation.get("action") == "review":
                    return ApplicationResult(
                        success=False,
                        job_listing=job,
                        timestamp=datetime.now().isoformat(),
                        message="Review pending - form filled but not submitted",
                        form_filled=form_data,
                    )

            return ApplicationResult(
                success=True,
                job_listing=job,
                timestamp=datetime.now().isoformat(),
                message="Form filled (submit manually if needed)",
                form_filled=form_data,
            )

        except Exception as e:
            log.error(f"Error in generic application: {e}")
            return ApplicationResult(
                success=False,
                job_listing=job,
                timestamp=datetime.now().isoformat(),
                error=str(e),
            )

    def _fill_generic_form(self, resume: ResumeData) -> dict:
        form_data = {}

        input_fields = self.page.query_selector_all(
            "input:not([type='hidden']):not([type='submit'])"
        )
        for inp in input_fields:
            try:
                if not inp.is_visible():
                    continue

                inp_type = inp.get_attribute("type")
                if inp_type in ["file", "checkbox", "radio"]:
                    continue

                label = self._find_label(inp)
                value = self._map_to_resume(
                    label, inp.get_attribute("name") or "", resume
                )

                if value:
                    inp.fill(value)
                    form_data[label] = value
            except:
                continue

        textareas = self.page.query_selector_all("textarea")
        for ta in textareas:
            try:
                if not ta.is_visible():
                    continue

                label = self._find_label(ta)

                if any(x in label.lower() for x in ["cover", "additional", "comments"]):
                    decision = self.ai.answer_custom_question(
                        f"Writing response for: {label}",
                        {"title": "Job Application"},
                        resume.to_dict() if hasattr(resume, "to_dict") else {},
                    )
                    if decision.get("action") == "generate":
                        ta.fill("I am excited to apply for this position...")
                        form_data[label] = "[AI Generated]"
            except:
                continue

        selects = self.page.query_selector_all("select")
        for sel in selects:
            try:
                if not sel.is_visible():
                    continue

                options = sel.query_selector_all("option")
                if len(options) > 1:
                    for opt in options:
                        opt_text = opt.inner_text().lower()
                        if "yes" in opt_text or "1-2" in opt_text:
                            sel.select_option(opt.get_attribute("value"))
                            break
            except:
                continue

        return form_data

    def _find_label(self, element) -> str:
        field_id = element.get_attribute("id")
        if field_id:
            label = self.page.query_selector(f"label[for='{field_id}']")
            if label:
                return label.inner_text().strip()

        parent = element.query_selector(
            "xpath=ancestor::div[contains(@class, 'field')]"
        )
        if parent:
            labels = parent.query_selector_all("label")
            if labels:
                return labels[0].inner_text().strip()

        parent_text = element.query_selector("xpath=preceding-sibling::*[1]")
        if parent_text:
            text = parent_text.inner_text().strip()
            if text and len(text) < 100:
                return text

        name = element.get_attribute("name") or ""
        placeholder = element.get_attribute("placeholder") or ""
        return placeholder or name

    def _map_to_resume(
        self, label: str, field_name: str, resume: ResumeData
    ) -> Optional[str]:
        combined = f"{label} {field_name}".lower()

        mappings = {
            "first name": lambda: (
                resume.personal.name.split()[0] if resume.personal.name else None
            ),
            "last name": lambda: (
                " ".join(resume.personal.name.split()[1:])
                if resume.personal.name
                else None
            ),
            "full name": lambda: resume.personal.name,
            "name": lambda: resume.personal.name,
            "email": lambda: resume.personal.email,
            "phone": lambda: resume.personal.phone,
            "telephone": lambda: resume.personal.phone,
            "mobile": lambda: resume.personal.phone,
            "address": lambda: resume.personal.location,
            "location": lambda: resume.personal.location,
            "city": lambda: (
                resume.personal.location.split(",")[0]
                if resume.personal.location
                else None
            ),
            "linkedin": lambda: resume.personal.linkedin,
            "github": lambda: resume.personal.github,
            "portfolio": lambda: resume.personal.website,
        }

        for key, getter in mappings.items():
            if key in combined:
                value = getter()
                if value:
                    return value

        return None

    def _find_submit_button(self):
        selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send')",
            "a:has-text('Submit')",
            "a:has-text('Apply')",
        ]

        for selector in selectors:
            try:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    return btn
            except:
                continue

        return None
