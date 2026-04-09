import json
import structlog
from anthropic import Anthropic, APIError

from src.ai.decisions import (
    ApplyDecision,
    CustomAnswerDecision,
    FALLBACK_ANSWER,
    FALLBACK_APPLY,
    FALLBACK_FIELD,
    FALLBACK_SUBMIT,
    FormFieldDecision,
    SubmitDecision,
)
from src.ai.prompts import (
    answer_question_prompt,
    candidate_system_prompt,
    confirm_submission_prompt,
    fill_field_prompt,
    should_apply_prompt,
)
from src.queue.models import JobListing
from src.resume.models import ResumeData

log = structlog.get_logger()


class AIClient:
    def __init__(
        self,
        api_key: str,
        decision_model: str = "claude-sonnet-4-6",
        fill_model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self._client = Anthropic(api_key=api_key)
        self._decision_model = decision_model
        self._fill_model = fill_model
        self._system: str = ""

    def set_resume(self, resume: ResumeData) -> None:
        self._system = candidate_system_prompt(resume)

    # ── Decision calls ───────────────────────────────────────────

    def should_apply(self, job: JobListing) -> ApplyDecision:
        raw = self._call(should_apply_prompt(job), model=self._decision_model)
        if raw is None:
            return FALLBACK_APPLY
        try:
            return ApplyDecision(**raw)
        except Exception:
            log.warning("ai.should_apply.parse_error", raw=raw)
            return FALLBACK_APPLY

    def fill_field(
        self,
        label: str,
        field_type: str,
        options: list[str],
        resume_value: str,
        job: JobListing,
    ) -> FormFieldDecision:
        raw = self._call(
            fill_field_prompt(label, field_type, options, resume_value, job),
            model=self._fill_model,
        )
        if raw is None:
            return FALLBACK_FIELD
        try:
            return FormFieldDecision(**raw)
        except Exception:
            log.warning("ai.fill_field.parse_error", raw=raw)
            return FALLBACK_FIELD

    def answer_question(self, question: str, job: JobListing) -> CustomAnswerDecision:
        raw = self._call(answer_question_prompt(question, job), model=self._fill_model)
        if raw is None:
            return FALLBACK_ANSWER
        try:
            return CustomAnswerDecision(**raw)
        except Exception:
            log.warning("ai.answer_question.parse_error", raw=raw)
            return FALLBACK_ANSWER

    def confirm_submission(self, job: JobListing, fields: dict[str, str]) -> SubmitDecision:
        raw = self._call(
            confirm_submission_prompt(job, fields), model=self._decision_model
        )
        if raw is None:
            return FALLBACK_SUBMIT
        try:
            return SubmitDecision(**raw)
        except Exception:
            log.warning("ai.confirm_submission.parse_error", raw=raw)
            return FALLBACK_SUBMIT

    # ── Internal ─────────────────────────────────────────────────

    def _call(self, user_prompt: str, model: str) -> dict | None:
        try:
            msg = self._client.messages.create(
                model=model,
                max_tokens=512,
                system=self._system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = msg.content[0].text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except APIError as e:
            log.error("ai.api_error", error=str(e), model=model)
            return None
        except (json.JSONDecodeError, IndexError) as e:
            log.error("ai.json_error", error=str(e), model=model)
            return None
