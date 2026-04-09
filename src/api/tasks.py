"""Background task runner — ensures only one scrape or apply runs at a time."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger()


class TaskType(str, Enum):
    IDLE = "idle"
    SCRAPING = "scraping"
    APPLYING = "applying"


@dataclass
class TaskState:
    type: TaskType = TaskType.IDLE
    progress: int = 0
    total: int = 0
    error: str = ""


class TaskRunner:
    def __init__(self) -> None:
        self._state = TaskState()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state.type != TaskType.IDLE

    async def run(self, task_type: TaskType, coro) -> None:
        if self.is_running:
            raise RuntimeError(f"Task already running: {self._state.type}")
        self._state = TaskState(type=task_type)
        self._task = asyncio.create_task(self._run(coro))

    async def _run(self, coro) -> None:
        try:
            await coro
        except Exception as e:
            log.error("task.error", error=str(e), task=self._state.type)
            self._state.error = str(e)
        finally:
            self._state = TaskState(type=TaskType.IDLE)

    def update_progress(self, progress: int, total: int) -> None:
        self._state.progress = progress
        self._state.total = total


runner = TaskRunner()
