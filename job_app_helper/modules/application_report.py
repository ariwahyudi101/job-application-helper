from __future__ import annotations

from pathlib import Path

from job_app_helper.models import CompanyResearch, GapReport, ParsedJob
from job_app_helper.providers.ai_client import AIClient
from job_app_helper.utils import assess_resume_timeline, current_date_context, read_prompt, sanitize_future_dated_claims


class ApplicationReportModule:
    """Input: parsed job + before/after analyses + artifacts -> Output: concise markdown report path"""

    def __init__(self, ai_client: AIClient, prompts_dir: str, output_dir: str) -> None:
        self.ai_client = ai_client
        self.prompts_dir = prompts_dir
        self.output_dir = Path(output_dir)

    def write(
        self,
        parsed_job: ParsedJob,
        company_research: CompanyResearch,
        original_gap: GapReport,
        final_gap: GapReport,
        rewrite_performed: bool,
        rewrite_decision_reason: str,
        gate_threshold: int,
        target_apply_score: int,
        stretch_score: int,
        rewritten_resume_path: str | None = None,
        cover_letter_path: str | None = None,
        output_path: str | None = None,
    ) -> str:
        rewritten_resume = ""
        if rewritten_resume_path and Path(rewritten_resume_path).exists():
            rewritten_resume = Path(rewritten_resume_path).read_text(encoding="utf-8")

        cover_letter = ""
        if cover_letter_path and Path(cover_letter_path).exists():
            cover_letter = Path(cover_letter_path).read_text(encoding="utf-8")

        final_resume_timeline = assess_resume_timeline(rewritten_resume) if rewritten_resume else assess_resume_timeline("")
        prompt_template = read_prompt(self.prompts_dir, "application_report_prompt.txt")
        prompt = prompt_template.format(
            language=parsed_job.language,
            current_date=current_date_context(),
            final_timeline_summary=final_resume_timeline.summary,
            final_future_dated_entries="\n".join(f"- {item}" for item in final_resume_timeline.future_dated_entries),
            job_title=parsed_job.title,
            company=parsed_job.company,
            rewrite_performed="yes" if rewrite_performed else "no",
            rewrite_decision_reason=rewrite_decision_reason,
            gate_threshold=gate_threshold,
            target_apply_score=target_apply_score,
            stretch_score=stretch_score,
            job_description=parsed_job.description,
            requirements="\n".join(f"- {item}" for item in parsed_job.requirements),
            responsibilities="\n".join(f"- {item}" for item in parsed_job.responsibilities),
            company_summary=company_research.summary,
            culture_notes="\n".join(f"- {item}" for item in company_research.culture_notes),
            products_services="\n".join(f"- {item}" for item in company_research.products_services),
            recent_news="\n".join(f"- {item}" for item in company_research.recent_news),
            hiring_signals="\n".join(f"- {item}" for item in company_research.hiring_signals),
            original_score=original_gap.match_score,
            original_matched="\n".join(f"- {item}" for item in original_gap.matched_skills),
            original_missing="\n".join(f"- {item}" for item in original_gap.missing_skills),
            original_experience_gaps="\n".join(f"- {item}" for item in original_gap.experience_gaps),
            original_keyword_gaps="\n".join(f"- {item}" for item in original_gap.keyword_gaps),
            original_closeable_gaps="\n".join(f"- {item}" for item in original_gap.closeable_gaps),
            original_stretch_gaps="\n".join(f"- {item}" for item in original_gap.stretch_gaps),
            original_hard_stop_gaps="\n".join(f"- {item}" for item in original_gap.hard_stop_gaps),
            original_notes=original_gap.analysis_notes,
            final_score=final_gap.match_score,
            final_matched="\n".join(f"- {item}" for item in final_gap.matched_skills),
            final_missing="\n".join(f"- {item}" for item in final_gap.missing_skills),
            final_experience_gaps="\n".join(f"- {item}" for item in final_gap.experience_gaps),
            final_keyword_gaps="\n".join(f"- {item}" for item in final_gap.keyword_gaps),
            final_closeable_gaps="\n".join(f"- {item}" for item in final_gap.closeable_gaps),
            final_stretch_gaps="\n".join(f"- {item}" for item in final_gap.stretch_gaps),
            final_hard_stop_gaps="\n".join(f"- {item}" for item in final_gap.hard_stop_gaps),
            final_notes=final_gap.analysis_notes,
            rewritten_resume=rewritten_resume,
            cover_letter=cover_letter,
        )
        response = self.ai_client.generate(prompt)

        resolved_output_path = Path(output_path) if output_path else self.output_dir / "application-report.md"
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        sanitized_report = sanitize_future_dated_claims(response.text.strip(), final_resume_timeline)
        resolved_output_path.write_text(sanitized_report, encoding="utf-8")
        return str(resolved_output_path)
