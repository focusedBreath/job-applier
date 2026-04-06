import json
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..utils.logger import log
from .ai_handler import AIHandler, LMStudioManager, create_ai_handler


DECISIONS_DIR = Path(__file__).parent.parent.parent / "decisions"


@dataclass
class DecisionRequest:
    id: str
    timestamp: str
    request_type: str
    context: dict
    status: str = "pending"
    response: Optional[dict] = None
    resolved_at: Optional[str] = None


class AIOversight:
    def __init__(
        self,
        pause_for_approval: bool = True,
        ai_handler: Optional[AIHandler] = None,
        lm_studio: Optional[LMStudioManager] = None,
    ):
        self.pause_for_approval = pause_for_approval
        self.ai_handler = ai_handler
        self.lm_studio = lm_studio
        self.pending_requests: dict[str, DecisionRequest] = {}
        DECISIONS_DIR.mkdir(parents=True, exist_ok=True)

    def ensure_ai_ready(self, resume_data=None) -> bool:
        if not self.ai_handler:
            log.info("No AI handler configured, using fallback mode")
            return False

        if self.ai_handler.is_available():
            log.info("AI handler is available")
            return True

        if not self.lm_studio:
            log.warning("No LM Studio manager configured")
            return False

        log.info("Attempting to start LM Studio...")
        if self.lm_studio.ensure_ready(resume_data):
            self.ai_handler._client = None
            return True

        log.warning("Failed to start LM Studio")
        return False

    def _request_decision(
        self,
        request_type: str,
        context: dict,
        options: Optional[list[dict]] = None,
        default_action: Optional[str] = None,
    ) -> dict:
        request_id = f"{request_type[:4]}_{int(time.time())}"

        request = DecisionRequest(
            id=request_id,
            timestamp=datetime.now().isoformat(),
            request_type=request_type,
            context=context,
        )

        self.pending_requests[request_id] = request

        request_file = DECISIONS_DIR / f"request_{request_id}.json"
        with open(request_file, "w") as f:
            json.dump(
                {
                    "id": request.id,
                    "timestamp": request.timestamp,
                    "request_type": request.request_type,
                    "context": context,
                    "options": options,
                    "status": request.status,
                },
                f,
                indent=2,
            )

        log.info(f"AI Oversight Request [{request_id}]: {request_type}")

        if self.ai_handler and self.ai_handler.is_available():
            log.info(f"Using AI handler for decision")
        else:
            log.info(f"No AI available, using file-based fallback")

        response_file = DECISIONS_DIR / f"response_{request_id}.json"

        start_time = time.time()
        timeout = 300

        while (time.time() - start_time) < timeout:
            if response_file.exists():
                with open(response_file) as f:
                    response = json.load(f)

                request.status = "resolved"
                request.response = response
                request.resolved_at = datetime.now().isoformat()

                log.info(
                    f"Decision received for [{request_id}]: {response.get('action', 'unknown')}"
                )
                response_file.unlink()
                return {
                    "action": response.get("action"),
                    "data": response.get("data"),
                    "request_id": request_id,
                }

            if self.ai_handler and self.ai_handler.is_available():
                break

            time.sleep(1)

        if request_file.exists():
            request_file.unlink()

        return None

    def should_apply_to_job(self, job_info: dict) -> dict:
        log.info(f"AI decision for job: {job_info.get('title', 'N/A')}")

        if self.ai_handler and self.ai_handler.is_available():
            try:
                result = self.ai_handler.decide_job_application(job_info)
                log.info(
                    f"AI decided: {result.get('action')} (source: {result.get('source')})"
                )
                return result
            except Exception as e:
                log.error(f"AI handler error: {e}")

        request_file = DECISIONS_DIR / f"request_job_{int(time.time())}.json"
        with open(request_file, "w") as f:
            json.dump(
                {
                    "type": "job_decision",
                    "job": job_info,
                    "timestamp": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        log.warning(f"No AI available. Request saved to {request_file}")
        log.warning("Using default action: proceed")

        if request_file.exists():
            request_file.unlink()

        return {"action": "proceed", "source": "default"}

    def fill_form_field(self, field_info: dict, resume_data: dict) -> dict:
        field_type = field_info.get("type", "text")
        field_label = field_info.get("label", field_info.get("name", "Unknown"))
        field_options = field_info.get("options", [])
        job_context = field_info.get("job_context", {})
        resume_value = resume_data.get(field_label.lower(), "")

        if self.ai_handler and self.ai_handler.is_available():
            try:
                result = self.ai_handler.decide_form_field(
                    field_label, field_type, field_options, resume_value
                )
                log.info(f"AI form field decision: {result.get('action')}")
                return result
            except Exception as e:
                log.error(f"AI handler error: {e}")

        if resume_value:
            return {"action": "use", "value": resume_value, "source": "resume"}

        return {"action": "skip", "value": None, "source": "default"}

    def answer_custom_question(
        self, question: str, job_info: dict, resume_data: dict
    ) -> dict:
        job_title = (
            job_info.get("title", "") if isinstance(job_info, dict) else str(job_info)
        )
        company = job_info.get("company", "") if isinstance(job_info, dict) else ""
        resume_summary = (
            resume_data.get("summary", "") if isinstance(resume_data, dict) else ""
        )

        if self.ai_handler and self.ai_handler.is_available():
            try:
                result = self.ai_handler.generate_answer(
                    question, job_title, company, resume_summary
                )
                log.info(f"AI generated answer for custom question")
                return result
            except Exception as e:
                log.error(f"AI handler error: {e}")

        log.warning("No AI available for custom question")
        return {"action": "skip", "value": None, "source": "default"}

    def handle_captcha(self, captcha_type: str, page_screenshot: str) -> dict:
        log.warning(f"CAPTCHA detected: {captcha_type}")
        log.warning("CAPTCHA requires manual intervention")

        return {
            "action": "skip",
            "source": "captcha",
            "message": "Manual intervention required",
        }

    def confirm_application(self, application_data: dict) -> dict:
        log.info(f"Confirming application: {application_data.get('title', 'N/A')}")

        if self.ai_handler and self.ai_handler.is_available():
            try:
                result = self.ai_handler.confirm_submission(application_data)
                log.info(f"AI confirmation: {result.get('action')}")
                return result
            except Exception as e:
                log.error(f"AI handler error: {e}")

        log.warning("No AI available for confirmation")
        log.warning("Using default action: submit")

        return {"action": "submit", "source": "default"}

    def report_status(self, message: str, level: str = "info"):
        status_file = DECISIONS_DIR / "current_status.json"
        with open(status_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": level,
                    "message": message,
                },
                f,
            )

    def cleanup(self):
        if self.lm_studio:
            log.info("Cleaning up LM Studio...")
            self.lm_studio.cleanup()


def create_ai_overseer(config: dict = None) -> AIOversight:
    if not config:
        log.info("No config provided, creating overseer without AI")
        return AIOversight(pause_for_approval=True)

    ai_config = config.get("ai", {})

    lm_studio, ai_handler = create_ai_handler(config)

    overseer = AIOversight(
        pause_for_approval=ai_config.get("pause_for_approval", True),
        ai_handler=ai_handler,
        lm_studio=lm_studio,
    )

    return overseer
