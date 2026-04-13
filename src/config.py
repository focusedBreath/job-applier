from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=False,  # allow runtime overrides from settings.json
    )

    # Credentials
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_manual_login: bool = False  # if True, skip auto login, let user login via noVNC
    indeed_email: str = ""
    indeed_password: str = ""
    dice_email: str = ""
    dice_password: str = ""
    monster_email: str = ""
    monster_password: str = ""

    # Claude
    claude_api_key: str = ""
    claude_decision_model: str = "claude-sonnet-4-6"
    claude_fill_model: str = "claude-haiku-4-5-20251001"

    # Search
    search_keywords: list[str] = ["SOC analyst", "security operations", "software engineer"]
    search_locations: list[str] = ["Remote", "New Jersey"]
    search_days_back: int = 7

    # Limits
    max_applications_per_day: int = 50
    delay_min_seconds: int = 10
    delay_max_seconds: int = 30

    # Paths
    db_path: str = "/app/data/jobs.db"
    sessions_dir: str = "/app/data/sessions"
    resume_path: str = "/app/data/resume.docx"
    resume_overrides_path: str = "/app/data/resume_overrides.json"
    reports_dir: str = "/app/reports"
