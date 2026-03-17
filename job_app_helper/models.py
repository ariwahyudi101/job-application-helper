from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ParsedJob:
    url: str
    title: str
    company: str
    description: str
    requirements: list[str]
    responsibilities: list[str]
    language: str = "en"
    cleaned_by_ai: bool = False


@dataclass
class CompanyResearch:
    company: str
    summary: str
    culture_notes: list[str]
    products_services: list[str]
    recent_news: list[str]
    hiring_signals: list[str]
    sources: list[str] = field(default_factory=list)


@dataclass
class GapReport:
    matched_skills: list[str]
    missing_skills: list[str]
    experience_gaps: list[str]
    keyword_gaps: list[str]
    match_score: int
    analysis_notes: str
    closeable_gaps: list[str] = field(default_factory=list)
    stretch_gaps: list[str] = field(default_factory=list)
    hard_stop_gaps: list[str] = field(default_factory=list)


@dataclass
class ApplicationRecord:
    created_at: str
    url: str
    parsed_job: dict[str, Any]
    company_research: dict[str, Any]
    gap_report: dict[str, Any]
    resume_path: str
    cover_letter_path: str
    report_path: str
    apply_status: str = "not_started"
    apply_portal: str = ""
    apply_attempted_at: str = ""
    apply_error_reason: str = ""
    apply_review_url: str = ""
    apply_screenshot_path: str = ""
    screening_answers: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        url: str,
        parsed_job: ParsedJob,
        company_research: CompanyResearch,
        gap_report: GapReport,
        resume_path: str,
        cover_letter_path: str,
        report_path: str,
    ) -> "ApplicationRecord":
        return cls(
            created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            url=url,
            parsed_job=asdict(parsed_job),
            company_research=asdict(company_research),
            gap_report=asdict(gap_report),
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            report_path=report_path,
        )


@dataclass
class ApplicationRunResult:
    application_id: int
    match_score: int
    rewrite_performed: bool
    rewrite_decision_reason: str
    resume_path: str
    cover_letter_path: str
    report_path: str
    step_timings: dict[str, float] = field(default_factory=dict)
    total_duration_seconds: float = 0.0


@dataclass
class ScreeningAnswerRecord:
    application_id: int
    question_key: str
    question_text: str
    answer_text: str
    source: str
    created_at: str
    field_type: str = "text"
    options_json: str = ""

    @classmethod
    def build(
        cls,
        application_id: int,
        question_key: str,
        question_text: str,
        answer_text: str,
        source: str,
        *,
        field_type: str = "text",
        options: list[str] | None = None,
    ) -> "ScreeningAnswerRecord":
        return cls(
            application_id=application_id,
            question_key=question_key,
            question_text=question_text,
            answer_text=answer_text,
            source=source,
            created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            field_type=field_type,
            options_json=json_dumps(options or []),
        )


@dataclass
class ApplyEventRecord:
    application_id: int
    event_type: str
    message: str
    details: dict[str, Any]
    created_at: str

    @classmethod
    def build(
        cls,
        application_id: int,
        event_type: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> "ApplyEventRecord":
        return cls(
            application_id=application_id,
            event_type=event_type,
            message=message,
            details=details or {},
            created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        )


@dataclass
class ApplyRunResult:
    application_id: int
    apply_status: str
    portal: str
    review_url: str = ""
    screenshot_path: str = ""
    audit_markdown_path: str = ""
    message: str = ""
    pending_questions: list[str] = field(default_factory=list)


def json_dumps(value: Any) -> str:
    return __import__("json").dumps(value, ensure_ascii=False)
