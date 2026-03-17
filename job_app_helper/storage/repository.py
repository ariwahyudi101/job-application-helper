from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from job_app_helper.models import ApplicationRecord, ApplyEventRecord, ScreeningAnswerRecord


class ApplicationRepository:
    """Swappable persistence interface."""

    def init_schema(self) -> None:
        raise NotImplementedError

    def save_application(self, record: ApplicationRecord) -> int:
        raise NotImplementedError

    def get_next_application_id(self) -> int:
        raise NotImplementedError

    def get_application(self, application_id: int) -> dict[str, Any] | None:
        raise NotImplementedError

    def update_apply_state(self, application_id: int, **fields: Any) -> None:
        raise NotImplementedError

    def save_screening_answer(self, answer: ScreeningAnswerRecord) -> None:
        raise NotImplementedError

    def get_screening_answers(self, application_id: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def append_apply_event(self, event: ApplyEventRecord) -> None:
        raise NotImplementedError

    def list_apply_events(self, application_id: int) -> list[dict[str, Any]]:
        raise NotImplementedError


class SQLiteApplicationRepository(ApplicationRepository):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    parsed_job_json TEXT NOT NULL,
                    company_research_json TEXT NOT NULL,
                    gap_report_json TEXT NOT NULL,
                    match_score INTEGER NOT NULL,
                    resume_path TEXT NOT NULL,
                    cover_letter_path TEXT NOT NULL,
                    report_path TEXT NOT NULL DEFAULT '',
                    apply_status TEXT NOT NULL DEFAULT 'not_started',
                    apply_portal TEXT NOT NULL DEFAULT '',
                    apply_attempted_at TEXT NOT NULL DEFAULT '',
                    apply_error_reason TEXT NOT NULL DEFAULT '',
                    apply_review_url TEXT NOT NULL DEFAULT '',
                    apply_screenshot_path TEXT NOT NULL DEFAULT '',
                    screening_answers_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS screening_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    question_key TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    field_type TEXT NOT NULL DEFAULT 'text',
                    options_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS apply_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(applications)").fetchall()
            }
            if "report_path" not in columns:
                conn.execute("ALTER TABLE applications ADD COLUMN report_path TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, columns, "apply_status", "TEXT NOT NULL DEFAULT 'not_started'")
            self._ensure_column(conn, columns, "apply_portal", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, columns, "apply_attempted_at", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, columns, "apply_error_reason", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, columns, "apply_review_url", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, columns, "apply_screenshot_path", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, columns, "screening_answers_json", "TEXT NOT NULL DEFAULT '[]'")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, columns: set[str], name: str, ddl: str) -> None:
        if name not in columns:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {name} {ddl}")
            columns.add(name)

    def save_application(self, record: ApplicationRecord) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO applications (
                    created_at, url, parsed_job_json, company_research_json,
                    gap_report_json, match_score, resume_path, cover_letter_path, report_path,
                    apply_status, apply_portal, apply_attempted_at, apply_error_reason,
                    apply_review_url, apply_screenshot_path, screening_answers_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.created_at,
                    record.url,
                    json.dumps(record.parsed_job),
                    json.dumps(record.company_research),
                    json.dumps(record.gap_report),
                    int(record.gap_report.get("match_score", 0)),
                    record.resume_path,
                    record.cover_letter_path,
                    record.report_path,
                    record.apply_status,
                    record.apply_portal,
                    record.apply_attempted_at,
                    record.apply_error_reason,
                    record.apply_review_url,
                    record.apply_screenshot_path,
                    json.dumps(record.screening_answers),
                ),
            )
            return int(cur.lastrowid)

    def get_next_application_id(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM applications").fetchone()
            return int(row["next_id"])

    def get_application(self, application_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "created_at": row["created_at"],
                "url": row["url"],
                "parsed_job": json.loads(row["parsed_job_json"]),
                "company_research": json.loads(row["company_research_json"]),
                "gap_report": json.loads(row["gap_report_json"]),
                "match_score": row["match_score"],
                "resume_path": row["resume_path"],
                "cover_letter_path": row["cover_letter_path"],
                "report_path": row["report_path"],
                "apply_status": row["apply_status"],
                "apply_portal": row["apply_portal"],
                "apply_attempted_at": row["apply_attempted_at"],
                "apply_error_reason": row["apply_error_reason"],
                "apply_review_url": row["apply_review_url"],
                "apply_screenshot_path": row["apply_screenshot_path"],
                "screening_answers": json.loads(row["screening_answers_json"] or "[]"),
            }

    def update_apply_state(self, application_id: int, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [application_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE applications SET {assignments} WHERE id = ?",
                values,
            )

    def save_screening_answer(self, answer: ScreeningAnswerRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO screening_answers (
                    application_id, question_key, question_text, answer_text, source,
                    field_type, options_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer.application_id,
                    answer.question_key,
                    answer.question_text,
                    answer.answer_text,
                    answer.source,
                    answer.field_type,
                    answer.options_json,
                    answer.created_at,
                ),
            )
            latest_answers = self._get_screening_answers_with_conn(conn, answer.application_id)
            conn.execute(
                "UPDATE applications SET screening_answers_json = ? WHERE id = ?",
                (json.dumps(latest_answers), answer.application_id),
            )

    def get_screening_answers(self, application_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return self._get_screening_answers_with_conn(conn, application_id)

    @staticmethod
    def _get_screening_answers_with_conn(conn: sqlite3.Connection, application_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT question_key, question_text, answer_text, source, field_type, options_json, created_at
            FROM screening_answers
            WHERE application_id = ?
            ORDER BY id ASC
            """,
            (application_id,),
        ).fetchall()
        return [
            {
                "question_key": row["question_key"],
                "question_text": row["question_text"],
                "answer_text": row["answer_text"],
                "source": row["source"],
                "field_type": row["field_type"],
                "options": json.loads(row["options_json"] or "[]"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def append_apply_event(self, event: ApplyEventRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO apply_events (application_id, event_type, message, details_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.application_id,
                    event.event_type,
                    event.message,
                    json.dumps(event.details),
                    event.created_at,
                ),
            )

    def list_apply_events(self, application_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_type, message, details_json, created_at
                FROM apply_events
                WHERE application_id = ?
                ORDER BY id ASC
                """,
                (application_id,),
            ).fetchall()
            return [
                {
                    "event_type": row["event_type"],
                    "message": row["message"],
                    "details": json.loads(row["details_json"] or "{}"),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
