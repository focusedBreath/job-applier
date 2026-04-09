from fastapi import APIRouter
from pydantic import BaseModel

from src.api.tasks import TaskState, runner

router = APIRouter(tags=["status"])


class StatusResponse(BaseModel):
    type: str
    progress: int
    total: int
    error: str


@router.get("/tasks/status", response_model=StatusResponse)
async def task_status() -> StatusResponse:
    s = runner.state
    return StatusResponse(
        type=s.type.value,
        progress=s.progress,
        total=s.total,
        error=s.error,
    )
