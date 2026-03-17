from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Callable

from job_app_helper.config import Settings
from job_app_helper.models import ApplicationRecord, ApplicationRunResult
from job_app_helper.modules.application_report import ApplicationReportModule
from job_app_helper.modules.company_research import CompanyResearchModule
from job_app_helper.modules.cover_letter import CoverLetterModule
from job_app_helper.modules.gap_analysis import GapAnalysisModule
from job_app_helper.modules.job_parser import JobParserModule
from job_app_helper.modules.jobstreet_apply import JobStreetApplyModule, default_jobstreet_session_factory
from job_app_helper.modules.output_namer import OutputNamer
from job_app_helper.modules.query_chat import QueryChatModule
from job_app_helper.modules.resume_rewrite import ResumeRewriteModule
from job_app_helper.providers.ai_client import FallbackAIClient
from job_app_helper.providers.computer_use import GeminiComputerUseClient
from job_app_helper.storage.repository import SQLiteApplicationRepository


class JobApplicationPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ai_client = FallbackAIClient(settings)
        self.repo = SQLiteApplicationRepository(settings.storage.sqlite_db_path)
        self.repo.init_schema()

        self.job_parser = JobParserModule(self.ai_client, settings.paths.prompts_dir)
        self.company_research = CompanyResearchModule(
            self.ai_client,
            settings.paths.prompts_dir,
            search_enabled=settings.search.enabled,
        )
        self.gap_analysis = GapAnalysisModule(self.ai_client, settings.paths.prompts_dir)
        self.resume_rewrite = ResumeRewriteModule(
            self.ai_client,
            settings.paths.prompts_dir,
            settings.paths.output_dir,
            settings.ai.resume_rewrite_provider,
            settings.ai.resume_rewrite_model,
        )
        self.cover_letter = CoverLetterModule(
            self.ai_client,
            settings.paths.prompts_dir,
            settings.paths.output_dir,
        )
        self.application_report = ApplicationReportModule(
            self.ai_client,
            settings.paths.prompts_dir,
            settings.paths.output_dir,
        )
        self.output_namer = OutputNamer(self.ai_client, settings.paths.output_dir)
        self.query_chat = QueryChatModule(self.ai_client, self.repo, settings.paths.prompts_dir)
        self.jobstreet_apply = JobStreetApplyModule(
            settings,
            self.repo,
            GeminiComputerUseClient(settings) if settings.computer_use.provider == "gemini" else None,
            default_jobstreet_session_factory,
        )

    def run_application(
        self,
        url: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> ApplicationRunResult:
        step_timings: dict[str, float] = {}
        timings_lock = Lock()
        total_start = perf_counter()

        def emit(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        def timed_step(step_name: str, label: str, func):
            emit(f"{label}...")
            started = perf_counter()
            result = func()
            duration = perf_counter() - started
            with timings_lock:
                step_timings[step_name] = duration
            emit(f"{label} selesai dalam {duration:.1f} detik.")
            return result

        parsed_job = timed_step("parse_job", "Parse lowongan", lambda: self.job_parser.parse(url))
        application_id = self.repo.get_next_application_id()

        with ThreadPoolExecutor(max_workers=3) as executor:
            naming_future = executor.submit(
                timed_step,
                "build_paths",
                "Siapkan nama folder/output",
                lambda: self.output_namer.build_paths(parsed_job, application_id=application_id),
            )
            research_future = executor.submit(
                timed_step,
                "company_research",
                "Riset perusahaan",
                lambda: self.company_research.research(parsed_job),
            )
            gap_future = executor.submit(
                timed_step,
                "initial_gap_analysis",
                "Analisis kecocokan awal",
                lambda: self.gap_analysis.analyze(parsed_job, self.settings.paths.default_resume_path),
            )

            resume_output_path, cover_letter_output_path, report_output_path = naming_future.result()
            research = research_future.result()
            gap = gap_future.result()

        min_baseline_score = self.settings.optimization.min_baseline_score
        target_apply_score = self.settings.optimization.target_apply_score
        stretch_score = self.settings.optimization.stretch_score

        rewrite_performed, rewrite_decision_reason = self._should_rewrite(
            gap,
            min_baseline_score=min_baseline_score,
        )
        resume_path = timed_step(
            "baseline_resume_copy",
            "Salin baseline resume",
            lambda: self.resume_rewrite.materialize_baseline(
                self.settings.paths.default_resume_path,
                output_path=resume_output_path,
            ),
        )
        cover_letter_path = timed_step(
            "skip_cover_letter_note",
            "Siapkan placeholder cover letter",
            lambda: self.cover_letter.write_skip_note(
                parsed_job,
                match_score=gap.match_score,
                gate_threshold=min_baseline_score,
                output_path=cover_letter_output_path,
            ),
        )
        final_gap = gap

        if rewrite_performed:
            resume_path = timed_step(
                "resume_rewrite",
                "Rewrite resume",
                lambda: self.resume_rewrite.rewrite(
                    self.settings.paths.default_resume_path,
                    parsed_job,
                    gap,
                    target_apply_score=target_apply_score,
                    stretch_score=stretch_score,
                    output_path=resume_output_path,
                ),
            )

            rewritten_resume_text = Path(resume_path).read_text(encoding="utf-8")
            with ThreadPoolExecutor(max_workers=2) as executor:
                cover_future = executor.submit(
                    timed_step,
                    "cover_letter",
                    "Generate cover letter",
                    lambda: self.cover_letter.write(
                        resume_path,
                        parsed_job,
                        research,
                        output_path=cover_letter_output_path,
                    ),
                )
                final_gap_future = executor.submit(
                    timed_step,
                    "final_gap_analysis",
                    "Analisis ulang resume hasil rewrite",
                    lambda: self.gap_analysis.analyze_text(parsed_job, rewritten_resume_text),
                )
                cover_letter_path = cover_future.result()
                final_gap = final_gap_future.result()

        report_path = timed_step(
            "application_report",
            "Generate application report",
            lambda: self.application_report.write(
                parsed_job,
                research,
                gap,
                final_gap,
                rewrite_performed=rewrite_performed,
                rewrite_decision_reason=rewrite_decision_reason,
                gate_threshold=min_baseline_score,
                target_apply_score=target_apply_score,
                stretch_score=stretch_score,
                rewritten_resume_path=resume_path,
                cover_letter_path=cover_letter_path if rewrite_performed else None,
                output_path=report_output_path,
            ),
        )

        record = ApplicationRecord.build(
            url=url,
            parsed_job=parsed_job,
            company_research=research,
            gap_report=gap,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            report_path=report_path,
        )
        saved_application_id = timed_step(
            "save_application",
            "Simpan ke database",
            lambda: self.repo.save_application(record),
        )
        total_duration_seconds = perf_counter() - total_start
        return ApplicationRunResult(
            application_id=saved_application_id,
            match_score=gap.match_score,
            rewrite_performed=rewrite_performed,
            rewrite_decision_reason=rewrite_decision_reason,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            report_path=report_path,
            step_timings=step_timings,
            total_duration_seconds=total_duration_seconds,
        )

    def ask(self, application_id: int, question: str) -> str:
        return self.query_chat.ask(application_id=application_id, question=question)

    def regenerate_application(
        self,
        application_id: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> ApplicationRunResult:
        application = self.repo.get_application(application_id)
        if not application:
            raise ValueError(f"Application id={application_id} tidak ditemukan.")
        return self.run_application(application["url"], progress_callback=progress_callback)

    def apply_to_jobstreet(
        self,
        application_id: int,
        progress_callback: Callable[[str], None] | None = None,
    ):
        return self.jobstreet_apply.apply(
            application_id,
            progress_callback=progress_callback,
            answer_provider=self._prompt_screening_answer,
        )

    @staticmethod
    def _prompt_screening_answer(question_text: str) -> str:
        print(f"\nPertanyaan screening JobStreet:\n{question_text}")
        return input("Jawaban: ").strip()

    @staticmethod
    def _should_rewrite(gap, min_baseline_score: int) -> tuple[bool, str]:
        if gap.match_score >= min_baseline_score:
            return True, "baseline_gate"

        transferable_signal_count = len(gap.closeable_gaps) + len(gap.stretch_gaps)
        if gap.match_score >= 25 and len(gap.matched_skills) >= 8 and transferable_signal_count >= 6:
            return True, "transferable_override"

        return False, "gated_out"
