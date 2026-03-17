from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from job_app_helper.models import (
    ApplicationRecord,
    ApplyEventRecord,
    CompanyResearch,
    GapReport,
    ParsedJob,
    ScreeningAnswerRecord,
)
from job_app_helper.storage.repository import SQLiteApplicationRepository


class RepositoryApplyStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tmp") / f"test-apply-repository-{uuid.uuid4().hex}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))
        self.db_path = str(self.tmp_dir / "test.db")
        self.repo = SQLiteApplicationRepository(self.db_path)
        self.repo.init_schema()

    def test_save_application_includes_apply_defaults(self) -> None:
        application_id = self.repo.save_application(_sample_record())
        row = self.repo.get_application(application_id)

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["apply_status"], "not_started")
        self.assertEqual(row["screening_answers"], [])

    def test_save_screening_answer_updates_snapshot_and_history(self) -> None:
        application_id = self.repo.save_application(_sample_record())
        self.repo.save_screening_answer(
            ScreeningAnswerRecord.build(
                application_id,
                "work-auth",
                "Do you have work authorization?",
                "Yes",
                "user_input",
            )
        )

        answers = self.repo.get_screening_answers(application_id)
        row = self.repo.get_application(application_id)

        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["answer_text"], "Yes")
        assert row is not None
        self.assertEqual(row["screening_answers"][0]["answer_text"], "Yes")

    def test_append_apply_event_round_trip(self) -> None:
        application_id = self.repo.save_application(_sample_record())
        self.repo.append_apply_event(
            ApplyEventRecord.build(
                application_id,
                "review_ready",
                "Reached review page.",
                details={"review_url": "https://example.com/review"},
            )
        )

        events = self.repo.list_apply_events(application_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "review_ready")


def _sample_record() -> ApplicationRecord:
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
        resume_path="output/0001-acme/resume.md",
        cover_letter_path="output/0001-acme/cover-letter.txt",
        report_path="output/0001-acme/application-report.md",
    )


if __name__ == "__main__":
    unittest.main()
