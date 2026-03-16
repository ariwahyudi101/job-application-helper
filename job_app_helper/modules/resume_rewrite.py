from __future__ import annotations

from pathlib import Path

from job_app_helper.models import GapReport, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import read_prompt


class ResumeRewriteModule:
    """Input: resume + ParsedJob + GapReport -> Output: path to rewritten .md"""

    def __init__(self, ai_client: AIClient, prompts_dir: str, output_dir: str) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir
        self.output_dir = Path(output_dir)

    def rewrite(
        self,
        default_resume_path: str,
        parsed_job: ParsedJob,
        gap_report: GapReport,
        output_path: str | None = None,
    ) -> str:
        resume_text = Path(default_resume_path).read_text(encoding="utf-8")
        prompt_template = read_prompt(self.prompts_dir, "resume_rewrite_prompt.txt")
        prompt = prompt_template.format(
            resume_text=resume_text,
            job_title=parsed_job.title,
            company=parsed_job.company,
            requirements="\n".join(f"- {r}" for r in parsed_job.requirements),
            responsibilities="\n".join(f"- {r}" for r in parsed_job.responsibilities),
            matched_skills="\n".join(f"- {s}" for s in gap_report.matched_skills),
            missing_skills="\n".join(f"- {s}" for s in gap_report.missing_skills),
            keyword_gaps="\n".join(f"- {k}" for k in gap_report.keyword_gaps),
            language=parsed_job.language,
        )
        response = self.ai_client.generate(prompt)

        resolved_output_path = Path(output_path) if output_path else self.output_dir / "resume.md"
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_output_path.write_text(response.text.strip() + "\n", encoding="utf-8")
        return str(resolved_output_path)
