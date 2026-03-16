from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AIProviderConfig:
    primary_provider: str = "openrouter"
    fallback_provider: str = "deepseek"
    primary_model: str = "deepseek/deepseek-chat-v3-0324"
    fallback_model: str = "deepseek-chat"
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
class Settings:
    ai: AIProviderConfig = field(default_factory=AIProviderConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    search: SearchConfig = field(default_factory=SearchConfig)


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


def load_settings(config_path: str = "config.json") -> Settings:
    # Environment variables are intentionally flat and optional for easy overrides.
    env_overrides = {
        "ai": {
            "primary_provider": os.getenv("JAH_PRIMARY_PROVIDER"),
            "fallback_provider": os.getenv("JAH_FALLBACK_PROVIDER"),
            "primary_model": os.getenv("JAH_PRIMARY_MODEL"),
            "fallback_model": os.getenv("JAH_FALLBACK_MODEL"),
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
        },
        "storage": {
            "backend": os.getenv("JAH_STORAGE_BACKEND"),
            "sqlite_db_path": os.getenv("JAH_SQLITE_DB_PATH"),
        },
    }

    default = Settings()
    payload = {
        "ai": default.ai.__dict__.copy(),
        "paths": default.paths.__dict__.copy(),
        "storage": default.storage.__dict__.copy(),
        "search": default.search.__dict__.copy(),
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

    settings = Settings(
        ai=AIProviderConfig(**payload["ai"]),
        paths=PathConfig(**payload["paths"]),
        storage=StorageConfig(**payload["storage"]),
        search=SearchConfig(**payload["search"]),
    )
    Path(settings.paths.output_dir).mkdir(parents=True, exist_ok=True)
    return settings
