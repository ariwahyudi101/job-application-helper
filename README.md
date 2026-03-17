# Job Application Helper

Lean, modular Python CLI that automates a personal job application workflow:

1. Parse a job posting URL
2. Research the company
3. Analyze resume gaps and match score
4. Gate low-fit roles using a baseline score threshold with a transferable-fit override for adjacent profiles
5. Rewrite resume for ATS alignment (`.md`) when the role passes the gate or qualifies through strong transferable signals
6. Generate cover letter (`.txt`) for passed roles, or write a skip note when the role is gated out
7. Rapikan output per lowongan ke folder pendek (AI-generated naming)
8. Store all artifacts in SQLite
9. Query previous applications with natural language
10. Semi-auto apply to JobStreet with browser automation, audit trail, and review stop

If a role fails the baseline gate, the app still saves:
- a baseline resume copy inside the job output folder
- a cover-letter note explaining why tailoring was skipped
- the application report

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp config.example.json config.json
playwright install chromium
```

Set API keys via `config.json` or env vars:
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY`
- `GEMINI_API_KEY` or `JAH_COMPUTER_USE_API_KEY`

## Apply automation setup

Detailed setup and behavior guide:
- `docs/jobstreet-apply.md`

Important config areas:
- `automation.enabled`: enable JobStreet apply flow
- `automation.stop_before_submit`: default `true`, so flow stops at review page
- `paths.browser_profile_dir`: persistent browser profile for keeping JobStreet login session
- `paths.automation_screenshots_dir`: screenshot output for failure/review states
- `computer_use.provider` / `computer_use.model`: computer-use classifier configuration
- `applicant_profile.*`: profile fields that can be auto-filled or reused as default screening answers

Recommended first run:
1. Fill `applicant_profile` in `config.json`.
2. Set `GEMINI_API_KEY` in `.env` or environment variables.
3. Run `python main.py` and make sure at least one application record already exists.
4. Use the apply menu or CLI command below.
5. If JobStreet asks for login, complete it in the opened browser profile and rerun.

## Interactive menu

```bash
python main.py
```

Menu options:
- Masukkan URL lowongan baru
- Bertanya tentang lowongan yang sudah lewat
- Regenerate ulang analisis dan dokumen
- Apply semi-auto ke JobStreet

## Command mode

```bash
python main.py --config config.json run "https://example.com/job-posting"
python main.py --config config.json ask 1 "What were my keyword gaps?"
python main.py --config config.json apply 1
```

The JobStreet apply flow will:
- open the stored JobStreet posting URL
- reuse your persistent browser session
- upload resume and cover letter if available
- fill known profile fields
- ask for missing screening answers in the terminal
- save screening answers to SQLite and `screening-answers.md`
- stop at review page by default instead of submitting

## Audit trail

Each apply attempt stores:
- apply status and review metadata in SQLite
- screening answer history in SQLite
- apply events in SQLite
- `screening-answers.md` in the application output folder
- a screenshot in `paths.automation_screenshots_dir`

For the full operational guide, troubleshooting, and status meanings, see:
- `docs/jobstreet-apply.md`

## Module interfaces

- `JobParserModule.parse(url: str) -> ParsedJob`
- `CompanyResearchModule.research(parsed_job: ParsedJob) -> CompanyResearch`
- `GapAnalysisModule.analyze(parsed_job: ParsedJob, default_resume_path: str) -> GapReport`
- `ResumeRewriteModule.rewrite(default_resume_path: str, parsed_job: ParsedJob, gap_report: GapReport, target_apply_score: int, stretch_score: int, output_path: str | None = None) -> str`
- `CoverLetterModule.write(rewritten_resume_path: str, parsed_job: ParsedJob, company_research: CompanyResearch, output_path: str | None = None) -> str`
- `SQLiteApplicationRepository.save_application(record: ApplicationRecord) -> int`
- `QueryChatModule.ask(application_id: int, question: str) -> str`
- `JobApplicationPipeline.apply_to_jobstreet(application_id: int, progress_callback: Callable[[str], None] | None = None) -> ApplyRunResult`

Each module is independent and can be tested in isolation by injecting a mocked AI client, browser session, or repository.
