from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from coach_garmin.storage import (
    default_coverage_report_path,
    default_db_path,
    default_report_path,
    read_records,
    write_json,
)
from coach_garmin.coverage import build_feature_coverage_report
from coach_garmin.text_encoding import repair_text_tree


@dataclass(slots=True)
class ActivityRow:
    record_hash: str
    source_run_id: str
    activity_id: str | None
    activity_type: str | None
    started_at: str | None
    activity_date: str | None
    duration_seconds: float | None
    distance_meters: float | None
    calories: float | None
    average_hr: float | None
    max_hr: float | None
    training_load: float | None
    raw_payload: str


@dataclass(slots=True)
class ArtifactInventoryRow:
    source_run_id: str
    dataset: str
    source_path: str
    stored_path: str
    file_format: str
    source_filename: str
    record_count: int
    content_hash: str
    source_kind: str | None
    raw_metadata: str


@dataclass(slots=True)
class NormalizedLineageRow:
    record_hash: str
    source_run_id: str
    dataset: str
    source_filename: str
    source_path: str
    stored_path: str
    content_hash: str


@dataclass(slots=True)
class WellnessRow:
    dataset: str
    record_hash: str
    source_run_id: str
    metric_date: str | None
    resting_hr: float | None = None
    avg_hr: float | None = None
    hrv_ms: float | None = None
    stress_score: float | None = None
    body_battery: float | None = None
    steps: float | None = None
    intensity_minutes: float | None = None
    training_readiness: float | None = None
    recovery_time_hours: float | None = None
    sleep_duration_seconds: float | None = None
    raw_payload: str = ""


@dataclass(slots=True)
class AcuteLoadRow:
    record_hash: str
    source_run_id: str
    metric_date: str | None
    acute_load: float | None
    chronic_load: float | None
    load_ratio: float | None
    acwr_percent: float | None
    acwr_status: str | None
    raw_payload: str


@dataclass(slots=True)
class TrainingHistoryRow:
    record_hash: str
    source_run_id: str
    metric_date: str | None
    sport: str | None
    sub_sport: str | None
    training_status: str | None
    fitness_trend: str | None
    feedback_phrase: str | None
    raw_payload: str


@dataclass(slots=True)
class ProfileRow:
    record_hash: str
    source_run_id: str
    profile_id: str | None
    display_name: str | None
    full_name: str | None
    gender: str | None
    birth_date: str | None
    location: str | None
    raw_payload: str


@dataclass(slots=True)
class HeartRateZoneRow:
    record_hash: str
    source_run_id: str
    sport: str | None
    training_method: str | None
    resting_hr: float | None
    max_hr: float | None
    lactate_threshold_hr: float | None
    zone1_floor: float | None
    zone2_floor: float | None
    zone3_floor: float | None
    zone4_floor: float | None
    zone5_floor: float | None
    raw_payload: str


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        current: Any = record
        found = True
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found and current not in ("", None):
            return current
    return None


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_floats(*values: Any) -> float | None:
    parsed = [_parse_float(value) for value in values]
    present = [value for value in parsed if value is not None]
    if not present:
        return None
    return float(sum(present))


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        if value > 1_000_000_000_000:
            return datetime.fromtimestamp(value / 1000.0, tz=UTC)
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        for candidate in (text, text.replace(" ", "T")):
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed_dt = _parse_datetime(value)
    if parsed_dt:
        return parsed_dt.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _json(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=True)


def _activity_speed_mps(duration_seconds: float | None, distance_meters: float | None) -> float | None:
    if duration_seconds in (None, 0) or distance_meters in (None, 0):
        return None
    if duration_seconds <= 0 or distance_meters <= 0:
        return None
    return distance_meters / duration_seconds


def _pace_min_per_km(duration_minutes: float | None, distance_km: float | None) -> float | None:
    if duration_minutes in (None, 0) or distance_km in (None, 0):
        return None
    if duration_minutes <= 0 or distance_km <= 0:
        return None
    return duration_minutes / distance_km


def _safe_json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = repair_text_tree(json.loads(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}

def _build_daily_distance_series(
    activities_rows: list[dict[str, Any]],
    predicate,
) -> dict[str, float]:
    by_day: dict[str, float] = {}
    for row in activities_rows:
        if not predicate(row.get("activity_type")):
            continue
        activity_date = row.get("activity_date")
        distance_meters = _parse_float(row.get("distance_meters")) or 0.0
        if activity_date is None or distance_meters <= 0:
            continue
        by_day.setdefault(str(activity_date), 0.0)
        by_day[str(activity_date)] += distance_meters
    return {day: round(distance / 1000.0, 2) for day, distance in by_day.items()}


def _build_daily_wellness_series(
    wellness_rows: list[dict[str, Any]],
    key: str,
) -> dict[str, float]:
    by_day: dict[str, float] = {}
    for row in wellness_rows:
        metric_date = row.get("metric_date")
        value = row.get(key)
        if metric_date is None or value is None:
            continue
        try:
            by_day[str(metric_date)] = round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return by_day


def _aggregate_wellness_sleep_hours(merged_wellness: dict[str, dict[str, Any]], metric_date: str) -> float | None:
    if metric_date not in merged_wellness:
        return None
    row = merged_wellness.get(metric_date, {})
    if "sleep_duration_seconds" not in row:
        return None
    try:
        return round((float(row["sleep_duration_seconds"]) or 0.0) / 3600.0, 2)
    except (TypeError, ValueError):
        return None


def _is_plausible_activity(
    activity_type: str | None,
    duration_seconds: float | None,
    distance_meters: float | None,
) -> bool:
    if duration_seconds is not None and duration_seconds <= 0:
        return False
    if distance_meters is not None and distance_meters < 0:
        return False
    if duration_seconds is not None and duration_seconds > 48 * 3600:
        return False
    if distance_meters is not None and distance_meters > 1_000_000:
        return False

    speed = _activity_speed_mps(duration_seconds, distance_meters)
    if speed is None:
        return True

    normalized_type = (activity_type or "").lower()
    if normalized_type in {"running", "trail_running", "walking", "hiking"}:
        return 0.5 <= speed <= 8.5
    if normalized_type in {"cycling", "biking"}:
        return 1.0 <= speed <= 30.0
    if normalized_type in {"swimming"}:
        return 0.2 <= speed <= 3.5
    return 0.2 <= speed <= 35.0


def _looks_like_garmin_summary_units(
    record: dict[str, Any],
    duration_seconds: float | None,
    distance_meters: float | None,
) -> bool:
    if duration_seconds is None or distance_meters is None:
        return False

    speed_hint = _parse_float(_first(record, "avgSpeed", "averageSpeed"))
    raw_ratio = _activity_speed_mps(duration_seconds, distance_meters)
    if speed_hint is None or raw_ratio is None:
        return False

    return abs(raw_ratio - speed_hint) <= max(0.05, abs(speed_hint) * 0.2)


def _normalize_activity_measurements(
    record: dict[str, Any],
    activity_type: str | None,
    duration_seconds: float | None,
    distance_meters: float | None,
) -> tuple[float | None, float | None]:
    if _is_plausible_activity(activity_type, duration_seconds, distance_meters):
        return duration_seconds, distance_meters

    if _looks_like_garmin_summary_units(record, duration_seconds, distance_meters):
        corrected_duration = duration_seconds / 1000.0
        corrected_distance = distance_meters / 100.0
        if _is_plausible_activity(activity_type, corrected_duration, corrected_distance):
            return corrected_duration, corrected_distance

    if (
        duration_seconds is not None
        and distance_meters is not None
        and duration_seconds > 100_000
        and distance_meters > 10_000
        and (_activity_speed_mps(duration_seconds, distance_meters) or 0.0) < 1.0
    ):
        corrected_duration = duration_seconds / 100.0
        corrected_distance = distance_meters / 10.0
        if _is_plausible_activity(activity_type, corrected_duration, corrected_distance):
            return corrected_duration, corrected_distance

    return None, None


def _record_hash(dataset: str, record: dict[str, Any], *identity_parts: Any) -> str:
    blob = json.dumps(
        {
            "dataset": dataset,
            "identity": identity_parts,
            "record": record,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def normalize_dataset(
    dataset: str, records: list[dict[str, Any]], run_id: str
) -> tuple[
    list[ActivityRow],
    list[WellnessRow],
    list[AcuteLoadRow],
    list[TrainingHistoryRow],
    list[ProfileRow],
    list[HeartRateZoneRow],
]:
    activities: list[ActivityRow] = []
    wellness: list[WellnessRow] = []
    acute_load_rows: list[AcuteLoadRow] = []
    training_history_rows: list[TrainingHistoryRow] = []
    profile_rows: list[ProfileRow] = []
    heart_rate_zone_rows: list[HeartRateZoneRow] = []
    for record in records:
        if dataset == "activities":
            activity_id = _first(record, "activityId", "activity_id", "id", "summaryId")
            activity_type = _first(
                record,
                "activityType.typeKey",
                "activityType",
                "activity_type",
                "sport",
            )
            started_at = _parse_datetime(
                _first(record, "startTimeLocal", "startTimeGMT", "start_time", "start_at", "beginTimestamp")
            )
            activity_date = _parse_date(_first(record, "activityDate", "date", "calendarDate", "summaryDate"))
            if activity_date is None and started_at is not None:
                activity_date = started_at.date()
            raw_duration_seconds = _parse_float(
                _first(record, "durationSeconds", "duration_seconds", "duration", "elapsedDuration")
            )
            raw_distance_meters = _parse_float(_first(record, "distanceMeters", "distance_meters", "distance"))
            duration_seconds, distance_meters = _normalize_activity_measurements(
                record,
                str(activity_type) if activity_type is not None else None,
                raw_duration_seconds,
                raw_distance_meters,
            )
            training_load = _parse_float(
                _first(record, "trainingLoad", "training_load", "activityTrainingLoad", "load")
            )
            if duration_seconds is None or distance_meters is None:
                training_load = None
            if training_load is None and duration_seconds is not None:
                training_load = round(duration_seconds / 60.0, 2)
            activity_hash_parts = [
                str(activity_id) if activity_id is not None else None,
                started_at.isoformat() if started_at else None,
                str(activity_type) if activity_type is not None else None,
                duration_seconds,
                distance_meters,
            ]
            activities.append(
                ActivityRow(
                    record_hash=_record_hash("activities", {}, *activity_hash_parts),
                    source_run_id=run_id,
                    activity_id=str(activity_id) if activity_id is not None else None,
                    activity_type=str(activity_type) if activity_type is not None else None,
                    started_at=started_at.isoformat() if started_at else None,
                    activity_date=activity_date.isoformat() if activity_date else None,
                    duration_seconds=duration_seconds,
                    distance_meters=distance_meters,
                    calories=_parse_float(_first(record, "calories")),
                    average_hr=_parse_float(_first(record, "averageHR", "average_hr", "avgHeartRate", "avgHr")),
                    max_hr=_parse_float(_first(record, "maxHR", "max_hr", "maxHeartRate", "maxHr")),
                    training_load=training_load,
                    raw_payload=_json(record),
                )
            )
            continue

        metric_date = _parse_date(
            _first(
                record,
                "calendarDate",
                "summaryDate",
                "date",
                "metricDate",
                "day",
                "sleepDate",
                "sleepStartTimestampGMT",
                "timestamp",
            )
        )
        common = {
            "dataset": dataset,
            "record_hash": _record_hash(dataset, {}, metric_date.isoformat() if metric_date else None),
            "source_run_id": run_id,
            "metric_date": metric_date.isoformat() if metric_date else None,
            "raw_payload": _json(record),
        }

        if dataset == "sleep":
            duration = _parse_float(
                _first(record, "sleepDurationSeconds", "sleep_duration_seconds", "durationSeconds", "duration")
            )
            if duration is None:
                duration = _sum_floats(
                    _first(record, "deepSleepSeconds"),
                    _first(record, "lightSleepSeconds"),
                    _first(record, "remSleepSeconds"),
                    _first(record, "awakeSleepSeconds"),
                )
            wellness.append(
                WellnessRow(
                    **common,
                    sleep_duration_seconds=duration,
                )
            )
        elif dataset == "heart_rate":
            wellness.append(
                WellnessRow(
                    **common,
                    resting_hr=_parse_float(
                        _first(
                            record,
                            "restingHeartRate",
                            "currentDayRestingHeartRate",
                            "resting_heart_rate",
                            "restingHR",
                        )
                    ),
                    avg_hr=_parse_float(
                        _first(record, "averageHeartRate", "average_hr", "avgHeartRate", "minAvgHeartRate")
                    ),
                )
            )
        elif dataset == "hrv":
            wellness.append(
                WellnessRow(
                    **common,
                    hrv_ms=_parse_float(_first(record, "hrv", "hrvMs", "overnightAvg", "averageHrv")),
                )
            )
        elif dataset == "stress":
            wellness.append(
                WellnessRow(
                    **common,
                    stress_score=_parse_float(_first(record, "stressLevel", "stress", "averageStressLevel")),
                )
            )
        elif dataset == "body_battery":
            wellness.append(
                WellnessRow(
                    **common,
                    body_battery=_parse_float(_first(record, "bodyBattery", "body_battery", "avgBodyBattery")),
                )
            )
        elif dataset == "steps":
            wellness.append(
                WellnessRow(
                    **common,
                    steps=_parse_float(_first(record, "steps", "stepCount", "totalSteps")),
                )
            )
        elif dataset == "intensity_minutes":
            wellness.append(
                WellnessRow(
                    **common,
                    intensity_minutes=_parse_float(
                        _first(record, "intensityMinutes", "intensity_minutes", "moderateIntensityMinutes")
                    ),
                )
            )
        elif dataset == "training_readiness":
            wellness.append(
                WellnessRow(
                    **common,
                    training_readiness=_parse_float(_first(record, "trainingReadiness", "training_readiness", "score")),
                )
            )
        elif dataset == "recovery_time":
            recovery_time_hours = _parse_float(_first(record, "recoveryTimeHours", "recovery_time_hours", "recoveryHours"))
            if recovery_time_hours is None:
                minutes = _parse_float(_first(record, "recoveryTimeMinutes", "recovery_time_minutes"))
                recovery_time_hours = round(minutes / 60.0, 2) if minutes is not None else None
            wellness.append(
                WellnessRow(
                    **common,
                    recovery_time_hours=recovery_time_hours,
                )
            )
        elif dataset == "acute_load":
            acute_date = _parse_date(_first(record, "calendarDate", "date", "timestamp"))
            acute_load_rows.append(
                AcuteLoadRow(
                    record_hash=_record_hash("acute_load", {}, acute_date.isoformat() if acute_date else None),
                    source_run_id=run_id,
                    metric_date=acute_date.isoformat() if acute_date else None,
                    acute_load=_parse_float(_first(record, "dailyTrainingLoadAcute", "acuteLoad")),
                    chronic_load=_parse_float(_first(record, "dailyTrainingLoadChronic", "chronicLoad")),
                    load_ratio=_parse_float(_first(record, "dailyAcuteChronicWorkloadRatio", "acwr", "loadRatio")),
                    acwr_percent=_parse_float(_first(record, "acwrPercent")),
                    acwr_status=(
                        str(_first(record, "acwrStatus", "status"))
                        if _first(record, "acwrStatus", "status") is not None
                        else None
                    ),
                    raw_payload=_json(record),
                )
            )
        elif dataset == "training_history":
            history_date = _parse_date(_first(record, "calendarDate", "date", "timestamp"))
            training_history_rows.append(
                TrainingHistoryRow(
                    record_hash=_record_hash(
                        "training_history",
                        {},
                        history_date.isoformat() if history_date else None,
                        _first(record, "sport"),
                        _first(record, "subSport"),
                    ),
                    source_run_id=run_id,
                    metric_date=history_date.isoformat() if history_date else None,
                    sport=str(_first(record, "sport")) if _first(record, "sport") is not None else None,
                    sub_sport=str(_first(record, "subSport")) if _first(record, "subSport") is not None else None,
                    training_status=(
                        str(_first(record, "trainingStatus")) if _first(record, "trainingStatus") is not None else None
                    ),
                    fitness_trend=(
                        str(_first(record, "fitnessLevelTrend"))
                        if _first(record, "fitnessLevelTrend") is not None
                        else None
                    ),
                    feedback_phrase=(
                        str(_first(record, "trainingStatus2FeedbackPhrase"))
                        if _first(record, "trainingStatus2FeedbackPhrase") is not None
                        else None
                    ),
                    raw_payload=_json(record),
                )
            )
        elif dataset == "profile":
            profile_rows.append(
                ProfileRow(
                    record_hash=_record_hash(
                        "profile",
                        {},
                        _first(record, "profileId", "userProfileId", "id"),
                        _first(record, "displayName", "fullName"),
                    ),
                    source_run_id=run_id,
                    profile_id=(
                        str(_first(record, "profileId", "userProfileId", "id"))
                        if _first(record, "profileId", "userProfileId", "id") is not None
                        else None
                    ),
                    display_name=(
                        str(_first(record, "displayName", "profileName"))
                        if _first(record, "displayName", "profileName") is not None
                        else None
                    ),
                    full_name=str(_first(record, "fullName")) if _first(record, "fullName") is not None else None,
                    gender=str(_first(record, "gender")) if _first(record, "gender") is not None else None,
                    birth_date=(
                        _parse_date(_first(record, "birthDate", "dob")).isoformat()
                        if _parse_date(_first(record, "birthDate", "dob"))
                        else None
                    ),
                    location=(
                        str(_first(record, "location", "country", "timeZone", "timeZoneUnitDTO.timeZone"))
                        if _first(record, "location", "country", "timeZone", "timeZoneUnitDTO.timeZone") is not None
                        else None
                    ),
                    raw_payload=_json(record),
                )
            )
        elif dataset == "heart_rate_zones":
            heart_rate_zone_rows.append(
                HeartRateZoneRow(
                    record_hash=_record_hash(
                        "heart_rate_zones",
                        {},
                        _first(record, "sport", "activityType"),
                        _first(record, "trainingMethod"),
                    ),
                    source_run_id=run_id,
                    sport=(
                        str(_first(record, "sport", "activityType"))
                        if _first(record, "sport", "activityType") is not None
                        else None
                    ),
                    training_method=(
                        str(_first(record, "trainingMethod")) if _first(record, "trainingMethod") is not None else None
                    ),
                    resting_hr=_parse_float(_first(record, "restingHeartRateUsed", "restingHeartRate")),
                    max_hr=_parse_float(_first(record, "maxHeartRateUsed", "maxHeartRate")),
                    lactate_threshold_hr=_parse_float(_first(record, "lactateThresholdHeartRateUsed")),
                    zone1_floor=_parse_float(_first(record, "zone1Floor")),
                    zone2_floor=_parse_float(_first(record, "zone2Floor")),
                    zone3_floor=_parse_float(_first(record, "zone3Floor")),
                    zone4_floor=_parse_float(_first(record, "zone4Floor")),
                    zone5_floor=_parse_float(_first(record, "zone5Floor")),
                    raw_payload=_json(record),
                )
            )

    return (
        activities,
        wellness,
        acute_load_rows,
        training_history_rows,
        profile_rows,
        heart_rate_zone_rows,
    )


def _load_manifests(data_dir: Path) -> list[dict[str, Any]]:
    runs_dir = data_dir / "runs"
    if not runs_dir.exists():
        return []
    return [
        repair_text_tree(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(runs_dir.glob("*.json"))
    ]


def _build_rows(
    data_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    activities: dict[str, ActivityRow] = {}
    wellness: dict[str, WellnessRow] = {}
    acute_load_rows: dict[str, AcuteLoadRow] = {}
    training_history_rows: dict[str, TrainingHistoryRow] = {}
    profile_rows: dict[str, ProfileRow] = {}
    heart_rate_zone_rows: dict[str, HeartRateZoneRow] = {}
    artifact_inventory_rows: list[ArtifactInventoryRow] = []
    lineage_rows: list[NormalizedLineageRow] = []
    sync_runs: list[dict[str, Any]] = []

    for manifest in _load_manifests(data_dir):
        sync_runs.append(
            {
                "run_id": manifest["run_id"],
                "run_label": manifest.get("run_label", ""),
                "source_kind": manifest["source_kind"],
                "source_path": manifest["source_path"],
                "started_at": manifest["started_at"],
                "finished_at": manifest["finished_at"],
                "dataset_count": manifest["dataset_count"],
                "artifact_count": manifest["artifact_count"],
                "total_records": manifest["total_records"],
            }
        )
        for artifact in manifest.get("artifacts", []):
            stored_path = Path(artifact["stored_path"])
            source_path = artifact.get("source_path") or artifact.get("stored_path") or ""
            metadata = artifact.get("metadata", {})
            source_filename = metadata.get("source_filename") if isinstance(metadata, dict) else None
            artifact_inventory_rows.append(
                ArtifactInventoryRow(
                    source_run_id=manifest["run_id"],
                    dataset=artifact["dataset"],
                    source_path=source_path,
                    stored_path=str(stored_path),
                    file_format=str(artifact.get("file_format", "")),
                    source_filename=str(source_filename or stored_path.name),
                    record_count=int(artifact.get("record_count", 0) or 0),
                    content_hash=str(artifact.get("content_hash", "")),
                    source_kind=manifest["source_kind"],
                    raw_metadata=json.dumps(metadata, sort_keys=True, ensure_ascii=True),
                )
            )
            records = read_records(stored_path, dataset=artifact["dataset"])
            (
                activity_rows,
                wellness_rows,
                acute_rows,
                history_rows,
                profile_snapshot_rows,
                heart_zone_rows,
            ) = normalize_dataset(artifact["dataset"], records, manifest["run_id"])
            for row in activity_rows:
                activities[row.record_hash] = row
            for row in wellness_rows:
                wellness[row.record_hash] = row
            for row in acute_rows:
                acute_load_rows[row.record_hash] = row
            for row in history_rows:
                training_history_rows[row.record_hash] = row
            for row in profile_snapshot_rows:
                profile_rows[row.record_hash] = row
            for row in heart_zone_rows:
                heart_rate_zone_rows[row.record_hash] = row
            lineage_rows.extend(
                NormalizedLineageRow(
                    record_hash=row.record_hash,
                    source_run_id=manifest["run_id"],
                    dataset=artifact["dataset"],
                    source_filename=str(source_filename or stored_path.name),
                    source_path=source_path,
                    stored_path=str(stored_path),
                    content_hash=str(artifact.get("content_hash", "")),
                )
                for row in (
                    list(activity_rows)
                    + list(wellness_rows)
                    + list(acute_rows)
                    + list(history_rows)
                    + list(profile_snapshot_rows)
                    + list(heart_zone_rows)
                )
            )

    return (
        sync_runs,
        [asdict(row) for row in artifact_inventory_rows],
        [asdict(row) for row in activities.values()],
        [asdict(row) for row in wellness.values()],
        [asdict(row) for row in acute_load_rows.values()],
        [asdict(row) for row in training_history_rows.values()],
        [asdict(row) for row in profile_rows.values()],
        [asdict(row) for row in heart_rate_zone_rows.values()],
        [asdict(row) for row in lineage_rows],
    )


def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE OR REPLACE TABLE sync_runs (
            run_id VARCHAR,
            run_label VARCHAR,
            source_kind VARCHAR,
            source_path VARCHAR,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            dataset_count INTEGER,
            artifact_count INTEGER,
            total_records INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE artifact_inventory (
            source_run_id VARCHAR,
            dataset VARCHAR,
            source_path VARCHAR,
            stored_path VARCHAR,
            file_format VARCHAR,
            source_filename VARCHAR,
            record_count INTEGER,
            content_hash VARCHAR,
            source_kind VARCHAR,
            raw_metadata VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE activities (
            record_hash VARCHAR,
            source_run_id VARCHAR,
            activity_id VARCHAR,
            activity_type VARCHAR,
            started_at TIMESTAMP,
            activity_date DATE,
            duration_seconds DOUBLE,
            distance_meters DOUBLE,
            calories DOUBLE,
            average_hr DOUBLE,
            max_hr DOUBLE,
            training_load DOUBLE,
            raw_payload VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE normalized_lineage (
            record_hash VARCHAR,
            source_run_id VARCHAR,
            dataset VARCHAR,
            source_filename VARCHAR,
            source_path VARCHAR,
            stored_path VARCHAR,
            content_hash VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE wellness_daily (
            dataset VARCHAR,
            record_hash VARCHAR,
            source_run_id VARCHAR,
            metric_date DATE,
            resting_hr DOUBLE,
            avg_hr DOUBLE,
            hrv_ms DOUBLE,
            stress_score DOUBLE,
            body_battery DOUBLE,
            steps DOUBLE,
            intensity_minutes DOUBLE,
            training_readiness DOUBLE,
            recovery_time_hours DOUBLE,
            sleep_duration_seconds DOUBLE,
            raw_payload VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE derived_daily_metrics (
            metric_date DATE,
            activity_load DOUBLE,
            load_7d DOUBLE,
            load_28d DOUBLE,
            load_ratio_7_28 DOUBLE,
            sleep_hours_7d DOUBLE,
            resting_hr_7d DOUBLE,
            hrv_7d DOUBLE,
            progression_delta DOUBLE,
            fatigue_flag BOOLEAN,
            overreaching_flag BOOLEAN
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE acute_load_daily (
            record_hash VARCHAR,
            source_run_id VARCHAR,
            metric_date DATE,
            acute_load DOUBLE,
            chronic_load DOUBLE,
            load_ratio DOUBLE,
            acwr_percent DOUBLE,
            acwr_status VARCHAR,
            raw_payload VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE training_history_daily (
            record_hash VARCHAR,
            source_run_id VARCHAR,
            metric_date DATE,
            sport VARCHAR,
            sub_sport VARCHAR,
            training_status VARCHAR,
            fitness_trend VARCHAR,
            feedback_phrase VARCHAR,
            raw_payload VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE profile_snapshots (
            record_hash VARCHAR,
            source_run_id VARCHAR,
            profile_id VARCHAR,
            display_name VARCHAR,
            full_name VARCHAR,
            gender VARCHAR,
            birth_date DATE,
            location VARCHAR,
            raw_payload VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE heart_rate_zones (
            record_hash VARCHAR,
            source_run_id VARCHAR,
            sport VARCHAR,
            training_method VARCHAR,
            resting_hr DOUBLE,
            max_hr DOUBLE,
            lactate_threshold_hr DOUBLE,
            zone1_floor DOUBLE,
            zone2_floor DOUBLE,
            zone3_floor DOUBLE,
            zone4_floor DOUBLE,
            zone5_floor DOUBLE,
            raw_payload VARCHAR
        )
        """
    )


def _insert_rows(
    con: duckdb.DuckDBPyConnection,
    sync_runs: list[dict[str, Any]],
    artifact_inventory_rows: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]],
    acute_load_rows: list[dict[str, Any]],
    training_history_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
    heart_rate_zone_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
) -> None:
    if sync_runs:
        con.executemany(
            "INSERT INTO sync_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["run_id"],
                    row["run_label"],
                    row["source_kind"],
                    row["source_path"],
                    row["started_at"],
                    row["finished_at"],
                    row["dataset_count"],
                    row["artifact_count"],
                    row["total_records"],
                )
                for row in sync_runs
            ],
        )
    if artifact_inventory_rows:
        con.executemany(
            "INSERT INTO artifact_inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["source_run_id"],
                    row["dataset"],
                    row["source_path"],
                    row["stored_path"],
                    row["file_format"],
                    row["source_filename"],
                    row["record_count"],
                    row["content_hash"],
                    row["source_kind"],
                    row["raw_metadata"],
                )
                for row in artifact_inventory_rows
            ],
        )
    if activities:
        con.executemany(
            "INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["record_hash"],
                    row["source_run_id"],
                    row["activity_id"],
                    row["activity_type"],
                    row["started_at"],
                    row["activity_date"],
                    row["duration_seconds"],
                    row["distance_meters"],
                    row["calories"],
                    row["average_hr"],
                    row["max_hr"],
                    row["training_load"],
                    row["raw_payload"],
                )
                for row in activities
            ],
        )
    if wellness:
        con.executemany(
            "INSERT INTO wellness_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["dataset"],
                    row["record_hash"],
                    row["source_run_id"],
                    row["metric_date"],
                    row["resting_hr"],
                    row["avg_hr"],
                    row["hrv_ms"],
                    row["stress_score"],
                    row["body_battery"],
                    row["steps"],
                    row["intensity_minutes"],
                    row["training_readiness"],
                    row["recovery_time_hours"],
                    row["sleep_duration_seconds"],
                    row["raw_payload"],
                )
                for row in wellness
            ],
        )
    if acute_load_rows:
        con.executemany(
            "INSERT INTO acute_load_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["record_hash"],
                    row["source_run_id"],
                    row["metric_date"],
                    row["acute_load"],
                    row["chronic_load"],
                    row["load_ratio"],
                    row["acwr_percent"],
                    row["acwr_status"],
                    row["raw_payload"],
                )
                for row in acute_load_rows
            ],
        )
    if training_history_rows:
        con.executemany(
            "INSERT INTO training_history_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["record_hash"],
                    row["source_run_id"],
                    row["metric_date"],
                    row["sport"],
                    row["sub_sport"],
                    row["training_status"],
                    row["fitness_trend"],
                    row["feedback_phrase"],
                    row["raw_payload"],
                )
                for row in training_history_rows
            ],
        )
    if profile_rows:
        con.executemany(
            "INSERT INTO profile_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["record_hash"],
                    row["source_run_id"],
                    row["profile_id"],
                    row["display_name"],
                    row["full_name"],
                    row["gender"],
                    row["birth_date"],
                    row["location"],
                    row["raw_payload"],
                )
                for row in profile_rows
            ],
        )
    if heart_rate_zone_rows:
        con.executemany(
            "INSERT INTO heart_rate_zones VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["record_hash"],
                    row["source_run_id"],
                    row["sport"],
                    row["training_method"],
                    row["resting_hr"],
                    row["max_hr"],
                    row["lactate_threshold_hr"],
                    row["zone1_floor"],
                    row["zone2_floor"],
                    row["zone3_floor"],
                    row["zone4_floor"],
                    row["zone5_floor"],
                    row["raw_payload"],
                )
                for row in heart_rate_zone_rows
            ],
        )
    if lineage_rows:
        con.executemany(
            "INSERT INTO normalized_lineage VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["record_hash"],
                    row["source_run_id"],
                    row["dataset"],
                    row["source_filename"],
                    row["source_path"],
                    row["stored_path"],
                    row["content_hash"],
                )
                for row in lineage_rows
            ],
        )


def _aggregate_wellness(wellness_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = {}
    for row in wellness_rows:
        metric_date = row["metric_date"]
        if not metric_date:
            continue
        merged.setdefault(metric_date, {})
        for key in (
            "resting_hr",
            "avg_hr",
            "hrv_ms",
            "stress_score",
            "body_battery",
            "steps",
            "intensity_minutes",
            "training_readiness",
            "recovery_time_hours",
            "sleep_duration_seconds",
        ):
            value = row.get(key)
            if value is not None:
                merged[metric_date][key] = float(value)
    return merged


def compute_metrics(
    activities_rows: list[dict[str, Any]],
    wellness_rows: list[dict[str, Any]],
    heart_rate_zone_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from coach_garmin.analytics_series import (
        _build_cadence_daily_series,
        _build_pace_hr_curve,
        _build_pace_hr_curve_diagnostics,
        _build_running_daily_series,
        _build_zone_duration_distribution,
        _classify_running_session_type,
        _extract_zone_thresholds,
        _is_cycling_type,
        _is_running_type,
        _percentile,
        _session_type_label,
    )

    running_rows = [row for row in activities_rows if _is_running_type(row.get("activity_type"))]
    cycling_rows = [row for row in activities_rows if _is_cycling_type(row.get("activity_type"))]
    load_by_day: dict[str, float] = {}
    for row in running_rows:
        if row["activity_date"]:
            load_by_day.setdefault(row["activity_date"], 0.0)
            load_by_day[row["activity_date"]] += float(row["training_load"] or 0.0)

    running_distance_by_day = _build_daily_distance_series(running_rows, _is_running_type)
    cycling_distance_by_day = _build_daily_distance_series(cycling_rows, _is_cycling_type)
    cadence_by_day = _build_cadence_daily_series(running_rows)
    running_pace_by_day, running_hr_by_day = _build_running_daily_series(running_rows)
    zone_thresholds = _extract_zone_thresholds(heart_rate_zone_rows)
    zone_distribution_all = _build_zone_duration_distribution(activities_rows, zone_thresholds, lambda activity_type: True)
    zone_distribution_running = _build_zone_duration_distribution(running_rows, zone_thresholds, _is_running_type)
    running_distances = [float(row.get("distance_meters") or 0.0) for row in running_rows if row.get("distance_meters") is not None]
    running_durations = [float(row.get("duration_seconds") or 0.0) for row in running_rows if row.get("duration_seconds") is not None]
    long_distance_threshold = _percentile(running_distances, 0.85) if running_distances else None
    long_duration_threshold = _percentile(running_durations, 0.85) if running_durations else None
    running_session_types = []
    for row in running_rows:
        session_type = _classify_running_session_type(
            row,
            long_distance_threshold=long_distance_threshold,
            long_duration_threshold=long_duration_threshold,
            zone_thresholds=zone_thresholds,
        )
        running_session_types.append(
            {
                "metric_date": row.get("activity_date"),
                "started_at": row.get("started_at"),
                "session_type": session_type,
                "session_label": _session_type_label(session_type),
                "duration_minutes": round(float(row.get("duration_seconds") or 0.0) / 60.0, 1),
                "distance_km": round(float(row.get("distance_meters") or 0.0) / 1000.0, 2),
                "training_load": round(float(row.get("training_load") or 0.0), 1),
                "average_hr": round(float(row.get("average_hr") or 0.0), 1) if row.get("average_hr") is not None else None,
            }
        )
    merged_wellness = _aggregate_wellness(wellness_rows)
    all_dates = sorted(
        set(load_by_day)
        | set(running_distance_by_day)
        | set(cycling_distance_by_day)
        | set(running_pace_by_day)
        | set(running_hr_by_day)
        | set(merged_wellness)
        | set(cadence_by_day)
    )
    metrics_rows: list[dict[str, Any]] = []

    def trailing_average(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    for index, metric_date in enumerate(all_dates):
        window_7 = all_dates[max(0, index - 6) : index + 1]
        window_28 = all_dates[max(0, index - 27) : index + 1]
        previous_7 = all_dates[max(0, index - 13) : max(0, index - 6)]

        load_7d = round(sum(load_by_day.get(day, 0.0) for day in window_7), 2)
        load_28d = round(sum(load_by_day.get(day, 0.0) for day in window_28), 2)
        previous_7d = round(sum(load_by_day.get(day, 0.0) for day in previous_7), 2)
        equivalent_chronic_load = round(load_28d / 4.0, 2) if load_28d else None
        load_ratio = round(load_7d / equivalent_chronic_load, 3) if equivalent_chronic_load else None
        sleep_hours_7d = trailing_average(
            [
                merged_wellness[day]["sleep_duration_seconds"] / 3600.0
                for day in window_7
                if day in merged_wellness and "sleep_duration_seconds" in merged_wellness[day]
            ]
        )
        resting_hr_7d = trailing_average(
            [
                merged_wellness[day]["resting_hr"]
                for day in window_7
                if day in merged_wellness and "resting_hr" in merged_wellness[day]
            ]
        )
        hrv_7d = trailing_average(
            [
                merged_wellness[day]["hrv_ms"]
                for day in window_7
                if day in merged_wellness and "hrv_ms" in merged_wellness[day]
            ]
        )
        cadence_7d = trailing_average(
            [cadence_by_day[day] for day in window_7 if day in cadence_by_day]
        )
        cadence_28d = trailing_average(
            [cadence_by_day[day] for day in window_28 if day in cadence_by_day]
        )
        hrv_28d = trailing_average(
            [
                merged_wellness[day]["hrv_ms"]
                for day in window_28
                if day in merged_wellness and "hrv_ms" in merged_wellness[day]
            ]
        )
        progression_delta = round(load_7d - previous_7d, 2)
        fatigue_flag = bool(
            (sleep_hours_7d is not None and sleep_hours_7d < 7.0)
            or (
                hrv_7d is not None
                and hrv_28d is not None
                and hrv_28d > 0
                and hrv_7d < hrv_28d * 0.95
            )
        )
        overreaching_flag = bool(
            load_ratio is not None
            and load_ratio > 1.3
            and (
                (sleep_hours_7d is not None and sleep_hours_7d < 7.0)
                or (
                    hrv_7d is not None
                    and hrv_28d is not None
                    and hrv_28d > 0
                    and hrv_7d < hrv_28d * 0.9
                )
            )
        )
        metrics_rows.append(
            {
                "metric_date": metric_date,
                "activity_load": round(load_by_day.get(metric_date, 0.0), 2),
                "running_distance_km": round(running_distance_by_day.get(metric_date, 0.0), 2),
                "cycling_distance_km": round(cycling_distance_by_day.get(metric_date, 0.0), 2),
                "running_pace_min_per_km": running_pace_by_day.get(metric_date),
                "running_hr": running_hr_by_day.get(metric_date),
                "load_7d": load_7d,
                "load_28d": load_28d,
                "load_ratio_7_28": load_ratio,
                "equivalent_chronic_load_7d": equivalent_chronic_load,
                "sleep_hours_7d": sleep_hours_7d,
                "resting_hr_7d": resting_hr_7d,
                "hrv_7d": hrv_7d,
                "cadence_7d": cadence_7d,
                "cadence_28d": cadence_28d,
                "progression_delta": progression_delta,
                "fatigue_flag": fatigue_flag,
                "overreaching_flag": overreaching_flag,
            }
        )

    latest = metrics_rows[-1] if metrics_rows else {}
    load_7d_series = [row["load_7d"] for row in metrics_rows if row.get("load_7d") is not None]
    sleep_7d_series = [row["sleep_hours_7d"] for row in metrics_rows if row.get("sleep_hours_7d") is not None]
    resting_hr_series = [row["resting_hr_7d"] for row in metrics_rows if row.get("resting_hr_7d") is not None]
    hrv_series = [row["hrv_7d"] for row in metrics_rows if row.get("hrv_7d") is not None]
    cadence_series = [row["cadence_7d"] for row in metrics_rows if row.get("cadence_7d") is not None]
    running_pace_series = [row["running_pace_min_per_km"] for row in metrics_rows if row.get("running_pace_min_per_km") is not None]
    running_hr_series = [row["running_hr"] for row in metrics_rows if row.get("running_hr") is not None]
    load_ratio_series = [row["load_ratio_7_28"] for row in metrics_rows if row.get("load_ratio_7_28") is not None]
    cadence_latest = latest.get("cadence_7d")
    cadence_ref_low = _percentile(cadence_series, 0.25)
    cadence_ref_high = _percentile(cadence_series, 0.75)
    load_ref_low = _percentile(load_7d_series, 0.25)
    load_ref_high = _percentile(load_7d_series, 0.75)
    sleep_ref_low = _percentile(sleep_7d_series, 0.25)
    sleep_ref_high = _percentile(sleep_7d_series, 0.75)
    resting_hr_ref_low = _percentile(resting_hr_series, 0.25)
    resting_hr_ref_high = _percentile(resting_hr_series, 0.75)
    hrv_ref_low = _percentile(hrv_series, 0.25)
    hrv_ref_high = _percentile(hrv_series, 0.75)
    running_pace_ref_low = _percentile(running_pace_series, 0.25)
    running_pace_ref_high = _percentile(running_pace_series, 0.75)
    running_hr_ref_low = _percentile(running_hr_series, 0.25)
    running_hr_ref_high = _percentile(running_hr_series, 0.75)
    load_ratio_ref_low = 0.8
    load_ratio_ref_high = 1.2
    pace_hr_curve = _build_pace_hr_curve(running_rows)
    pace_hr_curve_debug = _build_pace_hr_curve_diagnostics(running_rows, pace_hr_curve)
    cadence_trend = [
        {"metric_date": metric_date, "cadence_spm": cadence_by_day[metric_date]}
        for metric_date in sorted(cadence_by_day)
    ]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "latest_day": latest.get("metric_date"),
        "activity_rows": len(activities_rows),
        "wellness_rows": len(wellness_rows),
        "supported_metrics": {
            "load_7d": "Sum of daily activity training load over the trailing 7 days.",
            "load_28d": "Sum of daily activity training load over the trailing 28 days.",
            "load_ratio_7_28": "Trailing 7-day load divided by the equivalent average 7-day load inferred from the trailing 28 days (`load_7d / (load_28d / 4)`).",
            "sleep_hours_7d": "Average recorded sleep duration over the trailing 7 days.",
            "resting_hr_7d": "Average resting heart rate over the trailing 7 days when available.",
            "hrv_7d": "Average HRV over the trailing 7 days when available.",
            "running_pace_min_per_km": "Weighted average pace from running activities on the day.",
            "running_hr": "Weighted average running heart rate from running activities on the day.",
            "progression_delta": "Difference between trailing 7-day load and the previous 7-day load.",
            "fatigue_flag": "True when sleep is below 7h or recent HRV is down versus the trailing 28-day baseline.",
            "overreaching_flag": "True when recent load is elevated and recovery signals are degraded.",
            "heart_rate_zone_share": "Approximate distribution of activity time across heart-rate zones using average HR per activity.",
        },
        "trend_insights": {
            "window_days": 90,
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
            "cadence_daily": cadence_trend,
            "pace_hr_curve": pace_hr_curve,
            "curve_point_count": len(pace_hr_curve),
            "pace_hr_curve_debug": pace_hr_curve_debug,
            "heart_rate_zone_share": zone_distribution_all,
            "heart_rate_zone_share_running": zone_distribution_running,
            "running_session_types": running_session_types,
            "hrv_daily": [],
        },
        "latest_metrics": latest,
    }
    report["trend_insights"]["daily_volume"] = [
        {
            "metric_date": row["metric_date"],
            "distance_km": round((running_distance_by_day.get(row["metric_date"], 0.0) or 0.0), 2),
            "training_load": round(float(load_by_day.get(row["metric_date"], 0.0) or 0.0), 2),
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_bike_volume"] = [
        {
            "metric_date": row["metric_date"],
            "distance_km": round((cycling_distance_by_day.get(row["metric_date"], 0.0) or 0.0), 2),
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_load"] = [
        {
            "metric_date": row["metric_date"],
            "activity_load": row["activity_load"],
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_load_ratio"] = [
        {
            "metric_date": row["metric_date"],
            "load_ratio_7_28": row["load_ratio_7_28"],
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_sleep"] = [
        {
            "metric_date": row["metric_date"],
            "sleep_hours": _aggregate_wellness_sleep_hours(merged_wellness, row["metric_date"]),
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_sleep_smoothed"] = [
        {
            "metric_date": row["metric_date"],
            "sleep_hours": row["sleep_hours_7d"],
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_resting_hr"] = [
        {
            "metric_date": row["metric_date"],
            "resting_hr": merged_wellness.get(row["metric_date"], {}).get("resting_hr"),
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_hrv"] = [
        {
            "metric_date": row["metric_date"],
            "hrv_ms": merged_wellness.get(row["metric_date"], {}).get("hrv_ms"),
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_hrv_smoothed"] = [
        {
            "metric_date": row["metric_date"],
            "hrv_ms": row["hrv_7d"],
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_running_pace"] = [
        {
            "metric_date": row["metric_date"],
            "pace_min_per_km": row["running_pace_min_per_km"],
        }
        for row in metrics_rows
    ]
    report["trend_insights"]["daily_running_hr"] = [
        {
            "metric_date": row["metric_date"],
            "heart_rate": row["running_hr"],
        }
        for row in metrics_rows
    ]
    latest.update(
        {
            "load_reference_low": load_ref_low,
            "load_reference_high": load_ref_high,
            "sleep_reference_low": sleep_ref_low,
            "sleep_reference_high": sleep_ref_high,
            "resting_hr_reference_low": resting_hr_ref_low,
            "resting_hr_reference_high": resting_hr_ref_high,
            "hrv_reference_low": hrv_ref_low,
            "hrv_reference_high": hrv_ref_high,
            "running_pace_reference_low": running_pace_ref_low,
            "running_pace_reference_high": running_pace_ref_high,
            "running_hr_reference_low": running_hr_ref_low,
            "running_hr_reference_high": running_hr_ref_high,
            "load_ratio_reference_low": load_ratio_ref_low,
            "load_ratio_reference_high": load_ratio_ref_high,
            "load_ratio_target": 1.0,
            "cadence_7d": cadence_latest,
            "cadence_28d": latest.get("cadence_28d"),
            "cadence_reference_low": cadence_ref_low,
            "cadence_reference_high": cadence_ref_high,
            "cadence_target_spm": 170,
            "pace_hr_curve_points": len(pace_hr_curve),
            "running_distance_km_7d": round(sum(running_distance_by_day.get(day, 0.0) for day in all_dates[-7:]), 2) if all_dates else 0.0,
            "cycling_distance_km_7d": round(sum(cycling_distance_by_day.get(day, 0.0) for day in all_dates[-7:]), 2) if all_dates else 0.0,
            "pace_hr_curve_debug": pace_hr_curve_debug,
            "heart_rate_zone_share": zone_distribution_all,
            "heart_rate_zone_share_running": zone_distribution_running,
            "running_session_types": running_session_types,
            "running_session_type_reference": {
                "long_distance_threshold_m": long_distance_threshold,
                "long_duration_threshold_s": long_duration_threshold,
                "quality_hr_floor": zone_thresholds.get("zone3_floor") if isinstance(zone_thresholds, dict) else None,
            },
        }
    )
    return metrics_rows, report


def rebuild_analytics(data_dir: Path) -> dict[str, Any]:
    (
        sync_runs,
        artifact_inventory_rows,
        activities_rows,
        wellness_rows,
        acute_load_rows,
        training_history_rows,
        profile_rows,
        heart_rate_zone_rows,
        lineage_rows,
    ) = _build_rows(data_dir)
    db_path = default_db_path(data_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        _ensure_schema(con)
        _insert_rows(
            con,
            sync_runs,
            artifact_inventory_rows,
            activities_rows,
            wellness_rows,
            acute_load_rows,
            training_history_rows,
            profile_rows,
            heart_rate_zone_rows,
            lineage_rows,
        )
        metrics_rows, report = compute_metrics(activities_rows, wellness_rows, heart_rate_zone_rows)
        if metrics_rows:
            con.executemany(
                "INSERT INTO derived_daily_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        row["metric_date"],
                        row["activity_load"],
                        row["load_7d"],
                        row["load_28d"],
                        row["load_ratio_7_28"],
                        row["sleep_hours_7d"],
                        row["resting_hr_7d"],
                        row["hrv_7d"],
                        row["progression_delta"],
                        row["fatigue_flag"],
                        row["overreaching_flag"],
                    )
                    for row in metrics_rows
                ],
            )
    finally:
        con.close()

    report_path = default_report_path(data_dir)
    write_json(report_path, report)
    coverage_report = build_feature_coverage_report(
        sync_runs=sync_runs,
        artifact_inventory_rows=artifact_inventory_rows,
        activities_rows=activities_rows,
        wellness_rows=wellness_rows,
        acute_load_rows=acute_load_rows,
        training_history_rows=training_history_rows,
        profile_rows=profile_rows,
        heart_rate_zone_rows=heart_rate_zone_rows,
        lineage_rows=lineage_rows,
        metrics_rows=metrics_rows,
        latest_report=report,
    )
    coverage_path = default_coverage_report_path(data_dir)
    write_json(coverage_path, coverage_report)
    return {
        "db_path": str(db_path),
        "report_path": str(report_path),
        "coverage_report_path": str(coverage_path),
        "sync_runs": len(sync_runs),
        "artifact_inventory_rows": len(artifact_inventory_rows),
        "activity_rows": len(activities_rows),
        "wellness_rows": len(wellness_rows),
        "acute_load_rows": len(acute_load_rows),
        "training_history_rows": len(training_history_rows),
        "profile_rows": len(profile_rows),
        "heart_rate_zone_rows": len(heart_rate_zone_rows),
        "lineage_rows": len(lineage_rows),
        "metric_rows": len(metrics_rows),
        "latest_day": report.get("latest_day"),
    }
