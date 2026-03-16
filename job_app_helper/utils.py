from __future__ import annotations

import json
from pathlib import Path


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
