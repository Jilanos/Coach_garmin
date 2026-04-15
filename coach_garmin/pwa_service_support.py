from __future__ import annotations

import json
import mimetypes
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import duckdb

from coach_garmin.coach_chat import CoachChatSession
from coach_garmin.coach_llm import CoachLLMConfig, build_coach_client
from coach_garmin.coach_tools import LocalCoachToolkit
from coach_garmin.config import DEFAULT_GARMIN_TOKENSTORE, DEFAULT_WEB_HOST, DEFAULT_WEB_PORT
from coach_garmin.analytics import (
    _build_pace_hr_curve,
    _build_pace_hr_curve_diagnostics,
    _build_cadence_daily_series,
    _is_running_type,
    rebuild_analytics,
)
from coach_garmin.garmin_auth import describe_auth_environment, log_sync_error, test_garmin_auth
from coach_garmin.manual_import import run_import_export
from coach_garmin.garmin_auth import run_authenticated_sync
from coach_garmin.storage import default_boot_trace_path
from coach_garmin.sync_state import load_sync_summary
from coach_garmin.text_encoding import repair_mojibake_text, repair_text_tree


@dataclass(slots=True)
class CoachPwaConfig:
    web_root: Path
    default_data_dir: Path
    host: str = DEFAULT_WEB_HOST
    port: int = DEFAULT_WEB_PORT


def _chart_series_ready(series: Any, *, name: str, min_points: int = 1, empty_reason: str = '') -> dict[str, Any]:
    points = len(series) if isinstance(series, list) else 0
    if points >= min_points:
        return {"state": "ready", "label": "Prête", "reason": "", "details": [], "points": points}
    if points > 0:
        reason = f"{name}: {points} point(s) exploitable(s), minimum attendu {min_points}."
        return {"state": "partial_data", "label": "Partielle", "reason": reason, "details": [reason], "points": points}
    reason = empty_reason or f"{name}: aucune donnée exploitable."
    return {"state": "unavailable", "label": "Indisponible", "reason": reason, "details": [reason], "points": 0}


def _pace_curve_ready(curve_debug: Any, curve: Any) -> dict[str, Any]:
    curve_debug = curve_debug if isinstance(curve_debug, dict) else {}
    curve = curve if isinstance(curve, list) else []
    ready = curve_debug.get("ready") is True and len(curve) >= 3
    input_points = int(curve_debug.get("input_points") or 0)
    valid_points = int(curve_debug.get("valid_points") or 0)
    details: list[str] = []
    if isinstance(curve_debug.get("blocking_reasons"), list):
        details.extend([str(item) for item in curve_debug["blocking_reasons"] if item][:5])
    if input_points <= 0 and valid_points <= 0 and not curve:
        details.append("Aucun point running exploitable pour construire la courbe.")
    if valid_points > 0 and len(curve) < 3:
        details.append("Pas encore assez de points stables pour lisser la courbe correctement.")
    if ready:
        return {"state": "ready", "label": "Prête", "reason": "Courbe pace / FC exploitable.", "details": [], "points": len(curve), "input_points": input_points, "valid_points": valid_points}
    state = "recalculation_required" if (input_points > 0 or valid_points > 0 or details) else "unavailable"
    label = "Recalcul nécessaire" if state == "recalculation_required" else "Indisponible"
    reason = details[0] if details else "Courbe pace / FC indisponible."
    return {"state": state, "label": label, "reason": reason, "details": details or [reason], "points": len(curve), "input_points": input_points, "valid_points": valid_points}


def _build_dashboard_readiness(*, metrics: dict[str, Any], analysis: dict[str, Any], import_state: dict[str, Any], trend_series: dict[str, Any]) -> dict[str, Any]:
    chart_states = {
        "volume": _chart_series_ready(trend_series.get("daily_volume", []), name="Volume running"),
        "bike": _chart_series_ready(trend_series.get("daily_bike_volume", []), name="Volume vélo"),
        "load_ratio": _chart_series_ready(trend_series.get("daily_load_ratio", []), name="Charge relative", empty_reason="Le ratio 7j/28j nécessite des séries de charge locales."),
        "sleep": _chart_series_ready(trend_series.get("daily_sleep", []), name="Sommeil", empty_reason="Le sommeil est calculé à partir des signaux wellness locaux."),
        "resting_hr": _chart_series_ready(trend_series.get("daily_resting_hr", []), name="FC repos", empty_reason="La FC repos demande des mesures wellness exploitables."),
        "hrv": _chart_series_ready(trend_series.get("daily_hrv", []), name="HRV", empty_reason="La HRV dépend des mesures wellness locales."),
        "cadence": _chart_series_ready(trend_series.get("cadence_daily", []), name="Cadence", empty_reason="La cadence doit remonter depuis les activités running."),
        "running_pace": _chart_series_ready(trend_series.get("daily_running_pace", []), name="Allure running", empty_reason="Les activités running sont nécessaires pour reconstruire l’allure."),
        "running_hr": _chart_series_ready(trend_series.get("daily_running_hr", []), name="FC running", empty_reason="Les activités running sont nécessaires pour reconstruire la FC."),
        "pace_curve": _pace_curve_ready(trend_series.get("pace_hr_curve_debug", {}), trend_series.get("pace_hr_curve", [])),
    }
    has_db = bool(metrics.get("db_available"))
    has_import = bool(import_state.get("available"))
    any_points = any(int(state.get("points") or 0) > 0 for state in chart_states.values())
    required_ready = all(chart_states[key]["state"] == "ready" for key in ("volume", "load_ratio", "sleep", "resting_hr", "hrv", "cadence", "running_pace", "running_hr"))
    pace_ready = chart_states["pace_curve"]["state"] == "ready"
    details: list[str] = []
    if not has_db or not has_import:
        state = "unavailable"
        label = "Données indisponibles"
        details.append("Le workspace local n’est pas encore complètement chargé.")
    elif required_ready and pace_ready:
        state = "ready"
        label = "Analyse prête"
        details.append("Les séries clés sont présentes et la courbe pace / FC est exploitable.")
    elif chart_states["pace_curve"]["state"] == "recalculation_required" or (has_db and any_points and (not pace_ready or not required_ready)):
        state = "recalculation_required"
        label = "Recalcul nécessaire"
        pace_reason = chart_states["pace_curve"].get("reason")
        if pace_reason:
            details.append(str(pace_reason))
        if not chart_states["cadence"]["points"]:
            details.append("La cadence ne remonte pas correctement sur la fenêtre active.")
        if not chart_states["running_pace"]["points"] or not chart_states["running_hr"]["points"]:
            details.append("Les séries running utiles à la courbe ne sont pas assez stables.")
    elif any_points:
        state = "partial_data"
        label = "Données partielles"
        details.append("Certaines cartes sont prêtes, d’autres attendent encore des points exploitables.")
    else:
        state = "unavailable"
        label = "Données indisponibles"
        details.append("Aucune série exploitable n’a encore été chargée.")
    return repair_text_tree({
        "state": state,
        "label": label,
        "reason": details[0] if details else "Lecture des données indisponible.",
        "details": details,
        "chart_states": chart_states,
    })


def build_workspace_status(
    data_dir: Path,
    provider: str = "ollama",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    include_provider_probe: bool = False,
    trend_days: int = 90,
) -> dict[str, Any]:
    toolkit = LocalCoachToolkit(data_dir=data_dir)
    metrics = toolkit.metrics()
    history_7d = toolkit.history(days=7)
    history_21d = toolkit.history(days=21)
    history_28d = toolkit.history(days=28)
    goal_profile = toolkit.goals().get("goal_profile", {})
    if not isinstance(goal_profile, dict):
        goal_profile = {}
    analysis = toolkit.analysis(goal_profile or {"target_event": "running"})
    provider_status = (
        _probe_provider(provider=provider, model=model, base_url=base_url, api_key=api_key)
        if include_provider_probe
        else {
            "available": False,
            "provider": provider,
            "model": model,
            "status": "unchecked",
            "note": "provider probe skipped for fast status rendering",
        }
    )
    latest_metrics = metrics.get("latest_metrics", {}) if isinstance(metrics.get("latest_metrics", {}), dict) else {}
    trend_insights = metrics.get("trend_insights", {}) if isinstance(metrics.get("trend_insights", {}), dict) else {}
    sync_state = load_sync_summary(data_dir)
    latest_sync_run = sync_state.get("latest_run")
    trend_series = _build_trend_series(data_dir, days=trend_days) or trend_insights
    cadence_daily = trend_series.get("cadence_daily", []) if isinstance(trend_series, dict) else []
    cadence_daily_values = [
        float(row.get("cadence_spm"))
        for row in cadence_daily
        if isinstance(row, dict) and row.get("cadence_spm") is not None
    ]
    cadence_fallback_7d = round(sum(cadence_daily_values[-7:]) / len(cadence_daily_values[-7:]), 1) if cadence_daily_values[-7:] else None
    cadence_fallback_28d = round(sum(cadence_daily_values[-28:]) / len(cadence_daily_values[-28:]), 1) if cadence_daily_values[-28:] else None
    cadence_fallback_low = round(sorted(cadence_daily_values)[max(0, int(len(cadence_daily_values) * 0.25) - 1)], 1) if cadence_daily_values else None
    cadence_fallback_high = round(sorted(cadence_daily_values)[min(len(cadence_daily_values) - 1, int(len(cadence_daily_values) * 0.75))], 1) if cadence_daily_values else None
    cadence_latest_metric = latest_metrics.get("cadence_7d")
    cadence_metric_suspect = (
        cadence_latest_metric is None
        or (
            cadence_daily_values
            and cadence_latest_metric is not None
            and float(cadence_latest_metric) < 120
            and max(cadence_daily_values) >= 130
        )
    )
    heart_rate_zone_rows = metrics.get("heart_rate_zones", {}) if isinstance(metrics.get("heart_rate_zones", {}), dict) else {}
    max_hr_estimate = heart_rate_zone_rows.get("max_hr")
    pace_context = analysis.get("inferred_paces", {}) if isinstance(analysis.get("inferred_paces", {}), dict) else {}
    dashboard_metrics = {
        "load_7d": latest_metrics.get("load_7d"),
        "load_28d": latest_metrics.get("load_28d"),
        "load_ratio_7_28": latest_metrics.get("load_ratio_7_28"),
        "load_reference_low": latest_metrics.get("load_reference_low"),
        "load_reference_high": latest_metrics.get("load_reference_high"),
        "load_ratio_reference_low": latest_metrics.get("load_ratio_reference_low"),
        "load_ratio_reference_high": latest_metrics.get("load_ratio_reference_high"),
        "progression_delta": latest_metrics.get("progression_delta"),
        "sleep_hours_7d": latest_metrics.get("sleep_hours_7d"),
        "sleep_reference_low": latest_metrics.get("sleep_reference_low"),
        "sleep_reference_high": latest_metrics.get("sleep_reference_high"),
        "hrv_7d": latest_metrics.get("hrv_7d"),
        "hrv_reference_low": latest_metrics.get("hrv_reference_low"),
        "hrv_reference_high": latest_metrics.get("hrv_reference_high"),
        "resting_hr_7d": latest_metrics.get("resting_hr_7d"),
        "resting_hr_reference_low": latest_metrics.get("resting_hr_reference_low"),
        "resting_hr_reference_high": latest_metrics.get("resting_hr_reference_high"),
        "cadence_7d": cadence_fallback_7d if cadence_metric_suspect else latest_metrics.get("cadence_7d"),
        "cadence_28d": cadence_fallback_28d if cadence_metric_suspect else latest_metrics.get("cadence_28d"),
        "cadence_reference_low": cadence_fallback_low if cadence_metric_suspect else latest_metrics.get("cadence_reference_low"),
        "cadence_reference_high": cadence_fallback_high if cadence_metric_suspect else latest_metrics.get("cadence_reference_high"),
        "cadence_target_spm": latest_metrics.get("cadence_target_spm", 170),
        "fatigue_flag": latest_metrics.get("fatigue_flag"),
        "overreaching_flag": latest_metrics.get("overreaching_flag"),
        "training_phase": analysis.get("training_phase"),
        "recent_running_days": history_7d.get("recent_running_days"),
        "recent_activity_count_7d": history_7d.get("recent_activity_count"),
        "recent_bike_activity_count_7d": history_7d.get("recent_bike_activity_count"),
        "recent_activity_count_28d": history_28d.get("recent_activity_count"),
        "total_distance_km_7d": history_7d.get("running_distance_km"),
        "total_distance_km_21d": history_21d.get("running_distance_km"),
        "weekly_volume_km": history_7d.get("running_distance_km"),
        "weekly_bike_volume_km": history_7d.get("bike_distance_km"),
        "weekly_running_days": history_7d.get("recent_running_days"),
        "weekly_bike_days": history_7d.get("recent_bike_days"),
        "average_pace_21d": (analysis.get("windows") or {}).get("21d", {}).get("average_pace_min_per_km"),
        "threshold_pace_min_per_km": pace_context.get("threshold_pace_min_per_km"),
        "running_pace_7d": latest_metrics.get("running_pace_7d"),
        "running_hr_7d": latest_metrics.get("running_hr_7d"),
        "running_pace_reference_low": latest_metrics.get("running_pace_reference_low"),
        "running_pace_reference_high": latest_metrics.get("running_pace_reference_high"),
        "running_hr_reference_low": latest_metrics.get("running_hr_reference_low"),
        "running_hr_reference_high": latest_metrics.get("running_hr_reference_high"),
        "max_hr_estimate": max_hr_estimate,
        "pace_hr_curve_debug": latest_metrics.get("pace_hr_curve_debug"),
        "heart_rate_zone_share": latest_metrics.get("heart_rate_zone_share"),
        "heart_rate_zone_share_running": latest_metrics.get("heart_rate_zone_share_running"),
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
    readiness = _build_dashboard_readiness(metrics=metrics, analysis=analysis, import_state=import_state, trend_series=trend_series)
    return repair_text_tree({
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
            "trend_window_days": trend_days,
            "readiness": readiness,
        },
        "provider": provider_status,
        "health": {
            "workspace_exists": data_dir.exists(),
            "report_path": metrics.get("report_path"),
            "coverage_path": metrics.get("coverage_report_path"),
            "latest_sync_run": latest_sync_run,
            "sync_state": sync_state,
            "readiness": readiness,
        },
    })


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
    return repair_text_tree({
        "goal_profile": goal_profile,
        "questions": questions,
        "analysis": toolkit.analysis(goal_profile),
        "dashboard": build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url, api_key=api_key),
    })


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
        return repair_text_tree({
            "needs_clarification": True,
            "goal_profile": goal_profile,
            "questions": pending_questions,
            "analysis": toolkit.analysis(goal_profile),
            "dashboard": build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url, api_key=api_key),
        })

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
    return repair_text_tree({
        "needs_clarification": False,
        "goal_profile": goal_profile,
        "coach_summary": saved_plan_payload["coach_summary"],
        "signals_used": saved_plan_payload["signals_used"],
        "weekly_plan": normalized_plan,
        "plan_path": plan_state["path"],
        "analysis": analysis_context,
        "dashboard": build_workspace_status(data_dir, provider=provider, model=model, base_url=base_url, api_key=api_key),
    })


def import_garmin_export(*, source_path: str, data_dir: Path, run_label: str | None = None) -> dict[str, Any]:
    return repair_text_tree(run_import_export(Path(source_path), data_dir, run_label=run_label or "pwa-import"))


def sync_garmin_connect(
    *,
    data_dir: Path,
    days: int = 30,
    run_label: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    context = {
        "run_label": run_label or "pwa-garmin-sync",
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
    }
    try:
        result = run_authenticated_sync(
            data_dir=data_dir,
            days=days,
            run_label=run_label or "pwa-garmin-sync",
            start_date=start_date,
            end_date=end_date,
        )
        result["debug_log_path"] = result.get("debug_log_path") or str(Path(__file__).resolve().parent.parent / "logs" / "garmin-sync-debug.jsonl")
        return repair_text_tree(result)
    except Exception as exc:
        log_sync_error(data_dir=data_dir, error=exc, context=context)
        raise RuntimeError(f"{exc} (voir logs/garmin-sync-debug.jsonl)") from exc


def recalculate_workspace(
    *,
    data_dir: Path,
    provider: str = "ollama",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    analytics_summary = rebuild_analytics(data_dir)
    dashboard = build_workspace_status(
        data_dir,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    return repair_text_tree({
        "ok": True,
        "message": "Retraitement local terminé.",
        "analytics": analytics_summary,
        "dashboard": dashboard,
    })


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


def _build_reset_cache_page(next_url: str, version: str) -> str:
    escaped_next = json.dumps(next_url or "/")
    escaped_version = json.dumps(version)
    return repair_mojibake_text(f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <title>Coach Garmin - purge cache</title>
    <style>
      :root {{ color-scheme: dark; }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #0b1020;
        color: #f4f7fb;
        font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      }}
      .card {{
        width: min(720px, calc(100vw - 32px));
        border: 1px solid rgba(138, 180, 255, 0.18);
        border-radius: 24px;
        padding: 28px;
        background: rgba(13, 20, 36, 0.96);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
      }}
      .muted {{ color: rgba(244, 247, 251, 0.72); line-height: 1.5; }}
      .spinner {{
        width: 22px;
        height: 22px;
        border-radius: 50%;
        border: 3px solid rgba(138, 230, 192, 0.25);
        border-top-color: #8ae6c0;
        animation: spin 0.9s linear infinite;
        display: inline-block;
        vertical-align: middle;
        margin-right: 10px;
      }}
      @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
      .mono {{
        font-family: "Cascadia Mono", Consolas, monospace;
        white-space: pre-wrap;
        color: #b9c8db;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 14px;
        margin-top: 18px;
      }}
    </style>
  </head>
  <body>
    <main class="card">
      <h1>Coach Garmin: purge du cache local</h1>
      <p class="muted"><span class="spinner" aria-hidden="true"></span>Je nettoie les caches PWA et les service workers, puis je redirige vers la version {escaped_version}.</p>
      <p class="muted">Si rien ne bouge dans l'UI après ça, on saura que le problème ne vient plus du cache navigateur.</p>
      <div class="mono" id="status">Démarrage de la purge…</div>
    </main>
    <script>
      const nextUrl = {escaped_next};
      const status = document.getElementById('status');
      async function clearCaches() {{
        try {{
          if ('serviceWorker' in navigator) {{
            const registrations = await navigator.serviceWorker.getRegistrations();
            for (const registration of registrations) {{
              try {{ await registration.unregister(); }} catch (error) {{ console.warn(error); }}
            }}
          }}
        }} catch (error) {{
          console.warn(error);
        }}
        try {{
          if ('caches' in window) {{
            const keys = await caches.keys();
            await Promise.all(keys.map((key) => caches.delete(key)));
          }}
        }} catch (error) {{
          console.warn(error);
        }}
      }}
      (async () => {{
        try {{
          status.textContent = 'Purge du cache PWA en cours…';
          await clearCaches();
          status.textContent = 'Cache purgé. Redirection vers l\\'app…';
        }} catch (error) {{
          status.textContent = `Purge terminée avec avertissement: ${{error.message}}`;
        }} finally {{
          setTimeout(() => {{ location.replace(nextUrl); }}, 400);
        }}
      }})();
    </script>
  </body>
</html>""")


def _load_latest_sync_run(data_dir: Path) -> dict[str, Any] | None:
    runs_dir = data_dir / "runs"
    if not runs_dir.exists():
        return None
    manifests = sorted(runs_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for manifest_path in manifests:
        try:
            payload = repair_text_tree(json.loads(manifest_path.read_text(encoding="utf-8")))
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


def _boot_trace_path(data_dir: Path) -> Path:
    return default_boot_trace_path(data_dir)


def _append_boot_trace(data_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    trace_path = _boot_trace_path(data_dir)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    event = repair_text_tree({
        "timestamp": payload.get("timestamp") or datetime.now(UTC).isoformat(),
        "stage": payload.get("stage") or payload.get("event") or "unknown",
        "event": payload.get("event") or payload.get("stage") or "unknown",
        "detail": payload.get("detail"),
        "app_version": payload.get("app_version"),
        "section": payload.get("section"),
        "workspace": payload.get("workspace"),
        "provider": payload.get("provider"),
        "state": payload.get("state"),
        "url": payload.get("url"),
        "hash": payload.get("hash"),
    })
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _read_boot_trace(data_dir: Path, limit: int = 50) -> list[dict[str, Any]]:
    trace_path = _boot_trace_path(data_dir)
    if not trace_path.exists():
        return []
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            payload = repair_text_tree(json.loads(line))
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _build_trend_series(data_dir: Path, days: int = 90) -> dict[str, Any]:
    db_path = data_dir / "normalized" / "coach_garmin.duckdb"
    if not db_path.exists():
        return {
            "window_days": days,
            "daily_volume": [],
            "daily_bike_volume": [],
            "daily_load_ratio": [],
            "daily_sleep": [],
            "daily_resting_hr": [],
            "daily_hrv": [],
            "daily_running_pace": [],
            "daily_running_hr": [],
            "cadence_daily": [],
            "pace_hr_sessions": [],
            "heart_rate_zone_share": {"distribution": []},
            "heart_rate_zone_share_running": {"distribution": []},
            "pace_hr_curve_debug": {},
        }

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        latest_day_row = con.execute("SELECT max(activity_date) FROM activities WHERE activity_date IS NOT NULL").fetchone()
        latest_day = latest_day_row[0] if latest_day_row else None
        if latest_day is None:
            return {
                "window_days": days,
                "daily_volume": [],
                "daily_bike_volume": [],
                "daily_load_ratio": [],
                "daily_sleep": [],
                "daily_resting_hr": [],
                "daily_hrv": [],
                "daily_running_pace": [],
                "daily_running_hr": [],
                "cadence_daily": [],
                "pace_hr_sessions": [],
                "heart_rate_zone_share": {"distribution": []},
                "heart_rate_zone_share_running": {"distribution": []},
                "pace_hr_curve_debug": {},
            }

        latest_date = _coerce_date(latest_day)
        window_days = max(int(days or 90), 1)
        window_start = latest_date - timedelta(days=window_days - 1)
        volume_rows = con.execute(
            """
            SELECT activity_date,
                   SUM(CASE WHEN LOWER(activity_type) IN ('running','trail_running','treadmill_running','indoor_running') THEN distance_meters ELSE 0 END),
                   SUM(CASE WHEN LOWER(activity_type) IN ('cycling','bike','biking','road_biking','mountain_biking','indoor_cycling','virtual_ride','ebike','gravel_cycling') THEN distance_meters ELSE 0 END),
                   SUM(CASE WHEN LOWER(activity_type) IN ('running','trail_running','treadmill_running','indoor_running') THEN training_load ELSE 0 END)
            FROM activities
            WHERE activity_date >= ?
            GROUP BY activity_date
            ORDER BY activity_date
            """,
            [window_start.isoformat()],
        ).fetchall()
        load_rows = con.execute(
            """
            SELECT metric_date, load_7d, load_ratio_7_28, sleep_hours_7d, resting_hr_7d, hrv_7d
            FROM derived_daily_metrics
            WHERE metric_date >= ?
            ORDER BY metric_date
            """,
            [window_start.isoformat()],
        ).fetchall()
        pace_rows = con.execute(
            """
            SELECT activity_date, activity_type, duration_seconds, distance_meters, average_hr, raw_payload
            FROM activities
            WHERE activity_date >= ?
            ORDER BY activity_date DESC, started_at DESC
            LIMIT 12
            """,
            [window_start.isoformat()],
        ).fetchall()
        zone_rows = con.execute(
            """
            SELECT max_hr, zone1_floor, zone2_floor, zone3_floor, zone4_floor, zone5_floor
            FROM heart_rate_zones
            LIMIT 1
            """
        ).fetchall()
    finally:
        con.close()

    running_rows = [row for row in pace_rows if _is_running_type(row[1])]
    summary_rows = running_rows if running_rows else pace_rows
    cadence_daily_rows = _build_cadence_daily_series(
        [
            {
                "activity_type": row[1],
                "raw_payload": row[5],
                "activity_date": row[0],
                "duration_seconds": row[2],
            }
            for row in pace_rows
            if _is_running_type(row[1])
        ]
    )
    cadence_trend = [
        {"metric_date": metric_date, "cadence_spm": cadence_daily_rows[metric_date]}
        for metric_date in sorted(cadence_daily_rows)
    ]
    zone_row = zone_rows[0] if zone_rows else None
    max_hr = float(zone_row[0]) if zone_row and zone_row[0] is not None else None
    zone_floors = [zone_row[index] if zone_row and len(zone_row) > index and zone_row[index] is not None else None for index in range(1, 6)]
    def _zone_for_hr(value: float | None) -> int | None:
        if value is None:
            return None
        if zone_floors[1] is not None:
            if value < zone_floors[1]:
                return 1
            if zone_floors[2] is not None and value < zone_floors[2]:
                return 2
            if zone_floors[3] is not None and value < zone_floors[3]:
                return 3
            if zone_floors[4] is not None and value < zone_floors[4]:
                return 4
            return 5
        if max_hr:
            ratio = value / max_hr
            if ratio < 0.6:
                return 1
            if ratio < 0.7:
                return 2
            if ratio < 0.8:
                return 3
            if ratio < 0.9:
                return 4
            return 5
        return 5 if value >= 175 else 4 if value >= 160 else 3 if value >= 145 else 2 if value >= 130 else 1
    def _zone_distribution(rows, predicate):
        zone_seconds = {f"zone_{index}": 0.0 for index in range(1, 6)}
        total_seconds = 0.0
        source_count = 0
        for row in rows:
            if not predicate(row[1]):
                continue
            duration_seconds = float(row[2] or 0.0)
            avg_hr = float(row[4]) if row[4] is not None else None
            zone = _zone_for_hr(avg_hr)
            if duration_seconds <= 0 or zone is None:
                continue
            zone_seconds[f"zone_{zone}"] += duration_seconds
            total_seconds += duration_seconds
            source_count += 1
        distribution = []
        for index in range(1, 6):
            seconds = zone_seconds[f"zone_{index}"]
            share = (seconds / total_seconds) if total_seconds else None
            distribution.append({"zone": index, "seconds": round(seconds, 1), "minutes": round(seconds / 60.0, 1), "share": round(share, 3) if share is not None else None})
        return {"distribution": distribution, "total_seconds": round(total_seconds, 1), "source_count": source_count, "method": "Approximate activity-duration weighting by average HR"}
    daily_volume = [
        {
            "date": str(row[0]),
            "distance_km": round((row[1] or 0.0) / 1000.0, 2),
            "bike_distance_km": round((row[2] or 0.0) / 1000.0, 2),
            "training_load": round(float(row[3] or 0.0), 2),
        }
        for row in volume_rows
    ]
    daily_load_ratio = [
        {"date": str(row[0]), "load_7d": row[1], "load_ratio_7_28": row[2]}
        for row in load_rows
    ]
    daily_sleep = [
        {"date": str(row[0]), "sleep_hours": row[3]}
        for row in load_rows
    ]
    daily_resting_hr = [
        {"date": str(row[0]), "resting_hr": row[4]}
        for row in load_rows
    ]
    daily_hrv = [
        {"date": str(row[0]), "hrv_ms": row[5]}
        for row in load_rows
    ]
    daily_bike_volume = [
        {
            "date": str(row[0]),
            "distance_km": round((row[2] or 0.0) / 1000.0, 2),
        }
        for row in volume_rows
    ]
    daily_running_pace = []
    daily_running_hr = []
    pace_by_day: dict[str, list[tuple[float, float]]] = {}
    hr_by_day: dict[str, list[tuple[float, float]]] = {}
    for row in pace_rows:
      if not _is_running_type(row[1]):
        continue
      activity_date = str(row[0]) if row[0] is not None else None
      duration_seconds = float(row[2] or 0.0)
      distance_meters = float(row[3] or 0.0)
      avg_hr = float(row[4]) if row[4] is not None else None
      if activity_date and duration_seconds > 0 and distance_meters > 0:
        pace = _pace_min_per_km(duration_seconds / 60.0, distance_meters / 1000.0)
        if pace is not None:
          pace_by_day.setdefault(activity_date, []).append((pace, max(duration_seconds, 60.0)))
        if avg_hr is not None:
          hr_by_day.setdefault(activity_date, []).append((avg_hr, max(duration_seconds, 60.0)))
    for metric_date, samples in pace_by_day.items():
      total_weight = sum(weight for _, weight in samples)
      if total_weight > 0:
        daily_running_pace.append({"date": metric_date, "pace_min_per_km": round(sum(value * weight for value, weight in samples) / total_weight, 2)})
    for metric_date, samples in hr_by_day.items():
      total_weight = sum(weight for _, weight in samples)
      if total_weight > 0:
        daily_running_hr.append({"date": metric_date, "heart_rate": round(sum(value * weight for value, weight in samples) / total_weight, 1)})
    zone_distribution_all = _zone_distribution(pace_rows, lambda activity_type: True)
    zone_distribution_running = _zone_distribution(pace_rows, _is_running_type)
    pace_hr_curve_input = [
        {
            "pace_min_per_km": _pace_min_per_km((row[2] or 0.0) / 60.0, (row[3] or 0.0) / 1000.0),
            "heart_rate": float(row[4]) if row[4] is not None else None,
            "cadence_spm": None,
            "weight": max(float(row[2] or 0.0), 90.0),
            "point_count": 1,
        }
        for row in running_rows
        if (row[2] or 0.0) > 0 and (row[3] or 0.0) > 0 and row[4] is not None
    ]
    pace_hr_curve = _build_pace_hr_curve(pace_hr_curve_input)
    pace_hr_curve_debug = _build_pace_hr_curve_diagnostics(pace_hr_curve_input, pace_hr_curve)
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
    return repair_text_tree({
        "window_days": days,
        "daily_volume": daily_volume,
        "daily_bike_volume": daily_bike_volume,
        "daily_load_ratio": daily_load_ratio,
        "daily_sleep": daily_sleep,
        "daily_resting_hr": daily_resting_hr,
        "daily_hrv": daily_hrv,
        "daily_running_pace": daily_running_pace,
        "daily_running_hr": daily_running_hr,
        "cadence_daily": cadence_trend,
        "pace_hr_sessions": pace_hr_sessions,
        "pace_hr_curve": pace_hr_curve,
        "pace_hr_curve_debug": pace_hr_curve_debug,
        "heart_rate_zone_share": zone_distribution_all,
        "heart_rate_zone_share_running": zone_distribution_running,
    })


def _build_handler(config: CoachPwaConfig):
    class Handler(BaseHTTPRequestHandler):
        def _log_http(self, method: str, path: str, status: int | None = None) -> None:
            try:
                _append_boot_trace(
                    config.default_data_dir,
                    {
                        "event": "http",
                        "stage": f"http:{method.lower()}",
                        "detail": path if status is None else f"{path} -> {status}",
                        "state": "info",
                    },
                )
            except Exception:
                pass

        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(repair_text_tree(payload), indent=2, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, payload: str, content_type: str = "text/plain; charset=utf-8", status: int = HTTPStatus.OK) -> None:
            body = repair_mojibake_text(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return repair_text_tree(json.loads(raw.decode("utf-8")))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/reset-cache":
                params = parse_qs(parsed.query)
                next_url = params.get("next", ["/?v=reset"])[0]
                version = params.get("v", ["reset"])[0]
                self._log_http("GET", parsed.path)
                self._send_text(_build_reset_cache_page(next_url, version), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/debug/boot":
                params = parse_qs(parsed.query)
                data_dir = Path(params.get("data_dir", [str(config.default_data_dir)])[0])
                limit = int(params.get("limit", ["50"])[0])
                self._log_http("GET", parsed.path)
                self._send_json(
                    {
                        "data_dir": str(data_dir),
                        "trace_path": str(_boot_trace_path(data_dir)),
                        "events": _read_boot_trace(data_dir, limit=max(1, min(limit, 200))),
                    }
                )
                return
            if parsed.path == "/api/auth/debug":
                params = parse_qs(parsed.query)
                self._log_http("GET", parsed.path)
                self._send_json(
                    describe_auth_environment(
                        tokenstore_path=Path(params.get("tokenstore_path", [str(DEFAULT_GARMIN_TOKENSTORE)])[0]),
                    )
                )
                return
            if parsed.path == "/api/status":
                params = parse_qs(parsed.query)
                data_dir = Path(params.get("data_dir", [str(config.default_data_dir)])[0])
                provider = params.get("provider", ["ollama"])[0]
                model = params.get("model", [None])[0]
                base_url = params.get("base_url", [None])[0]
                try:
                    trend_days = max(30, min(365, int(params.get("days", ["90"])[0] or 90)))
                except (TypeError, ValueError):
                    trend_days = 90
                include_provider_probe = params.get("probe", ["0"])[0] in {"1", "true", "yes", "on"}
                self._log_http("GET", parsed.path)
                self._send_json(
                    build_workspace_status(
                        data_dir,
                        provider=provider,
                        model=model,
                        base_url=base_url,
                        include_provider_probe=include_provider_probe,
                        trend_days=trend_days,
                    )
                )
                return
            file_path = _resolve_static_path(config.web_root, parsed.path)
            if file_path is None:
                file_path = config.web_root / "index.html"
            if not file_path.exists() or not file_path.is_file():
                self._log_http("GET", parsed.path, status=HTTPStatus.NOT_FOUND)
                self._send_text("Not found", status=HTTPStatus.NOT_FOUND)
                return
            body, content_type = _build_static_response(file_path)
            self._log_http("GET", parsed.path, status=HTTPStatus.OK)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            payload = self._read_json()
            if parsed.path == "/api/debug/boot":
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                event = _append_boot_trace(data_dir, payload)
                self._log_http("POST", parsed.path)
                self._send_json({"ok": True, "event": event, "trace_path": str(_boot_trace_path(data_dir))})
                return
            if parsed.path == "/api/import":
                source_path = str(payload.get("source_path") or "").strip()
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                run_label = str(payload.get("run_label") or "pwa-import")
                self._log_http("POST", parsed.path)
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
            if parsed.path == "/api/sync/garmin-connect":
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                self._log_http("POST", parsed.path)
                try:
                    result = sync_garmin_connect(
                        data_dir=data_dir,
                        days=int(payload.get("days") or 30),
                        run_label=str(payload.get("run_label") or "pwa-garmin-sync"),
                        start_date=payload.get("start_date"),
                        end_date=payload.get("end_date"),
                    )
                except Exception as exc:  # pragma: no cover - surfaced in UI
                    self._send_json({"error": str(exc), "retryable": False}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._send_json(result)
                return
            if parsed.path == "/api/recalculate":
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                self._log_http("POST", parsed.path)
                try:
                    result = recalculate_workspace(
                        data_dir=data_dir,
                        provider=str(payload.get("provider") or "ollama"),
                        model=payload.get("model"),
                        base_url=payload.get("base_url"),
                        api_key=payload.get("api_key"),
                    )
                except Exception as exc:  # pragma: no cover - surfaced in UI
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._send_json(result)
                return
            if parsed.path == "/api/auth/test":
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                self._log_http("POST", parsed.path)
                result = test_garmin_auth(
                    data_dir=data_dir,
                    tokenstore_path=Path(str(payload.get("tokenstore_path") or DEFAULT_GARMIN_TOKENSTORE)),
                )
                self._send_json(result, status=HTTPStatus.OK if result.get("ok") else HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if parsed.path == "/api/coach/prepare":
                goal_text = str(payload.get("goal_text") or "").strip()
                data_dir = Path(str(payload.get("data_dir") or config.default_data_dir))
                self._log_http("POST", parsed.path)
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
                self._log_http("POST", parsed.path)
                if not goal_text:
                    self._send_json({"error": "goal_text is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                try:
                    result = generate_coach_plan(
                        data_dir=data_dir,
                        goal_text=goal_text,
                        answers=dict(payload.get("answers") or {}),
                        provider=str(payload.get("provider") or "ollama"),
                        model=payload.get("model"),
                        base_url=payload.get("base_url"),
                        api_key=payload.get("api_key"),
                    )
                except Exception as exc:  # pragma: no cover - surfaced in UI
                    status = HTTPStatus.SERVICE_UNAVAILABLE if _is_provider_issue(exc) else HTTPStatus.BAD_REQUEST
                    self._send_json({"error": str(exc), "retryable": status == HTTPStatus.SERVICE_UNAVAILABLE}, status=status)
                    return
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


def _is_provider_issue(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "gemini request failed with http 503",
            "gemini request failed with http 429",
            "openai request failed with http 503",
            "openai request failed with http 429",
            "ollama request failed with http 503",
            "ollama request failed with http 429",
            "unavailable",
            "temporarily unavailable",
        )
    )

