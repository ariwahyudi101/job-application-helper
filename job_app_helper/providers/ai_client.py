from __future__ import annotations

import json
import time
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


class BaseHTTPAIClient(AIClient):
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _post_with_retries(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        max_attempts = max(1, int(self.settings.ai.max_retries) + 1)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    data=json.dumps(body),
                    timeout=(
                        self.settings.ai.connect_timeout_seconds,
                        self.settings.ai.request_timeout_seconds,
                    ),
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                time.sleep(self.settings.ai.retry_backoff_seconds * attempt)
                continue

            if response.status_code >= 400:
                text = response.text[:800]
                # Retry only transient statuses.
                if response.status_code in {408, 425, 429, 500, 502, 503, 504} and attempt < max_attempts:
                    time.sleep(self.settings.ai.retry_backoff_seconds * attempt)
                    continue

                if self.provider_name == "openrouter" and response.status_code == 404 and "guardrail" in text.lower():
                    raise AIError(
                        "OpenRouter blocked by data/guardrail policy (404). "
                        "Update privacy settings at https://openrouter.ai/settings/privacy or choose another model/provider."
                    )
                raise AIError(f"{self.provider_name} request failed: {response.status_code} {text}")

            try:
                return response.json()
            except ValueError as exc:
                raise AIError(f"{self.provider_name} returned non-JSON response") from exc

        raise AIError(f"{self.provider_name} request failed after retries: {last_error}")


class OpenRouterClient(BaseHTTPAIClient):
    provider_name = "openrouter"

    def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        api_key = self.settings.ai.openrouter_api_key
        if not api_key:
            raise AIError("OPENROUTER_API_KEY missing")

        body: dict[str, Any] = {
            "model": self.settings.ai.primary_model,
            "messages": [],
        }
        if system_prompt:
            body["messages"].append({"role": "system", "content": system_prompt})
        body["messages"].append({"role": "user", "content": prompt})

        data = self._post_with_retries(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/ariwahyudi101/job-application-helper",
                "X-Title": "Job Application Helper",
            },
            body=body,
        )
        text = data["choices"][0]["message"]["content"]
        return AIResponse(text=text, provider="openrouter", model=self.settings.ai.primary_model)


class DeepSeekClient(BaseHTTPAIClient):
    provider_name = "deepseek"

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

        data = self._post_with_retries(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            body=body,
        )
        text = data["choices"][0]["message"]["content"]
        return AIResponse(text=text, provider="deepseek", model=self.settings.ai.fallback_model)


class FallbackAIClient(AIClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._clients = {
            "openrouter": OpenRouterClient(settings),
            "deepseek": DeepSeekClient(settings),
        }

    def _provider_enabled(self, provider: str) -> bool:
        if provider == "openrouter":
            return bool(self.settings.ai.openrouter_api_key)
        if provider == "deepseek":
            return bool(self.settings.ai.deepseek_api_key)
        return False

    def generate(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        order = [self.settings.ai.primary_provider.lower(), self.settings.ai.fallback_provider.lower()]
        tried_errors: list[str] = []

        for provider in order:
            client = self._clients.get(provider)
            if not client:
                tried_errors.append(f"unsupported provider '{provider}'")
                continue
            if not self._provider_enabled(provider):
                tried_errors.append(f"provider '{provider}' skipped (missing API key)")
                continue
            try:
                return client.generate(prompt=prompt, system_prompt=system_prompt)
            except AIError as exc:
                tried_errors.append(f"{provider}: {exc}")

        raise AIError("All configured AI providers failed. " + " | ".join(tried_errors))
