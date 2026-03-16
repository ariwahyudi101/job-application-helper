# Job Application Helper

Lean, modular Python CLI that automates a personal job application workflow:

1. Parse a job posting URL
2. Research the company
3. Analyze resume gaps and match score
4. Rewrite resume for ATS alignment (`.md`)
5. Generate cover letter (`.txt`)
6. Rapikan output per lowongan ke folder pendek (AI-generated naming)
7. Store all artifacts in SQLite
8. Query previous applications with natural language

## Folder structure

```text
job-application-helper/
├── config.example.json
├── main.py
├── pyproject.toml
├── resumes/
│   └── default_resume.md
├── output/
│   ├── acme-data-eng/
│   │   ├── resume.md
│   │   └── cover-letter.txt
├── job_app_helper/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── models.py
│   ├── utils.py
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── job_parser.py
│   │   ├── company_research.py
│   │   ├── gap_analysis.py
│   │   ├── resume_rewrite.py
│   │   ├── cover_letter.py
│   │   ├── output_namer.py
│   │   └── query_chat.py
│   ├── providers/
│   │   ├── __init__.py
│   │   └── ai_client.py
│   ├── prompts/
│   │   ├── job_parser_prompt.txt
│   │   ├── company_research_prompt.txt
│   │   ├── gap_analysis_prompt.txt
│   │   ├── resume_rewrite_prompt.txt
│   │   ├── cover_letter_prompt.txt
│   │   └── query_chat_prompt.txt
│   ├── storage/
│   │   ├── __init__.py
│   │   └── repository.py
│   └── templates/
└── .gitkeep
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp config.example.json config.json
```

Set API keys via `config.json` or env vars:
- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY`

Provider reliability notes:
- Provider order is controlled by `ai.primary_provider` and `ai.fallback_provider`.
- If a provider key is missing, it is skipped automatically.
- HTTP calls use configurable `connect_timeout_seconds`, `request_timeout_seconds`, and retry settings (`max_retries`, `retry_backoff_seconds`).
- OpenRouter 404 guardrail/privacy failures include a direct hint to update privacy settings.

Run interactive menu (recommended):

```bash
python main.py
```

Menu options:
- Masukkan URL lowongan baru
- Bertanya tentang lowongan yang sudah lewat

Optional: command mode is still available:

```bash
python main.py --config config.json run "https://example.com/job-posting"
python main.py --config config.json ask 1 "What were my keyword gaps?"
```

## Module interfaces

- `JobParserModule.parse(url: str) -> ParsedJob`
- `CompanyResearchModule.research(parsed_job: ParsedJob) -> CompanyResearch`
- `GapAnalysisModule.analyze(parsed_job: ParsedJob, default_resume_path: str) -> GapReport`
- `ResumeRewriteModule.rewrite(default_resume_path: str, parsed_job: ParsedJob, gap_report: GapReport, output_path: str | None = None) -> str`
- `CoverLetterModule.write(rewritten_resume_path: str, parsed_job: ParsedJob, company_research: CompanyResearch, output_path: str | None = None) -> str`
- `SQLiteApplicationRepository.save_application(record: ApplicationRecord) -> int`
- `QueryChatModule.ask(application_id: int, question: str) -> str`

Each module is independent and can be tested in isolation by injecting a mocked AI client or repository.
