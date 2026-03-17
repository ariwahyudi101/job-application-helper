from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from job_app_helper.config import ApplicantProfileConfig, Settings
from job_app_helper.models import ApplyEventRecord, ApplyRunResult, ScreeningAnswerRecord
from job_app_helper.providers.computer_use import ComputerUseClient, ComputerUseError
from job_app_helper.storage.repository import ApplicationRepository


class BrowserAutomationError(RuntimeError):
    pass


@dataclass
class BrowserQuestion:
    key: str
    text: str
    field_type: str = "text"
    options: list[str] = field(default_factory=list)
    required: bool = True


@dataclass
class SessionState:
    status: str
    review_url: str = ""
    message: str = ""
    pending_questions: list[BrowserQuestion] = field(default_factory=list)


class BrowserAutomationSession(Protocol):
    def open(self, url: str) -> None:
        ...

    def ensure_logged_in(self) -> bool:
        ...

    def start_apply(self) -> None:
        ...

    def upload_document(self, kind: str, path: str) -> bool:
        ...

    def fill_profile_fields(self, profile_fields: dict[str, str]) -> list[str]:
        ...

    def collect_screening_questions(self) -> list[BrowserQuestion]:
        ...

    def answer_question(self, question: BrowserQuestion, answer: str) -> None:
        ...

    def detect_state(self) -> SessionState:
        ...

    def capture_screenshot(self, path: str) -> str:
        ...

    def close(self) -> None:
        ...


class JobStreetApplyModule:
    def __init__(
        self,
        settings: Settings,
        repo: ApplicationRepository,
        computer_use_client: ComputerUseClient | None,
        session_factory: Callable[[Settings], BrowserAutomationSession],
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.computer_use_client = computer_use_client
        self.session_factory = session_factory

    def apply(
        self,
        application_id: int,
        *,
        progress_callback: Callable[[str], None] | None = None,
        answer_provider: Callable[[str], str] | None = None,
    ) -> ApplyRunResult:
        application = self.repo.get_application(application_id)
        if not application:
            raise ValueError(f"Application id={application_id} tidak ditemukan.")
        if "jobstreet" not in application["url"].lower():
            raise ValueError("Apply automation V1 hanya mendukung URL JobStreet.")

        resume_path = Path(application["resume_path"])
        if not resume_path.exists():
            self.repo.update_apply_state(
                application_id,
                apply_status="failed",
                apply_portal="jobstreet",
                apply_error_reason=f"Resume tidak ditemukan: {resume_path}",
            )
            raise ValueError(f"Resume tidak ditemukan: {resume_path}")

        cover_letter_path = Path(application["cover_letter_path"])
        output_dir = resume_path.parent
        audit_path = output_dir / "screening-answers.md"
        screenshot_path = Path(self.settings.paths.automation_screenshots_dir) / f"{application_id:04d}-jobstreet.png"

        def emit(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        self.repo.update_apply_state(
            application_id,
            apply_status="draft_started",
            apply_portal="jobstreet",
            apply_attempted_at=_utc_now(),
            apply_error_reason="",
        )
        self.repo.append_apply_event(
            ApplyEventRecord.build(
                application_id,
                "apply_started",
                "Memulai flow semi-auto apply JobStreet.",
                details={"url": application["url"]},
            )
        )

        session = self.session_factory(self.settings)
        try:
            emit("Buka halaman lowongan JobStreet")
            session.open(application["url"])
            if not session.ensure_logged_in():
                return self._pause_state(
                    application_id,
                    audit_path,
                    screenshot_path,
                    "awaiting_user_input",
                    "Login JobStreet diperlukan sebelum apply.",
                    session=session,
                )

            emit("Mulai flow apply")
            session.start_apply()

            emit("Upload dokumen aplikasi")
            session.upload_document("resume", str(resume_path))
            if cover_letter_path.exists():
                session.upload_document("cover_letter", str(cover_letter_path))

            emit("Isi field profil standar")
            filled_fields = session.fill_profile_fields(_profile_field_map(self.settings.applicant_profile))
            if filled_fields:
                self.repo.append_apply_event(
                    ApplyEventRecord.build(
                        application_id,
                        "profile_fields_filled",
                        "Mengisi field standar profil pelamar.",
                        details={"fields": filled_fields},
                    )
                )

            emit("Cek pertanyaan screening")
            pending_questions: list[str] = []
            for question in session.collect_screening_questions():
                answer_text, source = self._resolve_answer(application_id, question, answer_provider=answer_provider)
                if not answer_text:
                    pending_questions.append(question.text)
                    break
                session.answer_question(question, answer_text)
                self._persist_answer(application_id, question, answer_text, source)

            state = session.detect_state()
            if pending_questions:
                state = SessionState(
                    status="awaiting_user_input",
                    message="Ada pertanyaan screening yang butuh jawaban manual.",
                    review_url=state.review_url,
                    pending_questions=[BrowserQuestion(key="", text=q) for q in pending_questions],
                )

            if state.status == "unknown":
                state = self._resolve_unknown_state(state)

            if state.status in {"awaiting_user_input", "login_needed", "captcha", "failed"}:
                message = state.message or "Flow apply perlu intervensi manual."
                return self._pause_state(
                    application_id,
                    audit_path,
                    screenshot_path,
                    "awaiting_user_input" if state.status != "failed" else "failed",
                    message,
                    session=session,
                    review_url=state.review_url,
                    pending_questions=[question.text for question in state.pending_questions],
                )

            final_status = "ready_for_review" if self.settings.automation.stop_before_submit else "submitted"
            saved_screenshot = session.capture_screenshot(str(screenshot_path))
            self.repo.update_apply_state(
                application_id,
                apply_status=final_status,
                apply_portal="jobstreet",
                apply_review_url=state.review_url,
                apply_screenshot_path=saved_screenshot,
            )
            self.repo.append_apply_event(
                ApplyEventRecord.build(
                    application_id,
                    "review_ready",
                    "Flow apply berhenti di halaman review.",
                    details={"review_url": state.review_url},
                )
            )
            _write_screening_audit_markdown(
                application,
                self.repo.get_screening_answers(application_id),
                self.repo.list_apply_events(application_id),
                audit_path,
            )
            return ApplyRunResult(
                application_id=application_id,
                apply_status=final_status,
                portal="jobstreet",
                review_url=state.review_url,
                screenshot_path=saved_screenshot,
                audit_markdown_path=str(audit_path),
                message=state.message or "Draft apply siap direview.",
            )
        except BrowserAutomationError as exc:
            return self._pause_state(
                application_id,
                audit_path,
                screenshot_path,
                "failed",
                str(exc),
                session=session,
            )
        finally:
            session.close()

    def _resolve_answer(
        self,
        application_id: int,
        question: BrowserQuestion,
        *,
        answer_provider: Callable[[str], str] | None,
    ) -> tuple[str, str]:
        cached_answers = self.repo.get_screening_answers(application_id)
        for item in reversed(cached_answers):
            if item["question_key"] == question.key and item["answer_text"].strip():
                return item["answer_text"], "cached_answer"

        profile_answer = _profile_answer_for_question(self.settings.applicant_profile, question.text)
        if profile_answer:
            return profile_answer, "config_default"

        if answer_provider:
            answer_text = answer_provider(question.text).strip()
            if answer_text:
                return answer_text, "user_input"
        return "", ""

    def _persist_answer(self, application_id: int, question: BrowserQuestion, answer_text: str, source: str) -> None:
        self.repo.save_screening_answer(
            ScreeningAnswerRecord.build(
                application_id,
                question.key,
                question.text,
                answer_text,
                source,
                field_type=question.field_type,
                options=question.options,
            )
        )
        self.repo.append_apply_event(
            ApplyEventRecord.build(
                application_id,
                "screening_answer_recorded",
                f"Menyimpan jawaban untuk pertanyaan: {question.text}",
                details={"question_key": question.key, "source": source},
            )
        )

    def _resolve_unknown_state(self, state: SessionState) -> SessionState:
        if not self.computer_use_client:
            return SessionState(status="awaiting_user_input", message="State halaman apply belum dikenali.")
        try:
            response = self.computer_use_client.analyze(
                "Classify the current JobStreet apply page state conservatively.",
                {"status": state.status, "message": state.message, "review_url": state.review_url},
            )
        except ComputerUseError:
            return SessionState(status="awaiting_user_input", message="State halaman apply belum dikenali.")
        action_to_status = {
            "continue": "awaiting_user_input",
            "review_ready": "ready_for_review",
            "login_needed": "login_needed",
            "captcha": "captcha",
            "ask_user": "awaiting_user_input",
            "failed": "failed",
        }
        return SessionState(
            status=action_to_status.get(response.action, "awaiting_user_input"),
            review_url=state.review_url,
            message=response.reason or state.message,
        )

    def _pause_state(
        self,
        application_id: int,
        audit_path: Path,
        screenshot_path: Path,
        apply_status: str,
        message: str,
        *,
        session: BrowserAutomationSession,
        review_url: str = "",
        pending_questions: list[str] | None = None,
    ) -> ApplyRunResult:
        saved_screenshot = session.capture_screenshot(str(screenshot_path))
        self.repo.update_apply_state(
            application_id,
            apply_status=apply_status,
            apply_portal="jobstreet",
            apply_error_reason=message,
            apply_review_url=review_url,
            apply_screenshot_path=saved_screenshot,
        )
        self.repo.append_apply_event(
            ApplyEventRecord.build(
                application_id,
                "apply_paused" if apply_status != "failed" else "apply_failed",
                message,
                details={"review_url": review_url, "pending_questions": pending_questions or []},
            )
        )
        application = self.repo.get_application(application_id) or {"url": "", "resume_path": "", "cover_letter_path": ""}
        _write_screening_audit_markdown(
            application,
            self.repo.get_screening_answers(application_id),
            self.repo.list_apply_events(application_id),
            audit_path,
        )
        return ApplyRunResult(
            application_id=application_id,
            apply_status=apply_status,
            portal="jobstreet",
            review_url=review_url,
            screenshot_path=saved_screenshot,
            audit_markdown_path=str(audit_path),
            message=message,
            pending_questions=pending_questions or [],
        )


class PlaywrightJobStreetSession:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserAutomationError(
                "Playwright belum terinstall. Jalankan `pip install playwright` lalu `playwright install chromium`."
            ) from exc
        self._sync_playwright = sync_playwright
        self._manager = None
        self._context = None
        self._page = None

    def open(self, url: str) -> None:
        self._manager = self._sync_playwright().start()
        chromium = self._manager.chromium
        self._context = chromium.launch_persistent_context(
            user_data_dir=self.settings.paths.browser_profile_dir,
            headless=bool(self.settings.automation.headless),
        )
        self._page = self._context.new_page()
        self._page.goto(url, wait_until="domcontentloaded")

    def ensure_logged_in(self) -> bool:
        assert self._page is not None
        page_text = self._page.locator("body").inner_text(timeout=3000).lower()
        if "sign in" in page_text or "login" in page_text:
            return False
        return True

    def start_apply(self) -> None:
        assert self._page is not None
        for selector in [
            "text=Apply now",
            "text=Apply",
            "button:has-text('Apply')",
            "[data-automation='job-detail-apply']",
        ]:
            locator = self._page.locator(selector).first
            if locator.count():
                locator.click(timeout=5000)
                self._page.wait_for_load_state("domcontentloaded")
                return

    def upload_document(self, kind: str, path: str) -> bool:
        assert self._page is not None
        selectors = {
            "resume": ["[data-automation='resume-upload'] input[type='file']", "input[type='file']"],
            "cover_letter": ["[data-automation='cover-letter-upload'] input[type='file']", "input[type='file']"],
        }
        for selector in selectors.get(kind, []):
            locator = self._page.locator(selector).first
            if locator.count():
                locator.set_input_files(path)
                return True
        return False

    def fill_profile_fields(self, profile_fields: dict[str, str]) -> list[str]:
        assert self._page is not None
        filled: list[str] = []
        for label, value in profile_fields.items():
            if not value:
                continue
            for selector in _profile_selectors(label):
                locator = self._page.locator(selector).first
                if locator.count():
                    try:
                        locator.fill(value)
                        filled.append(label)
                        break
                    except Exception:
                        continue
        return filled

    def collect_screening_questions(self) -> list[BrowserQuestion]:
        assert self._page is not None
        rows = self._page.evaluate(
            """
            () => {
              const elements = Array.from(document.querySelectorAll("input, textarea, select"));
              return elements
                .filter((el) => {
                  const type = (el.getAttribute("type") || "").toLowerCase();
                  if (["hidden", "file", "submit", "button"].includes(type)) return false;
                  return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
                })
                .map((el) => {
                  const label = el.labels && el.labels.length ? Array.from(el.labels).map((item) => item.innerText.trim()).join(" ") : "";
                  const aria = el.getAttribute("aria-label") || "";
                  const placeholder = el.getAttribute("placeholder") || "";
                  const question = (label || aria || placeholder || "").trim();
                  const options = el.tagName === "SELECT" ? Array.from(el.options).map((opt) => opt.textContent.trim()).filter(Boolean) : [];
                  return {
                    question,
                    type: el.tagName.toLowerCase() === "select" ? "select" : (el.getAttribute("type") || el.tagName || "text").toLowerCase(),
                    options
                  };
                })
                .filter((item) => item.question);
            }
            """
        )
        questions: list[BrowserQuestion] = []
        for row in rows:
            if _is_profile_question(row["question"]):
                continue
            questions.append(
                BrowserQuestion(
                    key=normalize_question_key(row["question"]),
                    text=row["question"],
                    field_type=row["type"],
                    options=row.get("options", []),
                )
            )
        return _dedupe_questions(questions)

    def answer_question(self, question: BrowserQuestion, answer: str) -> None:
        assert self._page is not None
        target = self._page.get_by_label(question.text, exact=False).first
        if target.count():
            _fill_locator(target, question.field_type, answer)
            return
        placeholder = self._page.get_by_placeholder(question.text, exact=False).first
        if placeholder.count():
            _fill_locator(placeholder, question.field_type, answer)

    def detect_state(self) -> SessionState:
        assert self._page is not None
        text = self._page.locator("body").inner_text(timeout=3000).lower()
        current_url = self._page.url
        if "captcha" in text or "verify you are human" in text:
            return SessionState(status="captcha", review_url=current_url, message="CAPTCHA atau verifikasi manusia terdeteksi.")
        if "review" in text or "submit application" in text or "check your application" in text:
            return SessionState(status="ready_for_review", review_url=current_url, message="Halaman review terdeteksi.")
        return SessionState(status="unknown", review_url=current_url, message="State halaman belum dikenali.")

    def capture_screenshot(self, path: str) -> str:
        if self._page is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._page.screenshot(path=path, full_page=True)
        return path

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        if self._manager is not None:
            self._manager.stop()
            self._manager = None


def default_jobstreet_session_factory(settings: Settings) -> BrowserAutomationSession:
    return PlaywrightJobStreetSession(settings)


def normalize_question_key(question: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return normalized[:80] or "unknown-question"


def _utc_now() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _profile_field_map(profile: ApplicantProfileConfig) -> dict[str, str]:
    return {
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "years_of_experience": profile.years_of_experience,
        "current_salary": profile.current_salary,
        "expected_salary": profile.expected_salary,
        "notice_period": profile.notice_period,
        "work_authorization": profile.work_authorization,
    }


def _profile_answer_for_question(profile: ApplicantProfileConfig, question_text: str) -> str:
    lowered = question_text.lower()
    lookup = {
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "experience": profile.years_of_experience,
        "current salary": profile.current_salary,
        "expected salary": profile.expected_salary,
        "notice period": profile.notice_period,
        "work authorization": profile.work_authorization,
        "authorized": profile.work_authorization,
        "name": profile.full_name,
    }
    for key, value in lookup.items():
        if key in lowered and value:
            return value
    return ""


def _profile_selectors(label: str) -> list[str]:
    mapping = {
        "full_name": ["input[name*='name']", "input[autocomplete='name']"],
        "email": ["input[type='email']", "input[name*='email']"],
        "phone": ["input[type='tel']", "input[name*='phone']"],
        "location": ["input[name*='location']", "input[placeholder*='Location']"],
        "years_of_experience": ["input[name*='experience']"],
        "current_salary": ["input[name*='current'][name*='salary']"],
        "expected_salary": ["input[name*='expected'][name*='salary']"],
        "notice_period": ["input[name*='notice']"],
        "work_authorization": ["input[name*='authorization']", "input[name*='visa']"],
    }
    return mapping.get(label, [])


def _is_profile_question(question_text: str) -> bool:
    lowered = question_text.lower()
    keywords = ["name", "email", "phone", "location", "salary", "notice", "authorization", "experience"]
    return any(keyword in lowered for keyword in keywords)


def _dedupe_questions(questions: list[BrowserQuestion]) -> list[BrowserQuestion]:
    seen: set[str] = set()
    result: list[BrowserQuestion] = []
    for question in questions:
        if question.key in seen:
            continue
        seen.add(question.key)
        result.append(question)
    return result


def _fill_locator(locator, field_type: str, answer: str) -> None:
    if field_type.lower() == "select":
        try:
            locator.select_option(label=answer)
            return
        except Exception:
            pass
    locator.fill(answer)


def _write_screening_audit_markdown(
    application: dict,
    screening_answers: list[dict],
    apply_events: list[dict],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# JobStreet Apply Audit Trail",
        "",
        f"- URL: {application.get('url', '')}",
        f"- Resume: {application.get('resume_path', '')}",
        f"- Cover letter: {application.get('cover_letter_path', '')}",
        "",
        "## Screening Answers",
        "",
    ]
    if screening_answers:
        for answer in screening_answers:
            lines.extend(
                [
                    f"### {answer['question_text']}",
                    f"- Answer: {answer['answer_text']}",
                    f"- Source: {answer['source']}",
                    f"- Recorded at: {answer['created_at']}",
                    "",
                ]
            )
    else:
        lines.extend(["_Belum ada jawaban screening tersimpan._", ""])

    lines.extend(["## Apply Events", ""])
    if apply_events:
        for event in apply_events:
            lines.append(f"- {event['created_at']} [{event['event_type']}] {event['message']}")
    else:
        lines.append("_Belum ada event apply tercatat._")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
