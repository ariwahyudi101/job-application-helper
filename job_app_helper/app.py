from __future__ import annotations

from job_app_helper.config import Settings
from job_app_helper.models import ApplicationRecord
from job_app_helper.modules.company_research import CompanyResearchModule
from job_app_helper.modules.cover_letter import CoverLetterModule
from job_app_helper.modules.gap_analysis import GapAnalysisModule
from job_app_helper.modules.job_parser import JobParserModule
from job_app_helper.modules.output_namer import OutputNamer
from job_app_helper.modules.query_chat import QueryChatModule
from job_app_helper.modules.resume_rewrite import ResumeRewriteModule
from job_app_helper.providers.ai_client import FallbackAIClient
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
        )
        self.cover_letter = CoverLetterModule(
            self.ai_client,
            settings.paths.prompts_dir,
            settings.paths.output_dir,
        )
        self.output_namer = OutputNamer(self.ai_client, settings.paths.output_dir)
        self.query_chat = QueryChatModule(self.ai_client, self.repo, settings.paths.prompts_dir)

    def run_application(self, url: str) -> int:
        parsed_job = self.job_parser.parse(url)
        resume_output_path, cover_letter_output_path = self.output_namer.build_paths(parsed_job)
        research = self.company_research.research(parsed_job)
        gap = self.gap_analysis.analyze(parsed_job, self.settings.paths.default_resume_path)
        resume_path = self.resume_rewrite.rewrite(
            self.settings.paths.default_resume_path,
            parsed_job,
            gap,
            output_path=resume_output_path,
        )
        cover_letter_path = self.cover_letter.write(
            resume_path,
            parsed_job,
            research,
            output_path=cover_letter_output_path,
        )

        record = ApplicationRecord.build(
            url=url,
            parsed_job=parsed_job,
            company_research=research,
            gap_report=gap,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
        )
        return self.repo.save_application(record)

    def ask(self, application_id: int, question: str) -> str:
        return self.query_chat.ask(application_id=application_id, question=question)
