"""
Settings API — reads and writes runtime-editable config values to data/settings.json.
Sensitive fields (passwords, API keys) are accepted on write but masked on read.
"""

import json
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import get_config
from src.config import Config

log = structlog.get_logger()
router = APIRouter(prefix="/settings", tags=["settings"])

_SENSITIVE = {"linkedin_password", "indeed_password", "dice_password", "monster_password", "claude_api_key"}
_MASK = "••••••••"


def _settings_path(config: Config) -> Path:
    return Path(config.db_path).parent / "settings.json"


def load_settings(config: Config) -> dict:
    p = _settings_path(config)
    if not p.exists():
        return {}
    with p.open() as f:
        return json.load(f)


def save_settings(config: Config, data: dict) -> None:
    p = _settings_path(config)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(data, f, indent=2)


class SettingsResponse(BaseModel):
    # Credentials
    linkedin_email: str
    linkedin_password: str
    indeed_email: str
    indeed_password: str
    dice_email: str
    dice_password: str
    monster_email: str
    monster_password: str
    # Claude
    claude_api_key: str
    claude_decision_model: str
    claude_fill_model: str
    # Search
    search_keywords: list[str]
    search_locations: list[str]
    search_days_back: int
    # Limits
    max_applications_per_day: int
    delay_min_seconds: int
    delay_max_seconds: int


class SettingsPatch(BaseModel):
    # All fields optional — only provided fields are updated
    linkedin_email: str | None = None
    linkedin_password: str | None = None
    indeed_email: str | None = None
    indeed_password: str | None = None
    dice_email: str | None = None
    dice_password: str | None = None
    monster_email: str | None = None
    monster_password: str | None = None
    claude_api_key: str | None = None
    claude_decision_model: str | None = None
    claude_fill_model: str | None = None
    search_keywords: list[str] | None = None
    search_locations: list[str] | None = None
    search_days_back: int | None = None
    max_applications_per_day: int | None = None
    delay_min_seconds: int | None = None
    delay_max_seconds: int | None = None


def _effective(config: Config, overrides: dict) -> dict:
    """Merge base config with saved overrides."""
    base = {
        "linkedin_email": config.linkedin_email,
        "linkedin_password": config.linkedin_password,
        "indeed_email": config.indeed_email,
        "indeed_password": config.indeed_password,
        "dice_email": config.dice_email,
        "dice_password": config.dice_password,
        "monster_email": config.monster_email,
        "monster_password": config.monster_password,
        "claude_api_key": config.claude_api_key,
        "claude_decision_model": config.claude_decision_model,
        "claude_fill_model": config.claude_fill_model,
        "search_keywords": config.search_keywords,
        "search_locations": config.search_locations,
        "search_days_back": config.search_days_back,
        "max_applications_per_day": config.max_applications_per_day,
        "delay_min_seconds": config.delay_min_seconds,
        "delay_max_seconds": config.delay_max_seconds,
    }
    base.update(overrides)
    return base


@router.get("", response_model=SettingsResponse)
async def get_settings(config: Config = Depends(get_config)) -> SettingsResponse:
    overrides = load_settings(config)
    effective = _effective(config, overrides)
    # Mask sensitive fields — show filled indicator, not plaintext
    for key in _SENSITIVE:
        if effective.get(key):
            effective[key] = _MASK
    return SettingsResponse(**effective)


@router.patch("", response_model=dict)
async def patch_settings(
    body: SettingsPatch,
    config: Config = Depends(get_config),
) -> dict:
    overrides = load_settings(config)
    updates = body.model_dump(exclude_none=True)

    for key, value in updates.items():
        # Don't overwrite a real value with the mask (user just viewed + re-saved)
        if key in _SENSITIVE and value == _MASK:
            continue
        overrides[key] = value

    save_settings(config, overrides)
    log.info("settings.saved", fields=list(updates.keys()))
    return {"ok": True, "saved": list(updates.keys())}
