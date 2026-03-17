from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from job_app_helper.utils.timeline import TimelineAssessment, assess_resume_timeline, sanitize_future_dated_claims


def load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_prompt(prompts_dir: str, prompt_file: str) -> str:
    return load_text(str(Path(prompts_dir) / prompt_file))


def extract_json_block(text: str) -> dict:
    # Tolerant parser for LLM responses with fenced JSON.
    payload = text.strip()
    if "```" in payload:
        parts = payload.split("```")
        payload = next((p for p in parts if "{" in p and "}" in p), payload)
    start, end = payload.find("{"), payload.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(payload[start : end + 1])


def current_date_context() -> str:
    return date.today().isoformat()


__all__ = [
    "TimelineAssessment",
    "assess_resume_timeline",
    "current_date_context",
    "extract_json_block",
    "load_text",
    "read_prompt",
    "sanitize_future_dated_claims",
]
