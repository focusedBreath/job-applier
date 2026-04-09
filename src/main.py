from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.ai.client import AIClient
from src.api import apply, jobs, resume, scrape, settings, status, ws
from src.api.deps import init_deps
from src.config import Config
from src.queue.store import JobStore
from src.utils.browser import BrowserManager
from src.utils.logging import configure_logging

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    config = Config()

    # Apply any runtime overrides saved via the Settings UI
    from src.api.settings import load_settings
    overrides = load_settings(config)
    for key, value in overrides.items():
        if hasattr(config, key):
            object.__setattr__(config, key, value)

    store = JobStore(config.db_path)
    await store.init()

    browser = BrowserManager(config.sessions_dir)
    await browser.start()

    ai = AIClient(
        api_key=config.claude_api_key,
        decision_model=config.claude_decision_model,
        fill_model=config.claude_fill_model,
    )

    init_deps(config, store, browser, ai)
    log.info("app.started")

    yield

    await browser.stop()
    log.info("app.stopped")


app = FastAPI(title="Job Applier", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(jobs.router, prefix="/api")
app.include_router(scrape.router, prefix="/api")
app.include_router(apply.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(ws.router)

# Serve compiled React frontend (present after Docker build)
_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="ui")
