from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

DATE_RANGE_RE = re.compile(
    r"(?P<start_month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+"
    r"(?P<start_year>\d{4})\s*-\s*"
    r"(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4}|Present|Current|Now)",
    re.IGNORECASE,
)


@dataclass
class TimelineAssessment:
    current_date: str
    future_dated_entries: list[str] = field(default_factory=list)

    @property
    def has_future_dated_entries(self) -> bool:
        return bool(self.future_dated_entries)

    @property
    def summary(self) -> str:
        if self.future_dated_entries:
            entries = "; ".join(self.future_dated_entries)
            return f"Future-dated resume entries detected relative to {self.current_date}: {entries}"
        return f"No future-dated resume entries detected relative to {self.current_date}."


def assess_resume_timeline(resume_text: str, today: date | None = None) -> TimelineAssessment:
    current = today or date.today()
    future_dated_entries: list[str] = []

    for match in DATE_RANGE_RE.finditer(resume_text):
        start_month = MONTHS[match.group("start_month").lower()]
        start_year = int(match.group("start_year"))
        start_date = date(start_year, start_month, 1)
        if start_date > current:
            future_dated_entries.append(match.group(0))

    return TimelineAssessment(
        current_date=current.isoformat(),
        future_dated_entries=future_dated_entries,
    )


def sanitize_future_dated_claims(text: str, assessment: TimelineAssessment) -> str:
    if assessment.has_future_dated_entries:
        return text

    lines = text.splitlines()
    filtered_lines = [
        line
        for line in lines
        if "future-dated" not in line.lower() and "future dated" not in line.lower()
    ]
    sanitized = "\n".join(filtered_lines).strip()
    return sanitized + "\n"
