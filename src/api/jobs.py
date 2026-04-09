from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.queue.models import JobListing, JobStats, JobStatus, Platform
from src.queue.store import JobStore
from src.api.deps import get_store

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobPage(BaseModel):
    items: list[JobListing]
    total: int
    offset: int
    limit: int


class StatusUpdate(BaseModel):
    status: JobStatus
    reason: str = ""


@router.get("", response_model=JobPage)
async def list_jobs(
    status: JobStatus | None = None,
    platform: Platform | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    store: JobStore = Depends(get_store),
) -> JobPage:
    items, total = await store.list_jobs(status=status, platform=platform, offset=offset, limit=limit)
    return JobPage(items=items, total=total, offset=offset, limit=limit)


@router.get("/stats", response_model=JobStats)
async def job_stats(store: JobStore = Depends(get_store)) -> JobStats:
    return await store.stats()


@router.patch("/{job_id}", response_model=dict)
async def update_job_status(
    job_id: int,
    body: StatusUpdate,
    store: JobStore = Depends(get_store),
) -> dict:
    await store.update_status(job_id, body.status, skip_reason=body.reason)
    return {"ok": True}
