from __future__ import annotations

import requests

from job_app_helper.models import CompanyResearch, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import extract_json_block, read_prompt


class CompanyResearchModule:
    """Input: ParsedJob -> Output: CompanyResearch"""

    def __init__(self, ai_client: AIClient, prompts_dir: str, search_enabled: bool = False) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir
        self.search_enabled = search_enabled

    def _fetch_public_signals(self, company: str) -> str:
        # Lightweight fallback without paid search APIs.
        if not self.search_enabled:
            return "Search disabled in config."
        query = f"https://duckduckgo.com/html/?q={company}+company+news+culture+products"
        try:
            return requests.get(query, timeout=15).text[:12000]
        except Exception:
            return "Search fetch failed."

    def research(self, parsed_job: ParsedJob) -> CompanyResearch:
        web_notes = self._fetch_public_signals(parsed_job.company)
        prompt_template = read_prompt(self.prompts_dir, "company_research_prompt.txt")
        prompt = prompt_template.format(
            company=parsed_job.company,
            job_title=parsed_job.title,
            job_description=parsed_job.description,
            web_notes=web_notes,
        )
        response = self.ai_client.generate(prompt)
        structured = extract_json_block(response.text)

        return CompanyResearch(
            company=parsed_job.company,
            summary=structured.get("summary", ""),
            culture_notes=structured.get("culture_notes", []),
            products_services=structured.get("products_services", []),
            recent_news=structured.get("recent_news", []),
            hiring_signals=structured.get("hiring_signals", []),
            sources=structured.get("sources", []),
        )
