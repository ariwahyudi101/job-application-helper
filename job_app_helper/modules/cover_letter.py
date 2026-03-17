from __future__ import annotations

from pathlib import Path

from job_app_helper.models import CompanyResearch, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import current_date_context, read_prompt


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
            current_date=current_date_context(),
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

    def write_skip_note(
        self,
        parsed_job: ParsedJob,
        match_score: int,
        gate_threshold: int,
        output_path: str | None = None,
    ) -> str:
        resolved_output_path = Path(output_path) if output_path else self.output_dir / "cover-letter.txt"
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

        language = (parsed_job.language or "en").lower()
        if language == "id":
            body = (
                f"Surat lamaran tidak dibuat otomatis untuk lowongan ini.\n\n"
                f"Alasan: skor kecocokan awal {match_score}/100 berada di bawah ambang minimal "
                f"{gate_threshold}/100.\n\n"
                "Sistem tetap menyimpan resume dasar dan application report agar lowongan ini bisa ditinjau ulang."
            )
        else:
            body = (
                "A tailored cover letter was not generated for this role.\n\n"
                f"Reason: the baseline match score ({match_score}/100) is below the gate "
                f"threshold ({gate_threshold}/100).\n\n"
                "The system still saved the baseline resume and application report for review."
            )

        resolved_output_path.write_text(body + "\n", encoding="utf-8")
        return str(resolved_output_path)
