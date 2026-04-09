import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.ai.client import AIClient
from src.api.deps import get_ai, get_browser, get_config, get_resume, get_store
from src.api.tasks import TaskType, runner
from src.applier.generic import GenericApplier
from src.applier.linkedin import LinkedInApplier
from src.applier.workday import WorkdayApplier
from src.config import Config
from src.queue.models import JobStatus, Platform
from src.queue.store import JobStore
from src.resume.models import ResumeData
from src.utils.browser import BrowserManager
from src.utils.rate_limiter import RateLimiter

log = structlog.get_logger()

router = APIRouter(prefix="/apply", tags=["apply"])


class ApplyRequest(BaseModel):
    platforms: list[Platform] | None = None
    limit: int = 50
    dry_run: bool = False


class ApplyResponse(BaseModel):
    started: bool
    message: str


def _detect_applier(job_url: str):
    if "linkedin.com" in job_url:
        return "linkedin"
    if "myworkdayjobs.com" in job_url or "wd1.myworkday" in job_url:
        return "workday"
    return "generic"


@router.post("", response_model=ApplyResponse)
async def start_apply(
    body: ApplyRequest,
    config: Config = Depends(get_config),
    store: JobStore = Depends(get_store),
    browser: BrowserManager = Depends(get_browser),
    ai: AIClient = Depends(get_ai),
    resume: ResumeData = Depends(get_resume),
) -> ApplyResponse:
    if runner.is_running:
        raise HTTPException(409, f"Task already running: {runner.state.type}")

    async def _run() -> None:
        rate = RateLimiter(
            min_seconds=config.delay_min_seconds,
            max_seconds=config.delay_max_seconds,
            max_per_day=body.limit,
        )
        ai.set_resume(resume)

        appliers = {
            "linkedin": LinkedInApplier(browser, ai, resume),
            "workday": WorkdayApplier(browser, ai, resume),
            "generic": GenericApplier(browser, ai, resume),
        }

        jobs = await store.get_pending(
            platforms=body.platforms, limit=body.limit
        )
        log.info("apply.start", total=len(jobs), dry_run=body.dry_run)

        for i, job in enumerate(jobs):
            runner.update_progress(i + 1, len(jobs))
            if rate.at_limit:
                log.info("apply.daily_limit_reached")
                break

            # AI: should we apply?
            decision = ai.should_apply(job)
            log.info(
                "apply.decision",
                title=job.title,
                company=job.company,
                action=decision.action,
                reason=decision.reason,
            )

            if decision.action == "skip":
                await store.update_status(
                    job.id, JobStatus.SKIPPED,
                    skip_reason=decision.reason,
                    ai_reason=decision.reason,
                )
                continue

            if decision.action == "save":
                # Keep as pending — don't apply yet
                continue

            if body.dry_run:
                log.info("apply.dry_run", title=job.title)
                continue

            applier_key = _detect_applier(job.url)
            applier = appliers[applier_key]

            try:
                success = await applier.apply(job)
                if success:
                    await store.update_status(
                        job.id, JobStatus.APPLIED, ai_reason=decision.reason
                    )
                    rate.record_success()
                else:
                    await store.update_status(
                        job.id, JobStatus.FAILED, error="Applier returned False"
                    )
                    rate.record_error()
            except Exception as e:
                log.error("apply.error", title=job.title, error=str(e))
                await store.update_status(job.id, JobStatus.FAILED, error=str(e))
                rate.record_error()

            await rate.wait()

        log.info("apply.done", applied=rate.applied_today)

    await runner.run(TaskType.APPLYING, _run())
    return ApplyResponse(started=True, message="Apply started")
