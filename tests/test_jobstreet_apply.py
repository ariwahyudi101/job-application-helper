from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from job_app_helper.config import (
    AIProviderConfig,
    ApplicantProfileConfig,
    AutomationConfig,
    ComputerUseConfig,
    OptimizationConfig,
    PathConfig,
    SearchConfig,
    Settings,
    StorageConfig,
)
from job_app_helper.models import ApplicationRecord, CompanyResearch, GapReport, ParsedJob
from job_app_helper.modules.jobstreet_apply import BrowserQuestion, JobStreetApplyModule, SessionState
from job_app_helper.storage.repository import SQLiteApplicationRepository


class FakeSession:
    def __init__(self, settings, *, logged_in=True, state=None, questions=None):
        self.settings = settings
        self.logged_in = logged_in
        self.state = state or SessionState(status="ready_for_review", review_url="https://jobstreet.example/review", message="Review ready")
        self.questions = questions or []
        self.screenshot_path = ""
        self.filled_answers: list[tuple[str, str]] = []

    def open(self, url: str) -> None:
        self.url = url

    def ensure_logged_in(self) -> bool:
        return self.logged_in

    def start_apply(self) -> None:
        return None

    def upload_document(self, kind: str, path: str) -> bool:
        return True

    def fill_profile_fields(self, profile_fields: dict[str, str]) -> list[str]:
        return [key for key, value in profile_fields.items() if value]

    def collect_screening_questions(self):
        return self.questions

    def answer_question(self, question: BrowserQuestion, answer: str) -> None:
        self.filled_answers.append((question.text, answer))

    def detect_state(self) -> SessionState:
        return self.state

    def capture_screenshot(self, path: str) -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text("fake", encoding="utf-8")
        self.screenshot_path = path
        return path

    def close(self) -> None:
        return None


class FakeComputerUse:
    def analyze(self, instruction: str, context: dict[str, str]):
        class Response:
            action = "ask_user"
            reason = "Need manual review"
            metadata = {}
            provider = "gemini"
            model = "fake"

        return Response()


class JobStreetApplyModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path("tmp") / f"test-jobstreet-apply-{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        (root / "output" / "0001-acme").mkdir(parents=True, exist_ok=True)
        (root / "output" / "browser-screenshots").mkdir(parents=True, exist_ok=True)
        (root / "output" / "0001-acme" / "resume.md").write_text("resume", encoding="utf-8")
        (root / "output" / "0001-acme" / "cover-letter.txt").write_text("cover", encoding="utf-8")
        self.settings = Settings(
            ai=AIProviderConfig(),
            paths=PathConfig(
                default_resume_path=str(root / "resumes" / "default_resume.md"),
                output_dir=str(root / "output"),
                prompts_dir="job_app_helper/prompts",
                templates_dir="job_app_helper/templates",
                browser_profile_dir=str(root / "browser-profile"),
                automation_screenshots_dir=str(root / "output" / "browser-screenshots"),
            ),
            storage=StorageConfig(sqlite_db_path=str(root / "db.sqlite")),
            search=SearchConfig(),
            optimization=OptimizationConfig(),
            automation=AutomationConfig(enabled=True, stop_before_submit=True),
            computer_use=ComputerUseConfig(api_key="test-key"),
            applicant_profile=ApplicantProfileConfig(email="ari@example.com", phone="12345"),
        )
        self.repo = SQLiteApplicationRepository(self.settings.storage.sqlite_db_path)
        self.repo.init_schema()
        self.application_id = self.repo.save_application(_sample_record(root))

    def test_apply_records_user_answer_and_audit_markdown(self) -> None:
        session = FakeSession(
            self.settings,
            questions=[BrowserQuestion(key="why-join", text="Why do you want to join?", field_type="text")],
        )
        module = JobStreetApplyModule(
            self.settings,
            self.repo,
            FakeComputerUse(),
            lambda settings: session,
        )

        result = module.apply(
            self.application_id,
            answer_provider=lambda question: "Because the role matches my experience.",
        )

        answers = self.repo.get_screening_answers(self.application_id)
        self.assertEqual(result.apply_status, "ready_for_review")
        self.assertEqual(len(answers), 1)
        self.assertTrue(Path(result.audit_markdown_path).exists())
        self.assertIn("Why do you want to join?", Path(result.audit_markdown_path).read_text(encoding="utf-8"))

    def test_apply_pauses_when_login_needed(self) -> None:
        session = FakeSession(self.settings, logged_in=False)
        module = JobStreetApplyModule(self.settings, self.repo, FakeComputerUse(), lambda settings: session)

        result = module.apply(self.application_id, answer_provider=lambda question: "")

        self.assertEqual(result.apply_status, "awaiting_user_input")
        self.assertTrue(Path(result.screenshot_path).exists())

    def test_unknown_state_uses_computer_use_fallback(self) -> None:
        session = FakeSession(self.settings, state=SessionState(status="unknown", review_url="", message="Unknown"))
        module = JobStreetApplyModule(self.settings, self.repo, FakeComputerUse(), lambda settings: session)

        result = module.apply(self.application_id, answer_provider=lambda question: "")

        self.assertEqual(result.apply_status, "awaiting_user_input")
        events = self.repo.list_apply_events(self.application_id)
        self.assertTrue(any(event["event_type"] == "apply_paused" for event in events))


def _sample_record(root: Path) -> ApplicationRecord:
    return ApplicationRecord.build(
        url="https://www.jobstreet.com.sg/job/123",
        parsed_job=ParsedJob(
            url="https://www.jobstreet.com.sg/job/123",
            title="Data Analyst",
            company="Acme",
            description="desc",
            requirements=["SQL"],
            responsibilities=["Analyze"],
        ),
        company_research=CompanyResearch(
            company="Acme",
            summary="",
            culture_notes=[],
            products_services=[],
            recent_news=[],
            hiring_signals=[],
            sources=[],
        ),
        gap_report=GapReport(
            matched_skills=["SQL"],
            missing_skills=[],
            experience_gaps=[],
            keyword_gaps=[],
            match_score=80,
            analysis_notes="Good fit",
        ),
        resume_path=str(root / "output" / "0001-acme" / "resume.md"),
        cover_letter_path=str(root / "output" / "0001-acme" / "cover-letter.txt"),
        report_path=str(root / "output" / "0001-acme" / "application-report.md"),
    )


if __name__ == "__main__":
    unittest.main()
