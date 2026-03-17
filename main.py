from __future__ import annotations

import argparse
import sys

from job_app_helper.app import JobApplicationPipeline
from job_app_helper.config import load_settings
from job_app_helper.providers.ai_client import AIError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Job Application Helper CLI")
    parser.add_argument("--config", default="config.json", help="Path to config JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run full pipeline for a job posting URL")
    run_cmd.add_argument("url", help="Job posting URL")

    regenerate_cmd = sub.add_parser("regenerate", help="Regenerate analyses and documents for a stored application")
    regenerate_cmd.add_argument("application_id", type=int)

    ask_cmd = sub.add_parser("ask", help="Ask question about a stored application")
    ask_cmd.add_argument("application_id", type=int)
    ask_cmd.add_argument("question")

    apply_cmd = sub.add_parser("apply", help="Semi-auto apply to JobStreet for a stored application")
    apply_cmd.add_argument("application_id", type=int)

    return parser


def _prompt_non_empty(message: str) -> str:
    while True:
        value = input(message).strip()
        if value:
            return value
        print("Input tidak boleh kosong.")


def _print_run_result(result, *, language: str) -> None:
    if language == "id":
        print(f"Berhasil. Application tersimpan dengan id={result.application_id}")
        if result.rewrite_decision_reason == "baseline_gate":
            print(
                f"Skor awal {result.match_score}/100 melewati gate. Resume dan surat lamaran dibuat."
            )
        elif result.rewrite_decision_reason == "transferable_override":
            print(
                f"Skor awal {result.match_score}/100 tetap dilanjutkan karena sinyal transferable fit kuat. Resume dan surat lamaran dibuat."
            )
        else:
            print(
                f"Skor awal {result.match_score}/100 di bawah gate. Resume dasar, catatan cover letter, dan report tetap disimpan."
            )
    else:
        print(f"Application stored with id={result.application_id}")
        if result.rewrite_decision_reason == "baseline_gate":
            print(f"Baseline score {result.match_score}/100 passed the gate.")
        elif result.rewrite_decision_reason == "transferable_override":
            print(
                f"Baseline score {result.match_score}/100 advanced via transferable-fit override."
            )
        else:
            print(
                f"Baseline score {result.match_score}/100 missed the gate. Baseline resume and review artifacts were still saved."
            )

    print(f"Resume: {result.resume_path}")
    print(f"Cover letter: {result.cover_letter_path}")
    print(f"Report: {result.report_path}")
    if result.step_timings:
        if language == "id":
            print("Timing:")
        else:
            print("Timing:")
        for step_name, duration in sorted(result.step_timings.items(), key=lambda item: item[1], reverse=True):
            print(f"- {step_name}: {duration:.1f}s")
        print(f"Total: {result.total_duration_seconds:.1f}s")


def run_interactive(pipeline: JobApplicationPipeline) -> None:
    print("=== Job Application Helper (Interactive Menu) ===")

    while True:
        print("\nPilih menu:")
        print("1) Masukkan URL lowongan baru")
        print("2) Bertanya tentang lowongan yang sudah lewat")
        print("3) Regenerate ulang analisis dan dokumen")
        print("4) Apply semi-auto ke JobStreet")
        print("5) Keluar")

        choice = input("Masukkan pilihan (1/2/3/4/5): ").strip()

        if choice == "1":
            url = _prompt_non_empty("URL lowongan: ")
            try:
                result = pipeline.run_application(url, progress_callback=print)
                _print_run_result(result, language="id")
            except AIError as exc:
                print(f"AI request failed: {exc}")
                print("Tip: cek API key, model, provider order, dan timeout di config.")
        elif choice == "2":
            raw_id = _prompt_non_empty("Application ID: ")
            if not raw_id.isdigit():
                print("Application ID harus berupa angka.")
                continue

            question = _prompt_non_empty("Pertanyaan: ")
            try:
                answer = pipeline.ask(int(raw_id), question)
                print("\nJawaban:")
                print(answer)
            except AIError as exc:
                print(f"AI request failed: {exc}")
                print("Tip: cek API key, model, provider order, dan timeout di config.")
        elif choice == "3":
            raw_id = _prompt_non_empty("Application ID yang mau diregenerate: ")
            if not raw_id.isdigit():
                print("Application ID harus berupa angka.")
                continue

            try:
                result = pipeline.regenerate_application(int(raw_id), progress_callback=print)
                _print_run_result(result, language="id")
            except ValueError as exc:
                print(str(exc))
            except AIError as exc:
                print(f"AI request failed: {exc}")
                print("Tip: cek API key, model, provider order, dan timeout di config.")
        elif choice == "4":
            raw_id = _prompt_non_empty("Application ID yang mau di-apply ke JobStreet: ")
            if not raw_id.isdigit():
                print("Application ID harus berupa angka.")
                continue
            try:
                result = pipeline.apply_to_jobstreet(int(raw_id), progress_callback=print)
                print(f"Status apply: {result.apply_status}")
                print(f"Portal: {result.portal}")
                if result.review_url:
                    print(f"Review URL: {result.review_url}")
                if result.screenshot_path:
                    print(f"Screenshot: {result.screenshot_path}")
                if result.audit_markdown_path:
                    print(f"Audit trail: {result.audit_markdown_path}")
                print(result.message)
                if result.pending_questions:
                    print("Pertanyaan yang masih pending:")
                    for question in result.pending_questions:
                        print(f"- {question}")
            except ValueError as exc:
                print(str(exc))
        elif choice == "5":
            print("Sampai jumpa!")
            break
        else:
            print("Pilihan tidak valid. Silakan pilih 1, 2, 3, 4, atau 5.")


def main() -> None:
    if len(sys.argv) == 1:
        settings = load_settings("config.json")
        pipeline = JobApplicationPipeline(settings)
        run_interactive(pipeline)
        return

    args = build_parser().parse_args()
    settings = load_settings(args.config)
    pipeline = JobApplicationPipeline(settings)

    try:
        if args.command == "run":
            result = pipeline.run_application(args.url, progress_callback=print)
            _print_run_result(result, language="en")
        elif args.command == "regenerate":
            result = pipeline.regenerate_application(args.application_id, progress_callback=print)
            _print_run_result(result, language="en")
        elif args.command == "ask":
            answer = pipeline.ask(args.application_id, args.question)
            print(answer)
        elif args.command == "apply":
            result = pipeline.apply_to_jobstreet(args.application_id, progress_callback=print)
            print(f"Apply status: {result.apply_status}")
            if result.review_url:
                print(f"Review URL: {result.review_url}")
            if result.screenshot_path:
                print(f"Screenshot: {result.screenshot_path}")
            if result.audit_markdown_path:
                print(f"Audit trail: {result.audit_markdown_path}")
            print(result.message)
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1)
    except AIError as exc:
        print(f"AI request failed: {exc}")
        print("Tip: check API keys, model names, provider order, and network timeouts in config.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
