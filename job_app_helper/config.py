from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AIProviderConfig:
    primary_provider: str = "groq"
    fallback_provider: str = "openrouter"
    primary_model: str = "openai/gpt-oss-120b"
    fallback_model: str = "minimax/minimax-m2.5:free"
    resume_rewrite_provider: str = "groq"
    resume_rewrite_model: str = "openai/gpt-oss-120b"
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    deepseek_api_key: str = ""
    request_timeout_seconds: int = 60
    connect_timeout_seconds: int = 15
    max_retries: int = 1
    retry_backoff_seconds: float = 1.5


@dataclass
class PathConfig:
    default_resume_path: str = "resumes/default_resume.md"
    output_dir: str = "output"
    prompts_dir: str = "job_app_helper/prompts"
    templates_dir: str = "job_app_helper/templates"
    browser_profile_dir: str = "tmp/browser-profile"
    automation_screenshots_dir: str = "output/browser-screenshots"


@dataclass
class StorageConfig:
    backend: str = "sqlite"
    sqlite_db_path: str = "job_applications.db"


@dataclass
class SearchConfig:
    enabled: bool = False
    search_api_base_url: str = ""
    search_api_key: str = ""
    max_results: int = 5


@dataclass
class OptimizationConfig:
    min_baseline_score: int = 50
    target_apply_score: int = 70
    stretch_score: int = 90


@dataclass
class AutomationConfig:
    enabled: bool = False
    mode: str = "semi_auto"
    headless: bool = False
    max_wait_seconds: int = 20
    stop_before_submit: bool = True


@dataclass
class ComputerUseConfig:
    provider: str = "gemini"
    model: str = "gemini-2.0-flash"
    api_key: str = ""
    max_steps: int = 12
    screenshot_on_each_step: bool = False
    timeout_seconds: int = 45


@dataclass
class ApplicantProfileConfig:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    years_of_experience: str = ""
    current_salary: str = ""
    expected_salary: str = ""
    notice_period: str = ""
    work_authorization: str = ""


@dataclass
class Settings:
    ai: AIProviderConfig = field(default_factory=AIProviderConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    computer_use: ComputerUseConfig = field(default_factory=ComputerUseConfig)
    applicant_profile: ApplicantProfileConfig = field(default_factory=ApplicantProfileConfig)


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _coerce_numbers(ai_payload: dict[str, Any]) -> dict[str, Any]:
    int_fields = ["request_timeout_seconds", "connect_timeout_seconds", "max_retries"]
    for field_name in int_fields:
        value = ai_payload.get(field_name)
        if isinstance(value, str) and value.strip():
            ai_payload[field_name] = int(value)

    backoff = ai_payload.get("retry_backoff_seconds")
    if isinstance(backoff, str) and backoff.strip():
        ai_payload["retry_backoff_seconds"] = float(backoff)
    return ai_payload


def _coerce_bool(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return value


def _load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_settings(config_path: str = "config.json") -> Settings:
    _load_dotenv()
    # Environment variables are intentionally flat and optional for easy overrides.
    env_overrides = {
        "ai": {
            "primary_provider": os.getenv("JAH_PRIMARY_PROVIDER"),
            "fallback_provider": os.getenv("JAH_FALLBACK_PROVIDER"),
            "primary_model": os.getenv("JAH_PRIMARY_MODEL"),
            "fallback_model": os.getenv("JAH_FALLBACK_MODEL"),
            "resume_rewrite_provider": os.getenv("JAH_RESUME_REWRITE_PROVIDER"),
            "resume_rewrite_model": os.getenv("JAH_RESUME_REWRITE_MODEL"),
            "groq_api_key": os.getenv("GROQ_API_KEY"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY"),
            "request_timeout_seconds": os.getenv("JAH_REQUEST_TIMEOUT_SECONDS"),
            "connect_timeout_seconds": os.getenv("JAH_CONNECT_TIMEOUT_SECONDS"),
            "max_retries": os.getenv("JAH_MAX_RETRIES"),
            "retry_backoff_seconds": os.getenv("JAH_RETRY_BACKOFF_SECONDS"),
        },
        "paths": {
            "default_resume_path": os.getenv("JAH_DEFAULT_RESUME_PATH"),
            "output_dir": os.getenv("JAH_OUTPUT_DIR"),
            "prompts_dir": os.getenv("JAH_PROMPTS_DIR"),
            "templates_dir": os.getenv("JAH_TEMPLATES_DIR"),
            "browser_profile_dir": os.getenv("JAH_BROWSER_PROFILE_DIR"),
            "automation_screenshots_dir": os.getenv("JAH_AUTOMATION_SCREENSHOTS_DIR"),
        },
        "storage": {
            "backend": os.getenv("JAH_STORAGE_BACKEND"),
            "sqlite_db_path": os.getenv("JAH_SQLITE_DB_PATH"),
        },
        "optimization": {
            "min_baseline_score": os.getenv("JAH_MIN_BASELINE_SCORE"),
            "target_apply_score": os.getenv("JAH_TARGET_APPLY_SCORE"),
            "stretch_score": os.getenv("JAH_STRETCH_SCORE"),
        },
        "automation": {
            "enabled": os.getenv("JAH_AUTOMATION_ENABLED"),
            "mode": os.getenv("JAH_AUTOMATION_MODE"),
            "headless": os.getenv("JAH_AUTOMATION_HEADLESS"),
            "max_wait_seconds": os.getenv("JAH_AUTOMATION_MAX_WAIT_SECONDS"),
            "stop_before_submit": os.getenv("JAH_AUTOMATION_STOP_BEFORE_SUBMIT"),
        },
        "computer_use": {
            "provider": os.getenv("JAH_COMPUTER_USE_PROVIDER"),
            "model": os.getenv("JAH_COMPUTER_USE_MODEL"),
            "api_key": os.getenv("JAH_COMPUTER_USE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            "max_steps": os.getenv("JAH_COMPUTER_USE_MAX_STEPS"),
            "screenshot_on_each_step": os.getenv("JAH_COMPUTER_USE_SCREENSHOT_ON_EACH_STEP"),
            "timeout_seconds": os.getenv("JAH_COMPUTER_USE_TIMEOUT_SECONDS"),
        },
        "applicant_profile": {
            "full_name": os.getenv("JAH_APPLICANT_FULL_NAME"),
            "email": os.getenv("JAH_APPLICANT_EMAIL"),
            "phone": os.getenv("JAH_APPLICANT_PHONE"),
            "location": os.getenv("JAH_APPLICANT_LOCATION"),
            "years_of_experience": os.getenv("JAH_APPLICANT_YEARS_OF_EXPERIENCE"),
            "current_salary": os.getenv("JAH_APPLICANT_CURRENT_SALARY"),
            "expected_salary": os.getenv("JAH_APPLICANT_EXPECTED_SALARY"),
            "notice_period": os.getenv("JAH_APPLICANT_NOTICE_PERIOD"),
            "work_authorization": os.getenv("JAH_APPLICANT_WORK_AUTHORIZATION"),
        },
    }

    default = Settings()
    payload = {
        "ai": default.ai.__dict__.copy(),
        "paths": default.paths.__dict__.copy(),
        "storage": default.storage.__dict__.copy(),
        "search": default.search.__dict__.copy(),
        "optimization": default.optimization.__dict__.copy(),
        "automation": default.automation.__dict__.copy(),
        "computer_use": default.computer_use.__dict__.copy(),
        "applicant_profile": default.applicant_profile.__dict__.copy(),
    }

    path = Path(config_path)
    if path.exists():
        file_payload = json.loads(path.read_text(encoding="utf-8"))
        payload = _deep_update(payload, file_payload)

    sanitized_env = {
        section: {k: v for k, v in values.items() if v is not None}
        for section, values in env_overrides.items()
    }
    payload = _deep_update(payload, sanitized_env)
    payload["ai"] = _coerce_numbers(payload["ai"])
    payload["optimization"] = {
        key: int(value) if isinstance(value, str) and value.strip() else value
        for key, value in payload["optimization"].items()
    }
    payload["automation"] = {
        key: (
            int(value)
            if key == "max_wait_seconds" and isinstance(value, str) and value.strip()
            else _coerce_bool(value)
        )
        for key, value in payload["automation"].items()
    }
    payload["computer_use"] = {
        key: (
            int(value)
            if key in {"max_steps", "timeout_seconds"} and isinstance(value, str) and value.strip()
            else _coerce_bool(value)
        )
        for key, value in payload["computer_use"].items()
    }

    settings = Settings(
        ai=AIProviderConfig(**payload["ai"]),
        paths=PathConfig(**payload["paths"]),
        storage=StorageConfig(**payload["storage"]),
        search=SearchConfig(**payload["search"]),
        optimization=OptimizationConfig(**payload["optimization"]),
        automation=AutomationConfig(**payload["automation"]),
        computer_use=ComputerUseConfig(**payload["computer_use"]),
        applicant_profile=ApplicantProfileConfig(**payload["applicant_profile"]),
    )
    Path(settings.paths.output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.paths.browser_profile_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.paths.automation_screenshots_dir).mkdir(parents=True, exist_ok=True)
    return settings
