from __future__ import annotations

import argparse
import json
from pathlib import Path

from coach_garmin.coach_chat import run_coach_chat
from coach_garmin.config import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT
from coach_garmin.config import (
    DEFAULT_ENV_FILE,
    DEFAULT_GARMIN_EMAIL_ENV,
    DEFAULT_GARMIN_LOOKBACK_DAYS,
    DEFAULT_GARMIN_PASSWORD_ENV,
    DEFAULT_GARMIN_TOKENSTORE,
)
from coach_garmin.garmin_auth import initialize_garmin_auth, run_authenticated_sync
from coach_garmin.manual_import import run_import_export
from coach_garmin.pwa_service import run_pwa_server
from coach_garmin.storage import default_coverage_report_path, default_report_path
from coach_garmin.sync_state import load_sync_summary


def _print_payload(payload: dict[str, object], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def cmd_sync_import_export(args: argparse.Namespace) -> int:
    payload = run_import_export(
        source=Path(args.source),
        data_dir=Path(args.data_dir),
        run_label=args.run_label,
    )
    _print_payload(payload, args.format)
    return 0


def cmd_sync_garmin_auth(args: argparse.Namespace) -> int:
    payload = run_authenticated_sync(
        data_dir=Path(args.data_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        run_label=args.run_label,
        tokenstore_path=Path(args.tokenstore),
        env_file=Path(args.env_file),
        email_env=args.email_env,
        password_env=args.password_env,
    )
    _print_payload(payload, args.format)
    return 0


def cmd_auth_init(args: argparse.Namespace) -> int:
    payload = initialize_garmin_auth(
        tokenstore_path=Path(args.tokenstore),
        env_file=Path(args.env_file),
        email_env=args.email_env,
        password_env=args.password_env,
    )
    _print_payload(payload, args.format)
    return 0


def cmd_report_latest(args: argparse.Namespace) -> int:
    report_path = default_report_path(Path(args.data_dir))
    if not report_path.exists():
        raise SystemExit(f"No report found at {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    _print_payload(payload, args.format)
    return 0


def cmd_sync_refresh_export(args: argparse.Namespace) -> int:
    payload = run_import_export(
        source=Path(args.source),
        data_dir=Path(args.data_dir),
        run_label=args.run_label,
    )
    _print_payload(payload, args.format)
    return 0


def cmd_report_coverage(args: argparse.Namespace) -> int:
    report_path = default_coverage_report_path(Path(args.data_dir))
    if not report_path.exists():
        raise SystemExit(f"No coverage report found at {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    _print_payload(payload, args.format)
    return 0


def cmd_report_sync_state(args: argparse.Namespace) -> int:
    payload = load_sync_summary(Path(args.data_dir))
    _print_payload(payload, args.format)
    return 0


def cmd_web_serve(args: argparse.Namespace) -> int:
    run_pwa_server(
        web_root=Path(args.web_root),
        default_data_dir=Path(args.data_dir),
        host=args.host,
        port=args.port,
    )
    return 0


def cmd_coach_chat(args: argparse.Namespace) -> int:
    payload = run_coach_chat(
        data_dir=Path(args.data_dir),
        goal_text=args.goal,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        output_func=(lambda _: None) if args.format == "json" else print,
    )
    if args.format == "json":
        _print_payload(payload, args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coach Garmin local-first data foundation CLI.")
    parser.set_defaults(func=None)

    subparsers = parser.add_subparsers(dest="command")

    sync_parser = subparsers.add_parser("sync", help="Sync or import Garmin data.")
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")

    auth_parser = subparsers.add_parser("auth", help="Initialize or inspect Garmin authentication.")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command")

    import_parser = sync_subparsers.add_parser(
        "import-export",
        help="Import a local Garmin export directory or file into raw and normalized stores.",
    )
    import_parser.add_argument("--source", required=True)
    import_parser.add_argument("--data-dir", default="data")
    import_parser.add_argument("--run-label", default="manual-import")
    import_parser.add_argument("--format", choices=("text", "json"), default="text")
    import_parser.set_defaults(func=cmd_sync_import_export)

    refresh_parser = sync_subparsers.add_parser(
        "refresh-export",
        help="Refresh a local Garmin export baseline with the latest available source data.",
    )
    refresh_parser.add_argument("--source", required=True)
    refresh_parser.add_argument("--data-dir", default="data")
    refresh_parser.add_argument("--run-label", default="refresh-export")
    refresh_parser.add_argument("--format", choices=("text", "json"), default="text")
    refresh_parser.set_defaults(func=cmd_sync_refresh_export)

    auth_parser = sync_subparsers.add_parser(
        "garmin-auth",
        help="Fetch Garmin Connect data through an authenticated API session and store raw + normalized outputs locally.",
    )
    auth_parser.add_argument("--data-dir", default="data")
    auth_parser.add_argument("--start-date")
    auth_parser.add_argument("--end-date")
    auth_parser.add_argument("--days", type=int, default=DEFAULT_GARMIN_LOOKBACK_DAYS)
    auth_parser.add_argument("--run-label", default="garmin-auth")
    auth_parser.add_argument("--tokenstore", default=str(DEFAULT_GARMIN_TOKENSTORE))
    auth_parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    auth_parser.add_argument("--email-env", default=DEFAULT_GARMIN_EMAIL_ENV)
    auth_parser.add_argument("--password-env", default=DEFAULT_GARMIN_PASSWORD_ENV)
    auth_parser.add_argument("--format", choices=("text", "json"), default="text")
    auth_parser.set_defaults(func=cmd_sync_garmin_auth)

    init_parser = auth_subparsers.add_parser(
        "init",
        help="Initialize or refresh the local Garmin token store without syncing data.",
    )
    init_parser.add_argument("--tokenstore", default=str(DEFAULT_GARMIN_TOKENSTORE))
    init_parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    init_parser.add_argument("--email-env", default=DEFAULT_GARMIN_EMAIL_ENV)
    init_parser.add_argument("--password-env", default=DEFAULT_GARMIN_PASSWORD_ENV)
    init_parser.add_argument("--format", choices=("text", "json"), default="text")
    init_parser.set_defaults(func=cmd_auth_init)

    report_parser = subparsers.add_parser("report", help="Read derived reports.")
    report_subparsers = report_parser.add_subparsers(dest="report_command")
    coach_parser = subparsers.add_parser("coach", help="Run local-first coaching workflows.")
    coach_subparsers = coach_parser.add_subparsers(dest="coach_command")
    web_parser = subparsers.add_parser("web", help="Run the local-first PWA shell.")
    web_subparsers = web_parser.add_subparsers(dest="web_command")

    latest_parser = report_subparsers.add_parser("latest", help="Print the latest deterministic metrics report.")
    latest_parser.add_argument("--data-dir", default="data")
    latest_parser.add_argument("--format", choices=("text", "json"), default="text")
    latest_parser.set_defaults(func=cmd_report_latest)

    coverage_parser = report_subparsers.add_parser(
        "coverage",
        help="Print the latest feature coverage report.",
    )
    coverage_parser.add_argument("--data-dir", default="data")
    coverage_parser.add_argument("--format", choices=("text", "json"), default="text")
    coverage_parser.set_defaults(func=cmd_report_coverage)

    sync_state_parser = report_subparsers.add_parser(
        "sync-state",
        help="Print the latest local sync state ledger.",
    )
    sync_state_parser.add_argument("--data-dir", default="data")
    sync_state_parser.add_argument("--format", choices=("text", "json"), default="text")
    sync_state_parser.set_defaults(func=cmd_report_sync_state)

    coach_chat_parser = coach_subparsers.add_parser(
        "chat",
        help="Start a local-first coaching chat backed by Ollama or Gemini and local Garmin data.",
    )
    coach_chat_parser.add_argument("--data-dir", default="data")
    coach_chat_parser.add_argument("--goal")
    coach_chat_parser.add_argument("--provider", choices=("ollama", "gemini"), default="ollama")
    coach_chat_parser.add_argument("--model")
    coach_chat_parser.add_argument("--base-url")
    coach_chat_parser.add_argument("--api-key")
    coach_chat_parser.add_argument("--format", choices=("text", "json"), default="text")
    coach_chat_parser.set_defaults(func=cmd_coach_chat)

    web_serve_parser = web_subparsers.add_parser("serve", help="Serve the local-first PWA app.")
    web_serve_parser.add_argument("--web-root", default="web")
    web_serve_parser.add_argument("--data-dir", default="data")
    web_serve_parser.add_argument("--host", default=DEFAULT_WEB_HOST)
    web_serve_parser.add_argument("--port", type=int, default=DEFAULT_WEB_PORT)
    web_serve_parser.set_defaults(func=cmd_web_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return int(args.func(args))
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
