import time
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

from ..utils.logger import log


@dataclass
class RateLimitState:
    last_action: float = field(default_factory=time.time)
    action_count_today: int = 0
    day_started: str = ""

    def should_wait(self, min_delay: int, max_delay: int) -> tuple[bool, float]:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        if self.day_started != today:
            self.day_started = today
            self.action_count_today = 0

        self.action_count_today += 1

        elapsed = time.time() - self.last_action
        delay = random.uniform(min_delay, max_delay)

        if elapsed < delay:
            return True, delay - elapsed

        self.last_action = time.time()
        return False, 0


class RateLimiter:
    def __init__(self, min_delay: int = 15, max_delay: int = 60, max_per_day: int = 50):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_per_day = max_per_day
        self.state = RateLimitState()
        self.lock = Lock()
        self.applications_today: list[datetime] = []

    def wait_if_needed(self) -> float:
        with self.lock:
            should_wait, wait_time = self.state.should_wait(
                self.min_delay, self.max_delay
            )

            if self.state.action_count_today > self.max_per_day:
                log.warning(f"Daily limit reached ({self.max_per_day} applications)")
                return -1

            if should_wait:
                log.info(f"Rate limiting: waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                return wait_time

            return 0

    def add_jitter(self, base_delay: float, jitter_percent: float = 0.3) -> float:
        jitter = base_delay * jitter_percent * random.uniform(-1, 1)
        return max(1, base_delay + jitter)

    def human_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        delay = random.uniform(min_seconds, max_seconds)
        log.debug(f"Human-like delay: {delay:.2f}s")
        time.sleep(delay)

    def scroll_pause(self):
        self.human_delay(0.3, 0.8)

    def page_load_delay(self):
        self.human_delay(1.0, 2.5)


class AdaptiveRateLimiter(RateLimiter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_count = 0
        self.success_count = 0
        self.current_multiplier = 1.0

    def record_success(self):
        self.success_count += 1
        self.error_count = 0
        self.current_multiplier = max(0.5, self.current_multiplier - 0.1)
        log.debug(f"Success recorded. Speed multiplier: {self.current_multiplier:.2f}")

    def record_error(self):
        self.error_count += 1
        self.current_multiplier = min(3.0, self.current_multiplier + 0.5)
        log.warning(f"Error recorded. Speed multiplier: {self.current_multiplier:.2f}")

        if self.error_count >= 3:
            log.warning("Multiple errors detected. Slowing down significantly.")
            time.sleep(30)

    def wait_if_needed(self) -> float:
        with self.lock:
            should_wait, wait_time = self.state.should_wait(
                self.min_delay * self.current_multiplier,
                self.max_delay * self.current_multiplier,
            )

            if self.state.action_count_today > self.max_per_day:
                return -1

            if should_wait:
                actual_wait = wait_time * self.current_multiplier
                log.info(
                    f"Rate limiting: waiting {actual_wait:.1f}s (multiplier: {self.current_multiplier:.2f})"
                )
                time.sleep(actual_wait)
                return actual_wait

            self.state.last_action = time.time()
            return 0
