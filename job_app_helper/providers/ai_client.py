from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from job_app_helper.config import Settings


class AIError(RuntimeError):
    pass


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str


class AIClient:
    def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        raise NotImplementedError


class OpenRouterClient(AIClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        api_key = self.settings.ai.openrouter_api_key
        if not api_key:
            raise AIError("OPENROUTER_API_KEY missing")

        body = {
            "model": self.settings.ai.primary_model,
            "messages": [],
        }
        if system_prompt:
            body["messages"].append({"role": "system", "content": system_prompt})
        body["messages"].append({"role": "user", "content": prompt})

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(body),
            timeout=self.settings.ai.request_timeout_seconds,
        )
        if response.status_code >= 400:
            raise AIError(f"OpenRouter request failed: {response.status_code} {response.text}")
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return AIResponse(text=text, provider="openrouter", model=self.settings.ai.primary_model)


class DeepSeekClient(AIClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        api_key = self.settings.ai.deepseek_api_key
        if not api_key:
            raise AIError("DEEPSEEK_API_KEY missing")

        body: dict[str, Any] = {
            "model": self.settings.ai.fallback_model,
            "messages": [],
        }
        if system_prompt:
            body["messages"].append({"role": "system", "content": system_prompt})
        body["messages"].append({"role": "user", "content": prompt})

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(body),
            timeout=self.settings.ai.request_timeout_seconds,
        )
        if response.status_code >= 400:
            raise AIError(f"DeepSeek request failed: {response.status_code} {response.text}")
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return AIResponse(text=text, provider="deepseek", model=self.settings.ai.fallback_model)


class FallbackAIClient(AIClient):
    def __init__(self, settings: Settings) -> None:
        self.primary = OpenRouterClient(settings)
        self.fallback = DeepSeekClient(settings)

    def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        try:
            return self.primary.generate(prompt=prompt, system_prompt=system_prompt)
        except Exception:
            return self.fallback.generate(prompt=prompt, system_prompt=system_prompt)
