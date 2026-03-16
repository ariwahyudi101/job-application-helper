from __future__ import annotations

import argparse

from job_app_helper.app import JobApplicationPipeline
from job_app_helper.config import load_settings


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


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings(args.config)
    pipeline = JobApplicationPipeline(settings)

    if args.command == "run":
        app_id = pipeline.run_application(args.url)
        print(f"Application stored with id={app_id}")
    elif args.command == "ask":
        answer = pipeline.ask(args.application_id, args.question)
        print(answer)


if __name__ == "__main__":
    main()
