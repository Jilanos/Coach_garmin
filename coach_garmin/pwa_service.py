from __future__ import annotations

import json
import mimetypes
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import duckdb

from coach_garmin.coach_chat import CoachChatSession
from coach_garmin.coach_llm import CoachLLMConfig, build_coach_client
from coach_garmin.coach_tools import LocalCoachToolkit
from coach_garmin.config import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT
from coach_garmin.manual_import import run_import_export
from coach_garmin.sync_state import load_sync_summary


@dataclass(slots=True)
class CoachPwaConfig:
    web_root: Path
    default_data_dir: Path
    host: str = DEFAULT_WEB_HOST
    port: int = DEFAULT_WEB_PORT


def build_workspace_status(data_dir: Path, provider: str = "ollama", model: str | None = None, base_url: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    toolkit = LocalCoachToolkit(data_dir=data_dir)
    metrics = toolkit.metrics()
    history_7d = toolkit.history(days=7)
    history_21d = toolkit.history(days=21)
    history_28d = toolkit.history(days=28)
    goal_profile = toolkit.goals().get("goal_profile", {})
    if not isinstance(goal_profile, dict):
        goal_profile = {}
    analysis = toolkit.analysis(goal_profile or {"target_event": "running"})
    provider_status = _probe_provider(provider=provider, model=model, base_url=base_url, api_key=api_key)
    latest_metrics = metrics.get("latest_metrics", {}) if isinstance(metrics.get("latest_metrics", {}), dict) else {}
    sync_state = load_sync_summary(data_dir)
    latest_sync_run = sync_state.get("latest_run")
    trend_series = _build_trend_series(data_dir)
    heart_rate_zone_rows = metrics.get("heart_rate_zones", {}) if isinstance(metrics.get("heart_rate_zones", {}), dict) else {}
    max_hr_estimate = heart_rate_zone_rows.get("max_hr")
    pace_context = analysis.get("inferred_paces", {}) if isinstance(analysis.get("inferred_paces", {}), dict) else {}
    dashboard_metrics = {
        "load_7d": latest_metrics.get("load_7d"),
        "load_28d": latest_metrics.get("load_28d"),
        "load_ratio_7_28": latest_metrics.get("load_ratio_7_28"),
        "progression_delta": latest_metrics.get("progression_delta"),
        "sleep_hours_7d": latest_metrics.get("sleep_hours_7d"),
        "hrv_7d": latest_metrics.get("hrv_7d"),
        "resting_hr_7d": latest_metrics.get("resting_hr_7d"),
        "fatigue_flag": latest_metrics.get("fatigue_flag"),
        "overreaching_flag": latest_metrics.get("overreaching_flag"),
        "training_phase": analysis.get("training_phase"),
        "recent_running_days": history_7d.get("recent_running_days"),
        "recent_activity_count_7d": history_7d.get("recent_activity_count"),
        "recent_activity_count_28d": history_28d.get("recent_activity_count"),
        "total_distance_km_7d": history_7d.get("total_distance_km"),
        "total_distance_km_21d": history_21d.get("total_distance_km"),
        "long_run_km": history_21d.get("long_run_km"),
        "weekly_volume_km": history_7d.get("total_distance_km"),
        "weekly_running_days": history_7d.get("recent_running_days"),
        "average_pace_21d": (analysis.get("windows") or {}).get("21d", {}).get("average_pace_min_per_km"),
        "threshold_pace_min_per_km": pace_context.get("threshold_pace_min_per_km"),
        "max_hr_estimate": max_hr_estimate,
    }
    import_state = {
        "available": bool(metrics.get("db_available", False)),
        "state": (
            "imported"
            if latest_sync_run
            else ("indexed" if metrics.get("db_available", False) else "empty")
        ),
        "latest_activity_day": history_7d.get("latest_activity_day"),
        "recent_activity_count": history_7d.get("recent_activity_count"),
        "latest_run": latest_sync_run,
        "sync_state": sync_state,
        "new_artifact_count": sync_state.get("new_artifact_count"),
        "reused_artifact_count": sync_state.get("reused_artifact_count"),
        "pending_count": sync_state.get("pending_count"),
    }
    return {
        "data_dir": str(data_dir),
        "workspace": {
            "path": str(data_dir),
            "exists": data_dir.exists(),
            "db_path": str(data_dir / "normalized" / "coach_garmin.duckdb"),
        },
        "db_available": metrics.get("db_available", False),
        "latest_day": metrics.get("latest_day"),
        "coverage_ratio": (((metrics.get("coverage") or {}).get("coach") or {}).get("coverage_ratio")),
        "import_status": import_state,
        "analysis": {
            "available": analysis.get("available", False),
            "summary": analysis.get("analysis_summary"),
            "benchmark": analysis.get("recommended_benchmark"),
            "training_phase": analysis.get("training_phase"),
            "signals": analysis.get("signal_highlights", []),
            "metrics": dashboard_metrics,
            "trend": trend_series,
        },
        "provider": provider_status,
        "health": {
            "workspace_exists": data_dir.exists(),
            "report_path": metrics.get("report_path"),
            "coverage_path": metrics.get("coverage_report_path"),
            "latest_sync_run": latest_sync_run,
            "sync_state": sync_state,
        },
    }


def prepare_coach_questions(
    *,
    data_dir: Path,
    goal_text: str,
    provider: str = "ollama",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    toolkit = LocalCoachToolkit(data_dir=data_dir)
    history_context = toolkit.history()
    goal_profile = CoachChatSession._build_goal_profile(goal_text)
    existing_goal = toolkit.goals().get("goal_profile", {})
    if isinstance(existing_goal, dict):
        goal_profile = CoachChatSession._merge_existing_goal_profile(existing_goal, goal_profile)
    questions = []
    for key, question, parser in CoachChatSession._clarification_questions(goal_profile, history_context):
        questions.append({"key": key, "question": question, "parser": getattr(parser, "__name__", "callable")})
    return {
        "goal_profile": goal_profile,
        "questions": questions,
        "analysis": toolkit.analysis(goal_profile),
        "dashboard": build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url, api_key=api_key),
    }


def generate_coach_plan(
    *,
    data_dir: Path,
    goal_text: str,
    answers: dict[str, Any] | None = None,
    provider: str = "ollama",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    toolkit = LocalCoachToolkit(data_dir=data_dir)
    answers = answers or {}
    history_context = toolkit.history()
    existing_goal = toolkit.goals().get("goal_profile", {})
    goal_profile = CoachChatSession._build_goal_profile(goal_text)
    if isinstance(existing_goal, dict):
        goal_profile = CoachChatSession._merge_existing_goal_profile(existing_goal, goal_profile)
    pending_questions = []
    for key, question, parser in CoachChatSession._clarification_questions(goal_profile, history_context):
        raw_answer = answers.get(key)
        if raw_answer in (None, ""):
            pending_questions.append({"key": key, "question": question})
            continue
        goal_profile[key] = parser(str(raw_answer).strip())

    if pending_questions:
        return {
            "needs_clarification": True,
            "goal_profile": goal_profile,
            "questions": pending_questions,
            "analysis": toolkit.analysis(goal_profile),
            "dashboard": build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url, api_key=api_key),
        }

    goal_profile["goal_text"] = goal_text
    goal_profile["target_event"] = CoachChatSession._primary_event(goal_profile)
    from datetime import UTC, datetime

    goal_profile["updated_at"] = datetime.now(UTC).isoformat()
    toolkit.goals(goal_profile)

    metrics_context = toolkit.metrics()
    analysis_context = toolkit.analysis(goal_profile)
    plan_skeleton = CoachChatSession._build_plan_skeleton(goal_profile, metrics_context, history_context, analysis_context)
    prompt_bundle = CoachChatSession._build_prompt_bundle(
        goal_profile=goal_profile,
        metrics_context=metrics_context,
        history_context=history_context,
        analysis_context=analysis_context,
        plan_skeleton=plan_skeleton,
    )
    llm_client = build_coach_client(CoachLLMConfig(provider=provider, model=model, base_url=base_url, api_key=api_key))
    plan_response = llm_client.generate_weekly_plan(prompt_bundle)
    normalized_plan = CoachChatSession._normalize_weekly_plan(plan_response.get("weekly_plan", []), plan_skeleton)
    normalized_plan = CoachChatSession._enrich_weekly_plan(normalized_plan, plan_skeleton)
    saved_plan_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "goal_profile": goal_profile,
        "metrics_snapshot": metrics_context,
        "history_snapshot": history_context,
        "analysis_snapshot": analysis_context,
        "coverage_snapshot": metrics_context.get("coverage", {}),
        "coach_summary": CoachChatSession._choose_coach_summary(
            plan_response.get("coach_summary", ""),
            analysis_context,
        ),
        "signals_used": CoachChatSession._normalize_signals_used(
            plan_response.get("signals_used", []),
            metrics_context,
            history_context,
            analysis_context,
        ),
        "questions_asked": [],
        "weekly_plan": normalized_plan,
    }
    plan_state = toolkit.plan(saved_plan_payload)
    return {
        "needs_clarification": False,
        "goal_profile": goal_profile,
        "coach_summary": saved_plan_payload["coach_summary"],
        "signals_used": saved_plan_payload["signals_used"],
        "weekly_plan": normalized_plan,
        "plan_path": plan_state["path"],
        "analysis": analysis_context,
        "dashboard": build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url, api_key=api_key),
    }


def import_garmin_export(*, source_path: str, data_dir: Path, run_label: str | None = None) -> dict[str, Any]:
    return run_import_export(Path(source_path), data_dir, run_label=run_label or "pwa-import")


def run_pwa_server(*, web_root: Path, default_data_dir: Path, host: str = DEFAULT_WEB_HOST, port: int = DEFAULT_WEB_PORT) -> None:
    config = CoachPwaConfig(web_root=web_root, default_data_dir=default_data_dir, host=host, port=port)
    handler = _build_handler(config)
    httpd = ThreadingHTTPServer((config.host, config.port), handler)
    print(f"Coach Garmin PWA server running at http://{config.host}:{config.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def _probe_provider(*, provider: str, model: str | None, base_url: str | None, api_key: str | None) -> dict[str, Any]:
    try:
        client = build_coach_client(CoachLLMConfig(provider=provider, model=model, base_url=base_url, api_key=api_key))
        client.ensure_ready()
        return {"available": True, "provider": provider, "model": getattr(client, "model", None), "status": "ready"}
    except Exception as exc:  # pragma: no cover - surfaced in UI, not control flow
        return {"available": False, "provider": provider, "model": model, "status": "unavailable", "error": str(exc)}


def _build_static_response(path: Path) -> tuple[bytes, str]:
    content_type, _ = mimetypes.guess_type(str(path))
    return path.read_bytes(), content_type or "application/octet-stream"


def _load_latest_sync_run(data_dir: Path) -> dict[str, Any] | None:
    runs_dir = data_dir / "runs"
    if not runs_dir.exists():
        return None
    manifests = sorted(runs_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for manifest_path in manifests:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        return {
            "manifest_path": str(manifest_path),
            "run_id": payload.get("run_id"),
            "run_label": payload.get("run_label"),
            "source_path": payload.get("source_path"),
            "finished_at": payload.get("finished_at"),
            "artifact_count": payload.get("artifact_count"),
            "dataset_count": payload.get("dataset_count"),
            "total_records": payload.get("total_records"),
        }
    return None


def _build_trend_series(data_dir: Path) -> dict[str, Any]:
    db_path = data_dir / "normalized" / "coach_garmin.duckdb"
    if not db_path.exists():
        return {"daily_volume": [], "pace_hr_sessions": []}

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        latest_day_row = con.execute("SELECT max(activity_date) FROM activities WHERE activity_date IS NOT NULL").fetchone()
        latest_day = latest_day_row[0] if latest_day_row else None
        if latest_day is None:
            return {"daily_volume": [], "pace_hr_sessions": []}

        latest_date = _coerce_date(latest_day)
        window_start = latest_date - timedelta(days=13)
        volume_rows = con.execute(
            """
            SELECT activity_date, SUM(distance_meters), SUM(duration_seconds), SUM(training_load), AVG(average_hr)
            FROM activities
            WHERE activity_date >= ?
            GROUP BY activity_date
            ORDER BY activity_date
            """,
            [window_start.isoformat()],
        ).fetchall()
        pace_rows = con.execute(
            """
            SELECT activity_date, activity_type, duration_seconds, distance_meters, average_hr
            FROM activities
            WHERE activity_date >= ?
            ORDER BY activity_date DESC, started_at DESC
            LIMIT 12
            """,
            [window_start.isoformat()],
        ).fetchall()
    finally:
        con.close()

    running_rows = [row for row in pace_rows if _is_running_type(row[1])]
    summary_rows = running_rows if running_rows else pace_rows
    daily_volume = [
        {
            "date": str(row[0]),
            "distance_km": round((row[1] or 0.0) / 1000.0, 2),
            "duration_minutes": round((row[2] or 0.0) / 60.0, 1),
            "training_load": round(float(row[3] or 0.0), 2),
            "average_hr": round(float(row[4]), 1) if row[4] is not None else None,
        }
        for row in volume_rows
    ]
    pace_hr_sessions = [
        {
            "date": str(row[0]),
            "distance_km": round((row[3] or 0.0) / 1000.0, 2),
            "pace_min_per_km": _pace_min_per_km((row[2] or 0.0) / 60.0, (row[3] or 0.0) / 1000.0),
            "average_hr": round(float(row[4]), 1) if row[4] is not None else None,
        }
        for row in reversed(summary_rows[:8])
        if (row[2] or 0.0) > 0 and (row[3] or 0.0) > 0
    ]
    return {"daily_volume": daily_volume, "pace_hr_sessions": pace_hr_sessions}


def _build_handler(config: CoachPwaConfig):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, payload: str, content_type: str = "text/plain; charset=utf-8", status: int = HTTPStatus.OK) -> None:
            body = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/status":
                params = parse_qs(parsed.query)
                data_dir = Path(params.get("data_dir", [str(config.default_data_dir)])[0])
                provider = params.get("provider", ["ollama"])[0]
                model = params.get("model", [None])[0]
                base_url = params.get("base_url", [None])[0]
                self._send_json(build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url))
                return
            file_path = _resolve_static_path(config.web_root, parsed.path)
            if file_path is None:
                file_path = config.web_root / "index.html"
            if not file_path.exists() or not file_path.is_file():
                self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
                return
            body, content_type = _build_static_response(file_path)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            payload = self._read_json()
            if parsed.path == "/api/import":
                source_path = str(payload.get("source_path") or "").strip()
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                run_label = str(payload.get("run_label") or "pwa-import")
                if not source_path:
                    self._send_json({"error": "source_path is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                try:
                    result = import_garmin_export(source_path=source_path, data_dir=data_dir, run_label=run_label)
                except Exception as exc:  # pragma: no cover - surfaced in UI
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._send_json(result)
                return
            if parsed.path == "/api/coach/prepare":
                goal_text = str(payload.get("goal_text") or "").strip()
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                if not goal_text:
                    self._send_json({"error": "goal_text is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                result = prepare_coach_questions(
                    data_dir=data_dir,
                    goal_text=goal_text,
                    provider=str(payload.get("provider") or "ollama"),
                    model=payload.get("model"),
                    base_url=payload.get("base_url"),
                    api_key=payload.get("api_key"),
                )
                self._send_json(result)
                return
            if parsed.path == "/api/coach/plan":
                goal_text = str(payload.get("goal_text") or "").strip()
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                if not goal_text:
                    self._send_json({"error": "goal_text is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                result = generate_coach_plan(
                    data_dir=data_dir,
                    goal_text=goal_text,
                    answers=dict(payload.get("answers") or {}),
                    provider=str(payload.get("provider") or "ollama"),
                    model=payload.get("model"),
                    base_url=payload.get("base_url"),
                    api_key=payload.get("api_key"),
                )
                self._send_json(result)
                return
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return Handler


def _is_running_type(value: Any) -> bool:
    return str(value or "").lower() in {"running", "trail_running", "walking", "hiking"}


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _pace_min_per_km(duration_minutes: float, distance_km: float) -> float | None:
    if duration_minutes <= 0 or distance_km <= 0:
        return None
    return round(duration_minutes / distance_km, 2)


def _resolve_static_path(web_root: Path, request_path: str) -> Path | None:
    normalized = request_path.lstrip("/")
    if not normalized:
        return web_root / "index.html"
    candidate = (web_root / normalized).resolve()
    try:
        candidate.relative_to(web_root.resolve())
    except ValueError:
        return None
    return candidate
