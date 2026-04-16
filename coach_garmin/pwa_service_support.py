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

import coach_garmin.pwa_service_runtime_support as _runtime
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

_runtime.BaseHTTPRequestHandler = BaseHTTPRequestHandler
_runtime.HTTPStatus = HTTPStatus
_runtime.parse_qs = parse_qs
_runtime.urlparse = urlparse
_runtime.DEFAULT_GARMIN_TOKENSTORE = DEFAULT_GARMIN_TOKENSTORE
_runtime.describe_auth_environment = describe_auth_environment
_runtime.test_garmin_auth = test_garmin_auth


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


from coach_garmin.pwa_service_runtime_support import (
    _append_boot_trace,
    _boot_trace_path,
    _build_handler,
    _build_reset_cache_page,
    _build_static_response,
    _build_trend_series,
    _coerce_date,
    _is_provider_issue,
    _is_running_type,
    _load_latest_sync_run,
    _pace_min_per_km,
    _probe_provider,
    _read_boot_trace,
    _resolve_static_path,
)

