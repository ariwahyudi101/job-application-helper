from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from job_app_helper.config import Settings


class ComputerUseError(RuntimeError):
    pass


@dataclass
class ComputerUseResponse:
    action: str
    reason: str
    metadata: dict[str, Any]
    provider: str
    model: str


class ComputerUseClient:
    def analyze(self, instruction: str, context: dict[str, Any]) -> ComputerUseResponse:
        raise NotImplementedError


class GeminiComputerUseClient(ComputerUseClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze(self, instruction: str, context: dict[str, Any]) -> ComputerUseResponse:
        import requests

        api_key = self.settings.computer_use.api_key
        if not api_key:
            raise ComputerUseError("GEMINI API key missing. Set JAH_COMPUTER_USE_API_KEY or GEMINI_API_KEY.")

        model = self.settings.computer_use.model
        prompt = (
            "You are helping a browser automation workflow decide the safest next step.\n"
            "Return strict JSON with keys: action, reason, metadata.\n"
            "Allowed actions: continue, review_ready, login_needed, captcha, ask_user, failed.\n"
            "Prefer conservative actions.\n\n"
            f"Instruction: {instruction}\n"
            f"Context JSON: {json.dumps(context, ensure_ascii=False)}"
        )

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 400},
            },
            timeout=self.settings.computer_use.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ComputerUseError(f"Gemini request failed: {response.status_code} {response.text[:400]}")

        try:
            payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            parsed = _extract_json_block(text)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ComputerUseError("Gemini returned an unreadable computer-use response") from exc

        return ComputerUseResponse(
            action=str(parsed.get("action", "failed")).strip(),
            reason=str(parsed.get("reason", "")).strip(),
            metadata=parsed.get("metadata", {}) if isinstance(parsed.get("metadata"), dict) else {},
            provider="gemini",
            model=model,
        )


def _extract_json_block(text: str) -> dict[str, Any]:
    payload = text.strip()
    if "```" in payload:
        parts = payload.split("```")
        payload = next((part for part in parts if "{" in part and "}" in part), payload)
    start = payload.find("{")
    end = payload.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    return json.loads(payload[start : end + 1])
