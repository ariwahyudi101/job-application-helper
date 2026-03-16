from __future__ import annotations

from bs4 import BeautifulSoup
import requests

from job_app_helper.models import ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import extract_json_block, read_prompt


class JobParserModule:
    """Input: URL -> Output: ParsedJob"""

    def __init__(self, ai_client: AIClient, prompts_dir: str) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir

    def parse(self, url: str) -> ParsedJob:
        html = requests.get(url, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")

        title = (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "Unknown Title")
        page_text = soup.get_text("\n", strip=True)

        prompt_template = read_prompt(self.prompts_dir, "job_parser_prompt.txt")
        prompt = prompt_template.format(url=url, title=title, raw_text=page_text[:20000])
        response = self.ai_client.generate(prompt)
        structured = extract_json_block(response.text)

        return ParsedJob(
            url=url,
            title=structured.get("job_title", title),
            company=structured.get("company_name", "Unknown Company"),
            description=structured.get("full_job_description", ""),
            requirements=structured.get("requirements", []),
            responsibilities=structured.get("responsibilities", []),
            cleaned_by_ai=True,
        )
