from __future__ import annotations

from pathlib import Path

from job_app_helper.models import GapReport, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import current_date_context, read_prompt
from job_app_helper.utils.docx_utils import markdown_to_docx


class ResumeRewriteModule:
    """Input: resume + ParsedJob + GapReport -> Output: path to rewritten .md"""

    def __init__(
        self,
        ai_client: AIClient,
        prompts_dir: str,
        output_dir: str,
        rewrite_provider: str,
        rewrite_model: str,
    ) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir
        self.output_dir = Path(output_dir)
        self.rewrite_provider = rewrite_provider
        self.rewrite_model = rewrite_model

    def rewrite(
        self,
        default_resume_path: str,
        parsed_job: ParsedJob,
        gap_report: GapReport,
        target_apply_score: int,
        stretch_score: int,
        output_path: str | None = None,
    ) -> str:
        resume_text = Path(default_resume_path).read_text(encoding="utf-8")
        prompt_template = read_prompt(self.prompts_dir, "resume_rewrite_prompt.txt")
        prompt = prompt_template.format(
            current_date=current_date_context(),
            resume_text=resume_text,
            job_title=parsed_job.title,
            company=parsed_job.company,
            requirements="\n".join(f"- {r}" for r in parsed_job.requirements),
            responsibilities="\n".join(f"- {r}" for r in parsed_job.responsibilities),
            matched_skills="\n".join(f"- {s}" for s in gap_report.matched_skills),
            missing_skills="\n".join(f"- {s}" for s in gap_report.missing_skills),
            keyword_gaps="\n".join(f"- {k}" for k in gap_report.keyword_gaps),
            closeable_gaps="\n".join(f"- {g}" for g in gap_report.closeable_gaps),
            stretch_gaps="\n".join(f"- {g}" for g in gap_report.stretch_gaps),
            hard_stop_gaps="\n".join(f"- {g}" for g in gap_report.hard_stop_gaps),
            baseline_score=gap_report.match_score,
            target_apply_score=target_apply_score,
            stretch_score=stretch_score,
            language=parsed_job.language,
        )
        response = self.ai_client.generate(
            prompt,
            provider_override=self.rewrite_provider,
            model_override=self.rewrite_model,
        )

        resolved_output_path = Path(output_path) if output_path else self.output_dir / "resume.md"
        self._write_resume_artifacts(response.text.strip(), resolved_output_path)
        return str(resolved_output_path)

    def materialize_baseline(self, source_resume_path: str, output_path: str | None = None) -> str:
        resume_text = Path(source_resume_path).read_text(encoding="utf-8").strip()
        resolved_output_path = Path(output_path) if output_path else self.output_dir / "resume.md"
        self._write_resume_artifacts(resume_text, resolved_output_path)
        return str(resolved_output_path)

    @staticmethod
    def _write_resume_artifacts(markdown_text: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_text.strip() + "\n", encoding="utf-8")
        markdown_to_docx(markdown_text.strip(), str(output_path.with_suffix(".docx")))
