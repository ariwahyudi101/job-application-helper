from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from job_app_helper.models import ApplicationRecord


class ApplicationRepository:
    """Swappable persistence interface."""

    def init_schema(self) -> None:
        raise NotImplementedError

    def save_application(self, record: ApplicationRecord) -> int:
        raise NotImplementedError

    def get_application(self, application_id: int) -> dict[str, Any] | None:
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
                    cover_letter_path TEXT NOT NULL
                )
                """
            )

    def save_application(self, record: ApplicationRecord) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO applications (
                    created_at, url, parsed_job_json, company_research_json,
                    gap_report_json, match_score, resume_path, cover_letter_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            return int(cur.lastrowid)

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
            }
