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

    ask_cmd = sub.add_parser("ask", help="Ask question about a stored application")
    ask_cmd.add_argument("application_id", type=int)
    ask_cmd.add_argument("question")

    return parser


def _prompt_non_empty(message: str) -> str:
    while True:
        value = input(message).strip()
        if value:
            return value
        print("Input tidak boleh kosong.")


def run_interactive(pipeline: JobApplicationPipeline) -> None:
    print("=== Job Application Helper (Interactive Menu) ===")

    while True:
        print("\nPilih menu:")
        print("1) Masukkan URL lowongan baru")
        print("2) Bertanya tentang lowongan yang sudah lewat")
        print("3) Keluar")

        choice = input("Masukkan pilihan (1/2/3): ").strip()

        if choice == "1":
            url = _prompt_non_empty("URL lowongan: ")
            try:
                app_id = pipeline.run_application(url)
                print(f"Berhasil. Application tersimpan dengan id={app_id}")
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
            print("Sampai jumpa!")
            break
        else:
            print("Pilihan tidak valid. Silakan pilih 1, 2, atau 3.")


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
            app_id = pipeline.run_application(args.url)
            print(f"Application stored with id={app_id}")
        elif args.command == "ask":
            answer = pipeline.ask(args.application_id, args.question)
            print(answer)
    except AIError as exc:
        print(f"AI request failed: {exc}")
        print("Tip: check API keys, model names, provider order, and network timeouts in config.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
