import json
import random
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    ViewportSize,
)
from fake_useragent import UserAgent

from ..config import BrowserConfig
from ..utils.logger import log


SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"


class BrowserManager:
    def __init__(self, config: BrowserConfig):
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: dict[str, BrowserContext] = {}
        self.ua = UserAgent()

    def start(self):
        if self.playwright:
            return

        self.playwright = sync_playwright().start()
        log.info("Playwright started")

    def launch_browser(self, user_data_dir: Optional[str] = None) -> Browser:
        self.start()

        if self.browser:
            return self.browser

        context_args = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo,
        }

        if user_data_dir:
            context_args["user_data_dir"] = user_data_dir

        try:
            self.browser = self.playwright.chromium.launch(**context_args)
            log.info("Browser launched")
        except Exception as e:
            log.error(f"Failed to launch browser: {e}")
            raise

        return self.browser

    def create_context(self, name: str = "default") -> BrowserContext:
        if not self.browser:
            self.launch_browser()

        if name in self.contexts:
            return self.contexts[name]

        ua_string = self.ua.random

        context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=ua_string,
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            },
        )

        self._apply_stealth(context)

        self.contexts[name] = context
        log.info(f"Browser context '{name}' created")

        return context

    def _apply_stealth(self, context: BrowserContext):
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            window.chrome = { runtime: {} };
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
            });
            
            Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
                value: function() {
                    return null;
                }
            });
            
            CanvasRenderingContext2D.prototype.roundRect = function() {};
        """)

    def get_page(self, context_name: str = "default") -> Page:
        context = self.create_context(context_name)
        page = context.new_page()
        page.set_default_timeout(self.config.timeout)
        return page

    def save_session(self, context_name: str, session_file: Optional[str] = None):
        if context_name not in self.contexts:
            log.warning(f"Context '{context_name}' not found")
            return

        session_file = session_file or f"{context_name}_session.json"
        session_path = SESSIONS_DIR / session_file

        context = self.contexts[context_name]

        storage = context.storage_state()
        session_path.parent.mkdir(parents=True, exist_ok=True)

        with open(session_path, "w") as f:
            json.dump(storage, f, indent=2)

        log.info(f"Session saved to {session_path}")

    def load_session(
        self, context_name: str, session_file: Optional[str] = None
    ) -> bool:
        session_file = session_file or f"{context_name}_session.json"
        session_path = SESSIONS_DIR / session_file

        if not session_path.exists():
            log.info(f"No saved session found at {session_path}")
            return False

        self.start()
        self.launch_browser()

        context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self.ua.random,
            storage_state=str(session_path),
        )

        self._apply_stealth(context)
        self.contexts[context_name] = context

        log.info(f"Session loaded from {session_path}")
        return True

    def close_context(self, name: str = "default"):
        if name in self.contexts:
            try:
                self.contexts[name].close()
            except Exception as e:
                log.debug(f"Context '{name}' close error (may already be closed): {e}")
            finally:
                if name in self.contexts:
                    del self.contexts[name]
                    log.info(f"Context '{name}' closed")

    def close(self):
        for name in list(self.contexts.keys()):
            self.close_context(name)

        if self.browser:
            self.browser.close()
            self.browser = None
            log.info("Browser closed")

        if self.playwright:
            self.playwright.stop()
            self.playwright = None
            log.info("Playwright stopped")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def human_like_scroll(page: Page, iterations: int = 3):
    for _ in range(iterations):
        page.mouse.wheel(0, random.randint(200, 500))
        time.sleep(random.uniform(0.2, 0.5))


def human_like_mouse_move(page: Page, element):
    box = element.bounding_box()
    if box:
        start_x = random.randint(int(box["x"]), int(box["x"] + box["width"]))
        start_y = random.randint(int(box["y"]), int(box["y"] + box["height"]))

        page.mouse.move(start_x, start_y)
        time.sleep(random.uniform(0.1, 0.3))


def random_typing(page: Page, text: str, min_delay: int = 50, max_delay: int = 150):
    for char in text:
        page.keyboard.type(char, delay=random.randint(min_delay, max_delay))
