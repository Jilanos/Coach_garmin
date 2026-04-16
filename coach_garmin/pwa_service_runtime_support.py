from __future__ import annotations

import json
import mimetypes
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from coach_garmin.analytics import (
    _build_cadence_daily_series,
    _build_pace_hr_curve,
    _build_pace_hr_curve_diagnostics,
    _classify_running_session_type,
    _extract_running_cadence_spm,
    _percentile,
    _session_type_label,
)
from coach_garmin.coach_chat import CoachChatSession
from coach_garmin.coach_llm import CoachLLMConfig, build_coach_client
from coach_garmin.coach_tools import LocalCoachToolkit
from coach_garmin.config import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT
from coach_garmin.storage import default_boot_trace_path
from coach_garmin.sync_state import load_sync_summary
from coach_garmin.text_encoding import repair_mojibake_text, repair_text_tree

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
                "daily_load": [],
                "daily_load_ratio": [],
                "daily_sleep": [],
                "daily_sleep_smoothed": [],
                "daily_resting_hr": [],
                "daily_hrv": [],
                "daily_hrv_smoothed": [],
                "daily_running_pace": [],
                "daily_running_hr": [],
                "cadence_daily": [],
                "cadence_diagnostics": {"activities": [], "summary": {}},
                "pace_hr_sessions": [],
                "heart_rate_zone_share": {"distribution": []},
                "heart_rate_zone_share_running": {"distribution": []},
                "pace_hr_curve_debug": {},
                "running_session_types": [],
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
                "daily_load": [],
                "daily_load_ratio": [],
                "daily_sleep": [],
                "daily_sleep_smoothed": [],
                "daily_resting_hr": [],
                "daily_hrv": [],
                "daily_hrv_smoothed": [],
                "daily_running_pace": [],
                "daily_running_hr": [],
                "cadence_daily": [],
                "cadence_diagnostics": {"activities": [], "summary": {}},
                "pace_hr_sessions": [],
                "heart_rate_zone_share": {"distribution": []},
                "heart_rate_zone_share_running": {"distribution": []},
                "pace_hr_curve_debug": {},
                "running_session_types": [],
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
            SELECT metric_date, activity_load, load_7d, load_ratio_7_28, sleep_hours_7d, hrv_7d
            FROM derived_daily_metrics
            WHERE metric_date >= ?
            ORDER BY metric_date
            """,
            [window_start.isoformat()],
        ).fetchall()
        wellness_rows = con.execute(
            """
            SELECT metric_date,
                   AVG(sleep_duration_seconds),
                   AVG(resting_hr),
                   AVG(hrv_ms)
            FROM wellness_daily
            WHERE metric_date >= ?
            GROUP BY metric_date
            ORDER BY metric_date
            """,
            [window_start.isoformat()],
        ).fetchall()
        pace_rows = con.execute(
            """
            SELECT activity_date, started_at, activity_type, duration_seconds, distance_meters, average_hr, training_load, raw_payload
            FROM activities
            WHERE activity_date >= ?
            ORDER BY activity_date DESC, started_at DESC
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

    running_rows = [row for row in pace_rows if _is_running_type(row[2])]
    summary_rows = running_rows if running_rows else pace_rows
    cadence_daily_rows = _build_cadence_daily_series(
        [
            {
                "activity_type": row[2],
                "raw_payload": row[7],
                "activity_date": row[0],
                "duration_seconds": row[3],
            }
            for row in pace_rows
            if _is_running_type(row[2])
        ]
    )
    cadence_trend = [
        {"metric_date": metric_date, "cadence_spm": cadence_daily_rows[metric_date]}
        for metric_date in sorted(cadence_daily_rows)
    ]
    zone_row = zone_rows[0] if zone_rows else None
    max_hr = float(zone_row[0]) if zone_row and zone_row[0] is not None else None
    zone_floors = [zone_row[index] if zone_row and len(zone_row) > index and zone_row[index] is not None else None for index in range(1, 6)]

    def _zone_bpm_bounds(index: int) -> str:
        floor = zone_floors[index - 1] if len(zone_floors) >= index else None
        next_floor = zone_floors[index] if len(zone_floors) > index else None
        floor_value = int(round(float(floor))) if floor is not None else None
        next_value = int(round(float(next_floor))) if next_floor is not None else None
        if index == 1:
            return f"< {next_value} bpm" if next_value is not None else "< 130 bpm"
        if index == 5:
            return f">= {floor_value} bpm" if floor_value is not None else ">= 175 bpm"
        if floor_value is not None and next_value is not None:
            return f"{floor_value}-{next_value - 1} bpm"
        return "bpm non défini"

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
            if not predicate(row[2]):
                continue
            duration_seconds = float(row[3] or 0.0)
            avg_hr = float(row[5]) if row[5] is not None else None
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
            distribution.append(
                {
                    "zone": index,
                    "seconds": round(seconds, 1),
                    "minutes": round(seconds / 60.0, 1),
                    "share": round(share, 3) if share is not None else None,
                    "bpm_range": _zone_bpm_bounds(index),
                }
            )
        return {
            "distribution": distribution,
            "total_seconds": round(total_seconds, 1),
            "source_count": source_count,
            "method": "Approximate activity-duration weighting by average HR",
            "thresholds": {
                "max_hr": round(max_hr, 1) if max_hr is not None else None,
                "zone_floors": [round(float(value), 1) if value is not None else None for value in zone_floors],
            },
        }
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
        {"date": str(row[0]), "activity_load": row[1], "load_7d": row[2], "load_ratio_7_28": row[3]}
        for row in load_rows
    ]
    daily_load = [
        {"date": str(row[0]), "activity_load": round(float(row[1] or 0.0), 2)}
        for row in load_rows
    ]
    daily_sleep = [
        {"date": str(row[0]), "sleep_hours": round(float(row[1]) / 3600.0, 2) if row[1] is not None else None}
        for row in wellness_rows
    ]
    daily_sleep_smoothed = [
        {"date": str(row[0]), "sleep_hours": round(float(row[4]), 2) if row[4] is not None else None}
        for row in load_rows
    ]
    daily_resting_hr = [
        {"date": str(row[0]), "resting_hr": round(float(row[2]), 1) if row[2] is not None else None}
        for row in wellness_rows
    ]
    daily_hrv = [
        {"date": str(row[0]), "hrv_ms": round(float(row[3]), 1) if row[3] is not None else None}
        for row in wellness_rows
    ]
    daily_hrv_smoothed = [
        {"date": str(row[0]), "hrv_ms": round(float(row[5]), 1) if row[5] is not None else None}
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
      if not _is_running_type(row[2]):
        continue
      activity_date = str(row[0]) if row[0] is not None else None
      duration_seconds = float(row[3] or 0.0)
      distance_meters = float(row[4] or 0.0)
      avg_hr = float(row[5]) if row[5] is not None else None
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
    running_distances = [float(row[4] or 0.0) for row in running_rows if row[4] is not None]
    running_durations = [float(row[3] or 0.0) for row in running_rows if row[3] is not None]
    long_distance_threshold = _percentile(running_distances, 0.85) if running_distances else None
    long_duration_threshold = _percentile(running_durations, 0.85) if running_durations else None
    zone_thresholds = {
        "zone3_floor": zone_floors[2] if len(zone_floors) > 2 else None,
        "zone4_floor": zone_floors[3] if len(zone_floors) > 3 else None,
    }
    running_session_types = []
    for row in running_rows:
        activity = {
            "activity_date": row[0],
            "started_at": row[1],
            "activity_type": row[2],
            "duration_seconds": row[3],
            "distance_meters": row[4],
            "average_hr": row[5],
            "training_load": row[6],
            "raw_payload": row[7],
        }
        session_type = _classify_running_session_type(
            activity,
            long_distance_threshold=long_distance_threshold,
            long_duration_threshold=long_duration_threshold,
            zone_thresholds=zone_thresholds,
        )
        running_session_types.append(
            {
                "metric_date": str(row[0]) if row[0] is not None else None,
                "started_at": str(row[1]) if row[1] is not None else None,
                "session_type": session_type,
                "session_label": _session_type_label(session_type),
                "duration_minutes": round(float(row[3] or 0.0) / 60.0, 1),
                "distance_km": round(float(row[4] or 0.0) / 1000.0, 2),
                "training_load": round(float(row[6] or 0.0), 1),
                "average_hr": round(float(row[5]), 1) if row[5] is not None else None,
            }
        )
    cadence_activity_diagnostics = []
    cadence_activity_values = []
    for row in running_rows:
        payload = repair_text_tree(json.loads(row[7])) if row[7] else {}
        cadence_spm = _extract_running_cadence_spm(payload) if isinstance(payload, dict) else None
        if cadence_spm is not None:
            cadence_activity_values.append(float(cadence_spm))
        cadence_activity_diagnostics.append(
            {
                "metric_date": str(row[0]) if row[0] is not None else None,
                "activity_type": row[2],
                "duration_seconds": round(float(row[3] or 0.0), 1),
                "raw_source_value": payload.get("averageRunCadence")
                or payload.get("averageRunningCadenceInStepsPerMinute")
                or payload.get("averageCadence")
                or payload.get("cadence"),
                "normalized_value": round(float(cadence_spm), 1) if cadence_spm is not None else None,
                "detected_unit": "spm"
                if cadence_spm is not None
                else ("unknown" if payload else "missing_payload"),
            }
        )
    cadence_plot_bounds = (
        {
            "min": round(min(cadence_activity_values), 1),
            "max": round(max(cadence_activity_values), 1),
        }
        if cadence_activity_values
        else {"min": None, "max": None}
    )
    pace_hr_curve_input = [
        {
            "pace_min_per_km": _pace_min_per_km((row[3] or 0.0) / 60.0, (row[4] or 0.0) / 1000.0),
            "heart_rate": float(row[5]) if row[5] is not None else None,
            "cadence_spm": next(
                (
                    entry["normalized_value"]
                    for entry in cadence_activity_diagnostics
                    if entry.get("metric_date") == (str(row[0]) if row[0] is not None else None)
                    and entry.get("duration_seconds") == round(float(row[3] or 0.0), 1)
                ),
                None,
            ),
            "weight": max(float(row[3] or 0.0), 90.0),
            "point_count": 1,
        }
        for row in running_rows
        if (row[3] or 0.0) > 0 and (row[4] or 0.0) > 0 and row[5] is not None
    ]
    pace_hr_curve = _build_pace_hr_curve(pace_hr_curve_input)
    pace_hr_curve_debug = _build_pace_hr_curve_diagnostics(pace_hr_curve_input, pace_hr_curve)
    pace_hr_sessions = [
        {
            "date": str(row[0]),
            "distance_km": round((row[4] or 0.0) / 1000.0, 2),
            "pace_min_per_km": _pace_min_per_km((row[3] or 0.0) / 60.0, (row[4] or 0.0) / 1000.0),
            "average_hr": round(float(row[5]), 1) if row[5] is not None else None,
        }
        for row in reversed(summary_rows[:8])
        if (row[3] or 0.0) > 0 and (row[4] or 0.0) > 0
    ]
    return repair_text_tree({
        "window_days": days,
        "daily_volume": daily_volume,
        "daily_bike_volume": daily_bike_volume,
        "daily_load": daily_load,
        "daily_load_ratio": daily_load_ratio,
        "daily_sleep": daily_sleep,
        "daily_sleep_smoothed": daily_sleep_smoothed,
        "daily_resting_hr": daily_resting_hr,
        "daily_hrv": daily_hrv,
        "daily_hrv_smoothed": daily_hrv_smoothed,
        "daily_running_pace": daily_running_pace,
        "daily_running_hr": daily_running_hr,
        "cadence_daily": cadence_trend,
        "cadence_diagnostics": {
            "activities": cadence_activity_diagnostics,
            "summary": {
                "activity_count": len(cadence_activity_diagnostics),
                "plotted_point_count": len(cadence_trend),
                "unit": "spm",
                "plot_bounds": cadence_plot_bounds,
            },
        },
        "pace_hr_sessions": pace_hr_sessions,
        "pace_hr_curve": pace_hr_curve,
        "pace_hr_curve_debug": pace_hr_curve_debug,
        "heart_rate_zone_share": zone_distribution_all,
        "heart_rate_zone_share_running": zone_distribution_running,
        "running_session_types": running_session_types,
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

