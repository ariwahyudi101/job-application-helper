from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from job_app_helper.models import ParsedJob
from job_app_helper.providers.ai_client import AIClient, AIError


@dataclass
class OutputNames:
    folder: str
    resume_filename: str
    cover_letter_filename: str


class OutputNamer:
    """Generate short, consistent output names per job using AI with safe fallbacks."""

    def __init__(self, ai_client: AIClient, output_dir: str) -> None:
        self.ai_client = ai_client
        self.output_dir = Path(output_dir)

    def build_paths(self, parsed_job: ParsedJob) -> tuple[str, str]:
        names = self._generate_names(parsed_job)
        target_dir = self.output_dir / names.folder
        target_dir.mkdir(parents=True, exist_ok=True)

        resume_path = target_dir / names.resume_filename
        cover_letter_path = target_dir / names.cover_letter_filename
        return str(resume_path), str(cover_letter_path)

    def _generate_names(self, parsed_job: ParsedJob) -> OutputNames:
        fallback_folder = self._sanitize_short(f"{parsed_job.company}-{parsed_job.title}", max_len=26)
        fallback_resume = "resume.md"
        fallback_cover = "cover-letter.txt"

        prompt = (
            "Generate short file naming metadata for a job application output folder.\n"
            "Return strict JSON only (no markdown), with keys: folder, resume_filename, cover_letter_filename.\n"
            "Rules:\n"
            "- folder: 8-26 chars, lowercase, letters/numbers/hyphen only, compact and meaningful.\n"
            "- resume_filename: lowercase kebab-case ending with .md\n"
            "- cover_letter_filename: lowercase kebab-case ending with .txt\n"
            "- Keep names concise and professional.\n\n"
            f"Company: {parsed_job.company}\n"
            f"Role: {parsed_job.title}\n"
            f"Language: {parsed_job.language}\n"
        )

        try:
            response = self.ai_client.generate(prompt)
            payload = json.loads(response.text)
        except (AIError, json.JSONDecodeError, TypeError, ValueError):
            return OutputNames(
                folder=fallback_folder,
                resume_filename=fallback_resume,
                cover_letter_filename=fallback_cover,
            )

        folder = self._sanitize_short(str(payload.get("folder", "")), max_len=26) or fallback_folder
        resume_filename = self._sanitize_filename(
            str(payload.get("resume_filename", "")),
            default=fallback_resume,
            required_extension=".md",
        )
        cover_letter_filename = self._sanitize_filename(
            str(payload.get("cover_letter_filename", "")),
            default=fallback_cover,
            required_extension=".txt",
        )
        return OutputNames(
            folder=folder,
            resume_filename=resume_filename,
            cover_letter_filename=cover_letter_filename,
        )

    @staticmethod
    def _sanitize_short(value: str, max_len: int) -> str:
        cleaned = re.sub(r"[^a-z0-9-]", "-", value.lower())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")
        if not cleaned:
            return ""
        return cleaned[:max_len].strip("-")

    def _sanitize_filename(self, value: str, default: str, required_extension: str) -> str:
        stem = value.lower().strip()
        if stem.endswith(required_extension):
            stem = stem[: -len(required_extension)]
        stem = self._sanitize_short(stem, max_len=40)
        if not stem:
            return default
        return f"{stem}{required_extension}"
