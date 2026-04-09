from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import fitdecode
except ImportError as exc:  # pragma: no cover - dependency installed in the venv
    fitdecode = None  # type: ignore[assignment]
    _FITDECODE_IMPORT_ERROR = exc
else:
    _FITDECODE_IMPORT_ERROR = None


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _first_value(message: Any, *field_names: str) -> Any:
    for field_name in field_names:
        try:
            if message.has_field(field_name):
                value = message.get_value(field_name)
                if value not in (None, ""):
                    return _jsonable(value)
        except Exception:
            continue
    return None


def _normalize_activity_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace(" ", "_")
    mapping = {
        "running": "running",
        "run": "running",
        "trail_running": "trail_running",
        "trailrun": "trail_running",
        "biking": "cycling",
        "cycling": "cycling",
        "ride": "cycling",
        "swimming": "swimming",
        "walk": "walking",
        "walking": "walking",
        "hiking": "hiking",
    }
    return mapping.get(text, text or None)


def read_fit_activity_records(path: Path) -> list[dict[str, Any]]:
    if fitdecode is None:  # pragma: no cover - dependency is installed in the venv
        raise RuntimeError(
            "FIT parsing requires the optional fitdecode dependency. Install it in the active environment."
        ) from _FITDECODE_IMPORT_ERROR

    sessions: list[dict[str, Any]] = []
    with fitdecode.FitReader(path) as fit:
        for frame in fit:
            if getattr(frame, "frame_type", None) != fitdecode.FIT_FRAME_DATA:
                continue
            if getattr(frame, "name", "") != "session":
                continue
            activity_type = _normalize_activity_type(
                _first_value(frame, "sport", "sub_sport", "activity", "activity_type")
            )
            started_at = _first_value(frame, "start_time", "timestamp")
            duration_seconds = _first_value(frame, "total_timer_time", "total_elapsed_time")
            distance_meters = _first_value(frame, "total_distance")
            average_hr = _first_value(frame, "avg_heart_rate", "avg_hr")
            max_hr = _first_value(frame, "max_heart_rate", "max_hr")
            calories = _first_value(frame, "total_calories", "calories")
            training_load = _first_value(frame, "training_load")
            avg_speed = _first_value(frame, "avg_speed")
            session: dict[str, Any] = {
                "sourceFormat": "fit",
                "activityType": activity_type,
                "startTimeLocal": started_at,
                "durationSeconds": duration_seconds,
                "distanceMeters": distance_meters,
                "averageHR": average_hr,
                "maxHR": max_hr,
                "calories": calories,
                "trainingLoad": training_load,
                "avgSpeed": avg_speed,
            }
            session = {key: value for key, value in session.items() if value not in (None, "")}
            sessions.append(session)

    return sessions
