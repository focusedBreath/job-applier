"""FastAPI dependency providers — injected into route handlers."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException

from src.ai.client import AIClient
from src.config import Config
from src.queue.store import JobStore
from src.resume.models import ResumeData
from src.resume.parser import load_overrides, parse_docx
from src.utils.browser import BrowserManager

# These are initialized once at app startup and reused
_config: Config | None = None
_store: JobStore | None = None
_browser: BrowserManager | None = None
_ai: AIClient | None = None


def init_deps(config: Config, store: JobStore, browser: BrowserManager, ai: AIClient) -> None:
    global _config, _store, _browser, _ai
    _config = config
    _store = store
    _browser = browser
    _ai = ai


def get_config() -> Config:
    assert _config is not None
    # Re-apply saved settings overrides on every call so search params,
    # limits, and credential changes take effect on the next task run
    # without a container restart.  (AIClient is still initialized at startup
    # with the credentials that were in effect then.)
    from src.api.settings import load_settings
    overrides = load_settings(_config)
    if not overrides:
        return _config
    return _config.model_copy(update=overrides)


def get_store() -> JobStore:
    assert _store is not None
    return _store


def get_browser() -> BrowserManager:
    assert _browser is not None
    return _browser


def get_ai() -> AIClient:
    assert _ai is not None
    return _ai


def get_resume(config: Config = Depends(get_config)) -> ResumeData:
    p = Path(config.resume_path)
    if not p.exists():
        raise HTTPException(404, "No resume uploaded yet — use POST /resume/upload first")
    parsed = parse_docx(p)
    overrides = load_overrides(config.resume_overrides_path)
    return parsed.merged(overrides)
