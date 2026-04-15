from __future__ import annotations

import argparse
import json
import sys
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
from coach_garmin.garmin_auth import describe_auth_environment, initialize_garmin_auth, run_authenticated_sync, test_garmin_auth
from coach_garmin.manual_import import run_import_export
from coach_garmin.pwa_service import run_pwa_server
from coach_garmin.storage import default_boot_trace_path, default_coverage_report_path, default_report_path
from coach_garmin.sync_state import load_sync_summary
from coach_garmin.text_encoding import repair_text_tree


def _print_payload(payload: dict[str, object], fmt: str) -> None:
    payload = repair_text_tree(payload)
    if fmt == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
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
    payload = repair_text_tree(json.loads(report_path.read_text(encoding="utf-8")))
    _print_payload(payload, args.format)
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    payload = describe_auth_environment(
        tokenstore_path=Path(args.tokenstore),
        env_file=Path(args.env_file),
        email_env=args.email_env,
        password_env=args.password_env,
    )
    _print_payload(payload, args.format)
    return 0


def cmd_auth_test(args: argparse.Namespace) -> int:
    payload = test_garmin_auth(
        data_dir=Path(args.data_dir),
        tokenstore_path=Path(args.tokenstore),
        env_file=Path(args.env_file),
        email_env=args.email_env,
        password_env=args.password_env,
    )
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
    payload = repair_text_tree(json.loads(report_path.read_text(encoding="utf-8")))
    _print_payload(payload, args.format)
    return 0


def cmd_report_sync_state(args: argparse.Namespace) -> int:
    payload = repair_text_tree(load_sync_summary(Path(args.data_dir)))
    _print_payload(payload, args.format)
    return 0


def cmd_report_boot_trace(args: argparse.Namespace) -> int:
    trace_path = default_boot_trace_path(Path(args.data_dir))
    if not trace_path.exists():
        raise SystemExit(f"No boot trace found at {trace_path}")
    if args.format == "json":
        lines = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            lines.append(repair_text_tree(json.loads(line)))
        _print_payload({"path": str(trace_path), "events": lines}, args.format)
        return 0
    print(f"path: {trace_path}")
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            if line.lstrip().startswith("{"):
                print(json.dumps(repair_text_tree(json.loads(line)), ensure_ascii=False, sort_keys=True))
            else:
                print(line)
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

    status_parser = auth_subparsers.add_parser(
        "status",
        help="Inspect the local Garmin authentication environment without logging in.",
    )
    status_parser.add_argument("--tokenstore", default=str(DEFAULT_GARMIN_TOKENSTORE))
    status_parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    status_parser.add_argument("--email-env", default=DEFAULT_GARMIN_EMAIL_ENV)
    status_parser.add_argument("--password-env", default=DEFAULT_GARMIN_PASSWORD_ENV)
    status_parser.add_argument("--format", choices=("text", "json"), default="text")
    status_parser.set_defaults(func=cmd_auth_status)

    test_parser = auth_subparsers.add_parser(
        "test",
        help="Attempt a Garmin authentication and write debug details locally.",
    )
    test_parser.add_argument("--data-dir", default="data")
    test_parser.add_argument("--tokenstore", default=str(DEFAULT_GARMIN_TOKENSTORE))
    test_parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    test_parser.add_argument("--email-env", default=DEFAULT_GARMIN_EMAIL_ENV)
    test_parser.add_argument("--password-env", default=DEFAULT_GARMIN_PASSWORD_ENV)
    test_parser.add_argument("--format", choices=("text", "json"), default="text")
    test_parser.set_defaults(func=cmd_auth_test)

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

    boot_trace_parser = report_subparsers.add_parser(
        "boot-trace",
        help="Print the latest PWA boot trace log.",
    )
    boot_trace_parser.add_argument("--data-dir", default="data")
    boot_trace_parser.add_argument("--format", choices=("text", "json"), default="text")
    boot_trace_parser.set_defaults(func=cmd_report_boot_trace)

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
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        return int(args.func(args))
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
