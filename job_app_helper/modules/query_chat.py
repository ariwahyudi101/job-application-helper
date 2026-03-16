from __future__ import annotations

import json
from pathlib import Path

from job_app_helper.providers.ai_client import AIClient
from job_app_helper.storage.repository import ApplicationRepository
from job_app_helper.utils import read_prompt


class QueryChatModule:
    """Input: application_id + natural language question -> Output: answer text"""

    def __init__(self, ai_client: AIClient, repo: ApplicationRepository, prompts_dir: str) -> None:
        self.ai_client = ai_client
        self.repo = repo
        self.prompts_dir = prompts_dir

    def ask(self, application_id: int, question: str) -> str:
        app = self.repo.get_application(application_id)
        if not app:
            return f"No application found for id={application_id}"

        resume_text = Path(app["resume_path"]).read_text(encoding="utf-8") if Path(app["resume_path"]).exists() else ""
        cover_letter_text = (
            Path(app["cover_letter_path"]).read_text(encoding="utf-8")
            if Path(app["cover_letter_path"]).exists()
            else ""
        )

        prompt_template = read_prompt(self.prompts_dir, "query_chat_prompt.txt")
        prompt = prompt_template.format(
            application_json=json.dumps(app, indent=2),
            resume_text=resume_text,
            cover_letter_text=cover_letter_text,
            question=question,
        )
        response = self.ai_client.generate(prompt)
        return response.text.strip()
