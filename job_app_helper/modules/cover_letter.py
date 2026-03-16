from __future__ import annotations

from pathlib import Path

from job_app_helper.models import CompanyResearch, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import read_prompt


class CoverLetterModule:
    """Input: rewritten resume + ParsedJob + CompanyResearch -> Output: path to .txt"""

    def __init__(self, ai_client: AIClient, prompts_dir: str, output_dir: str) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir
        self.output_dir = Path(output_dir)

    def write(
        self,
        rewritten_resume_path: str,
        parsed_job: ParsedJob,
        company_research: CompanyResearch,
        output_path: str | None = None,
    ) -> str:
        rewritten_resume = Path(rewritten_resume_path).read_text(encoding="utf-8")
        prompt_template = read_prompt(self.prompts_dir, "cover_letter_prompt.txt")
        prompt = prompt_template.format(
            rewritten_resume=rewritten_resume,
            job_title=parsed_job.title,
            company=parsed_job.company,
            job_description=parsed_job.description,
            company_summary=company_research.summary,
            culture_notes="\n".join(f"- {c}" for c in company_research.culture_notes),
            products_services="\n".join(f"- {p}" for p in company_research.products_services),
            recent_news="\n".join(f"- {n}" for n in company_research.recent_news),
            language=parsed_job.language,
        )
        response = self.ai_client.generate(prompt)

        resolved_output_path = Path(output_path) if output_path else self.output_dir / "cover-letter.txt"
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_output_path.write_text(response.text.strip() + "\n", encoding="utf-8")
        return str(resolved_output_path)
