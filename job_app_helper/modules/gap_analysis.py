from __future__ import annotations

from pathlib import Path

from job_app_helper.models import GapReport, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import extract_json_block, read_prompt


class GapAnalysisModule:
    """Input: ParsedJob + resume path -> Output: GapReport"""

    def __init__(self, ai_client: AIClient, prompts_dir: str) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir

    def analyze(self, parsed_job: ParsedJob, default_resume_path: str) -> GapReport:
        resume_text = Path(default_resume_path).read_text(encoding="utf-8")
        prompt_template = read_prompt(self.prompts_dir, "gap_analysis_prompt.txt")
        prompt = prompt_template.format(
            job_title=parsed_job.title,
            company=parsed_job.company,
            job_description=parsed_job.description,
            requirements="\n".join(f"- {r}" for r in parsed_job.requirements),
            responsibilities="\n".join(f"- {r}" for r in parsed_job.responsibilities),
            resume_text=resume_text,
        )
        response = self.ai_client.generate(prompt)
        structured = extract_json_block(response.text)

        return GapReport(
            matched_skills=structured.get("matched_skills", []),
            missing_skills=structured.get("missing_skills", []),
            experience_gaps=structured.get("experience_gaps", []),
            keyword_gaps=structured.get("keyword_gaps", []),
            match_score=int(structured.get("match_score", 0)),
            analysis_notes=structured.get("analysis_notes", ""),
        )
