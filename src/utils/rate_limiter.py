import asyncio
import random
import structlog
from datetime import date

log = structlog.get_logger()


class RateLimiter:
    def __init__(
        self,
        min_seconds: float = 10,
        max_seconds: float = 30,
        max_per_day: int = 50,
    ) -> None:
        self._min = min_seconds
        self._max = max_seconds
        self._max_per_day = max_per_day
        self._count_today: int = 0
        self._last_date: date = date.today()
        self._multiplier: float = 1.0

    @property
    def applied_today(self) -> int:
        self._reset_if_new_day()
        return self._count_today

    @property
    def at_limit(self) -> bool:
        self._reset_if_new_day()
        return self._count_today >= self._max_per_day

    async def wait(self) -> None:
        delay = random.uniform(self._min, self._max) * self._multiplier
        log.debug("rate_limiter.waiting", seconds=round(delay, 1))
        await asyncio.sleep(delay)

    def record_success(self) -> None:
        self._reset_if_new_day()
        self._count_today += 1
        self._multiplier = max(0.8, self._multiplier * 0.95)

    def record_error(self) -> None:
        self._multiplier = min(2.0, self._multiplier * 1.2)
        log.warning("rate_limiter.backing_off", multiplier=round(self._multiplier, 2))

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._last_date:
            self._count_today = 0
            self._last_date = today
            self._multiplier = 1.0
