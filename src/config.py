from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml
from dotenv import load_dotenv
import os

credentials_path = Path(__file__).parent.parent / "credentials.env"
load_dotenv(credentials_path)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass
class SearchConfig:
    keywords: list[str] = field(
        default_factory=lambda: ["SOC", "cybersecurity", "software engineer"]
    )
    locations: list[str] = field(default_factory=lambda: ["Remote"])
    days_back: int = 7
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None


@dataclass
class CredentialsConfig:
    linkedin_email: str = field(default_factory=lambda: _env("LINKEDIN_EMAIL"))
    linkedin_password: str = field(default_factory=lambda: _env("LINKEDIN_PASSWORD"))
    indeed_email: str = field(default_factory=lambda: _env("INDEED_EMAIL"))
    indeed_password: str = field(default_factory=lambda: _env("INDEED_PASSWORD"))
    monster_email: str = field(default_factory=lambda: _env("MONSTER_EMAIL"))
    monster_password: str = field(default_factory=lambda: _env("MONSTER_PASSWORD"))
    dice_email: str = field(default_factory=lambda: _env("DICE_EMAIL"))
    dice_password: str = field(default_factory=lambda: _env("DICE_PASSWORD"))


@dataclass
class BrowserConfig:
    headless: bool = False
    slow_mo: int = 100
    timeout: int = 30000
    user_data_dir: Optional[str] = None


@dataclass
class LimitsConfig:
    applications_per_day: int = 50
    delay_between_apps: int = 30
    min_delay: int = 15
    max_delay: int = 60
    scraper_delay_min: int = 10
    scraper_delay_max: int = 20


@dataclass
class AIConfig:
    enabled: bool = True
    endpoint: str = "http://127.0.0.1:1234/v1"
    model: str = "openai/gpt-oss-20b"
    pause_for_approval: bool = True
    startup_timeout: int = 30


@dataclass
class ResumeConfig:
    docx_path: str = ""
    pdf_output: str = "resume.pdf"
    generate_pdf: bool = True


@dataclass
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    credentials: CredentialsConfig = field(default_factory=CredentialsConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    resume: ResumeConfig = field(default_factory=ResumeConfig)


def load_config(config_path: str = "config.yaml") -> Config:
    config_file = Path(config_path)

    config = Config()

    if config_file.exists():
        with open(config_file) as f:
            data = yaml.safe_load(f) or {}

        if "search" in data:
            for key, value in data["search"].items():
                if hasattr(config.search, key):
                    setattr(config.search, key, value)

        if "credentials" in data:
            pass

        if "browser" in data:
            for key, value in data["browser"].items():
                if hasattr(config.browser, key):
                    setattr(config.browser, key, value)

        if "limits" in data:
            for key, value in data["limits"].items():
                if hasattr(config.limits, key):
                    setattr(config.limits, key, value)

        if "ai" in data:
            for key, value in data["ai"].items():
                if hasattr(config.ai, key):
                    setattr(config.ai, key, value)

        if "resume" in data:
            for key, value in data["resume"].items():
                if hasattr(config.resume, key):
                    setattr(config.resume, key, value)

    return config


def save_config(config: Config, config_path: str = "config.yaml"):
    data = {
        "search": {
            "keywords": config.search.keywords,
            "locations": config.search.locations,
            "days_back": config.search.days_back,
            "experience_level": config.search.experience_level,
            "salary_min": config.search.salary_min,
        },
        "credentials": {
            "linkedin_email": config.credentials.linkedin_email,
            "linkedin_password": config.credentials.linkedin_password,
            "indeed_email": config.credentials.indeed_email,
            "monster_email": config.credentials.monster_email,
            "dice_email": config.credentials.dice_email,
        },
        "browser": {
            "headless": config.browser.headless,
            "slow_mo": config.browser.slow_mo,
            "timeout": config.browser.timeout,
            "user_data_dir": config.browser.user_data_dir,
        },
        "limits": {
            "applications_per_day": config.limits.applications_per_day,
            "delay_between_apps": config.limits.delay_between_apps,
            "min_delay": config.limits.min_delay,
            "max_delay": config.limits.max_delay,
        },
        "ai": {
            "enabled": config.ai.enabled,
            "endpoint": config.ai.endpoint,
            "model": config.ai.model,
            "pause_for_approval": config.ai.pause_for_approval,
            "startup_timeout": config.ai.startup_timeout,
        },
        "resume": {
            "docx_path": config.resume.docx_path,
            "pdf_output": config.resume.pdf_output,
            "generate_pdf": config.resume.generate_pdf,
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
