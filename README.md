# Job Application Helper

Lean, modular Python CLI that automates a personal job application workflow:

1. Parse a job posting URL
2. Research the company
3. Analyze resume gaps and match score
4. Rewrite resume for ATS alignment (`.md`)
5. Generate cover letter (`.txt`)
6. Store all artifacts in SQLite
7. Query previous applications with natural language

## Folder structure

```text
job-application-helper/
├── config.example.json
├── main.py
├── pyproject.toml
├── resumes/
│   └── default_resume.md
├── output/
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

Run pipeline:

```bash
python main.py --config config.json run "https://example.com/job-posting"
```

Ask a stored application question:

```bash
python main.py --config config.json ask 1 "What were my keyword gaps?"
```

## Module interfaces

- `JobParserModule.parse(url: str) -> ParsedJob`
- `CompanyResearchModule.research(parsed_job: ParsedJob) -> CompanyResearch`
- `GapAnalysisModule.analyze(parsed_job: ParsedJob, default_resume_path: str) -> GapReport`
- `ResumeRewriteModule.rewrite(default_resume_path: str, parsed_job: ParsedJob, gap_report: GapReport) -> str`
- `CoverLetterModule.write(rewritten_resume_path: str, parsed_job: ParsedJob, company_research: CompanyResearch) -> str`
- `SQLiteApplicationRepository.save_application(record: ApplicationRecord) -> int`
- `QueryChatModule.ask(application_id: int, question: str) -> str`

Each module is independent and can be tested in isolation by injecting a mocked AI client or repository.
