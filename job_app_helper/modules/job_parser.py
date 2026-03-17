from __future__ import annotations

import re

from bs4 import BeautifulSoup
import requests

from job_app_helper.models import ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import extract_json_block, read_prompt

ENGLISH_MARKERS = {
    "the",
    "and",
    "with",
    "for",
    "you",
    "your",
    "role",
    "position",
    "responsible",
    "responsibilities",
    "requirements",
    "experience",
    "skills",
    "ability",
    "strong",
    "looking",
    "join",
    "team",
    "monitoring",
    "reporting",
}

INDONESIAN_MARKERS = {
    "yang",
    "dan",
    "untuk",
    "dengan",
    "pada",
    "akan",
    "kami",
    "posisi",
    "tanggung",
    "jawab",
    "persyaratan",
    "pengalaman",
    "kemampuan",
    "minimal",
    "lulusan",
    "penempatan",
    "sebagai",
    "berpengalaman",
}


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
        language = self._resolve_language(structured=structured, title=title, page_text=page_text)

        return ParsedJob(
            url=url,
            title=structured.get("job_title", title),
            company=structured.get("company_name", "Unknown Company"),
            description=structured.get("full_job_description", ""),
            requirements=structured.get("requirements", []),
            responsibilities=structured.get("responsibilities", []),
            language=language,
            cleaned_by_ai=True,
        )

    def _resolve_language(self, structured: dict, title: str, page_text: str) -> str:
        ai_language = str(structured.get("language") or "").strip().lower()
        heuristic_language = self._detect_language(
            " ".join(
                [
                    title,
                    str(structured.get("job_title", "")),
                    str(structured.get("full_job_description", "")),
                    " ".join(str(item) for item in structured.get("requirements", []) if item),
                    " ".join(str(item) for item in structured.get("responsibilities", []) if item),
                    page_text[:4000],
                ]
            )
        )

        if heuristic_language:
            return heuristic_language
        if ai_language in {"id", "en"}:
            return ai_language
        return "id" if "bahasa indonesia" in page_text.lower() else "en"

    def _detect_language(self, text: str) -> str | None:
        normalized = re.sub(r"[^a-z\s]", " ", text.lower())
        words = [word for word in normalized.split() if len(word) > 1]
        if not words:
            return None

        english_hits = sum(1 for word in words if word in ENGLISH_MARKERS)
        indonesian_hits = sum(1 for word in words if word in INDONESIAN_MARKERS)

        english_phrases = (
            "we are looking for",
            "job description",
            "key responsibilities",
            "requirements",
            "qualifications",
        )
        indonesian_phrases = (
            "kami mencari",
            "deskripsi pekerjaan",
            "tanggung jawab",
            "kualifikasi",
            "persyaratan",
        )

        phrase_bonus_en = sum(3 for phrase in english_phrases if phrase in text.lower())
        phrase_bonus_id = sum(3 for phrase in indonesian_phrases if phrase in text.lower())

        english_score = english_hits + phrase_bonus_en
        indonesian_score = indonesian_hits + phrase_bonus_id

        if english_score >= max(4, indonesian_score + 2):
            return "en"
        if indonesian_score >= max(4, english_score + 2):
            return "id"
        return None
