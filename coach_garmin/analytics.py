from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

from coach_garmin.storage import default_db_path, default_report_path, read_records, write_json


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


def normalize_dataset(dataset: str, records: list[dict[str, Any]], run_id: str) -> tuple[list[ActivityRow], list[WellnessRow]]:
    activities: list[ActivityRow] = []
    wellness: list[WellnessRow] = []
    for record in records:
        if dataset == "activities":
            started_at = _parse_datetime(
                _first(record, "startTimeLocal", "startTimeGMT", "start_time", "start_at", "beginTimestamp")
            )
            activity_date = _parse_date(_first(record, "activityDate", "date", "calendarDate", "summaryDate"))
            if activity_date is None and started_at is not None:
                activity_date = started_at.date()
            duration_seconds = _parse_float(_first(record, "durationSeconds", "duration_seconds", "duration", "elapsedDuration"))
            training_load = _parse_float(_first(record, "trainingLoad", "training_load", "load"))
            if training_load is None and duration_seconds is not None:
                training_load = round(duration_seconds / 60.0, 2)
            activity_id = _first(record, "activityId", "activity_id", "id", "summaryId")
            activity_type = _first(
                record,
                "activityType.typeKey",
                "activityType",
                "activity_type",
                "sport",
            )
            activity_hash_parts = [
                str(activity_id) if activity_id is not None else None,
                started_at.isoformat() if started_at else None,
                str(activity_type) if activity_type is not None else None,
                duration_seconds,
                _parse_float(_first(record, "distanceMeters", "distance_meters", "distance")),
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
                    distance_meters=_parse_float(_first(record, "distanceMeters", "distance_meters", "distance")),
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

    return activities, wellness


def _load_manifests(data_dir: Path) -> list[dict[str, Any]]:
    runs_dir = data_dir / "runs"
    if not runs_dir.exists():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(runs_dir.glob("*.json"))
    ]


def _build_rows(data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    activities: dict[str, ActivityRow] = {}
    wellness: dict[str, WellnessRow] = {}
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
            records = read_records(Path(artifact["stored_path"]), dataset=artifact["dataset"])
            activity_rows, wellness_rows = normalize_dataset(artifact["dataset"], records, manifest["run_id"])
            for row in activity_rows:
                activities[row.record_hash] = row
            for row in wellness_rows:
                wellness[row.record_hash] = row

    return sync_runs, [asdict(row) for row in activities.values()], [asdict(row) for row in wellness.values()]


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


def _insert_rows(
    con: duckdb.DuckDBPyConnection,
    sync_runs: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    wellness: list[dict[str, Any]],
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


def compute_metrics(activities_rows: list[dict[str, Any]], wellness_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    load_by_day: dict[str, float] = {}
    for row in activities_rows:
        if row["activity_date"]:
            load_by_day.setdefault(row["activity_date"], 0.0)
            load_by_day[row["activity_date"]] += float(row["training_load"] or 0.0)

    merged_wellness = _aggregate_wellness(wellness_rows)
    all_dates = sorted(set(load_by_day) | set(merged_wellness))
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
        load_ratio = round(load_7d / load_28d, 3) if load_28d else None
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
                "load_7d": load_7d,
                "load_28d": load_28d,
                "load_ratio_7_28": load_ratio,
                "sleep_hours_7d": sleep_hours_7d,
                "resting_hr_7d": resting_hr_7d,
                "hrv_7d": hrv_7d,
                "progression_delta": progression_delta,
                "fatigue_flag": fatigue_flag,
                "overreaching_flag": overreaching_flag,
            }
        )

    latest = metrics_rows[-1] if metrics_rows else {}
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "latest_day": latest.get("metric_date"),
        "activity_rows": len(activities_rows),
        "wellness_rows": len(wellness_rows),
        "supported_metrics": {
            "load_7d": "Sum of daily activity training load over the trailing 7 days.",
            "load_28d": "Sum of daily activity training load over the trailing 28 days.",
            "load_ratio_7_28": "Trailing 7-day load divided by trailing 28-day load.",
            "sleep_hours_7d": "Average recorded sleep duration over the trailing 7 days.",
            "resting_hr_7d": "Average resting heart rate over the trailing 7 days when available.",
            "hrv_7d": "Average HRV over the trailing 7 days when available.",
            "progression_delta": "Difference between trailing 7-day load and the previous 7-day load.",
            "fatigue_flag": "True when sleep is below 7h or recent HRV is down versus the trailing 28-day baseline.",
            "overreaching_flag": "True when recent load is elevated and recovery signals are degraded.",
        },
        "latest_metrics": latest,
    }
    return metrics_rows, report


def rebuild_analytics(data_dir: Path) -> dict[str, Any]:
    sync_runs, activities_rows, wellness_rows = _build_rows(data_dir)
    db_path = default_db_path(data_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        _ensure_schema(con)
        _insert_rows(con, sync_runs, activities_rows, wellness_rows)
        metrics_rows, report = compute_metrics(activities_rows, wellness_rows)
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
    return {
        "db_path": str(db_path),
        "report_path": str(report_path),
        "sync_runs": len(sync_runs),
        "activity_rows": len(activities_rows),
        "wellness_rows": len(wellness_rows),
        "metric_rows": len(metrics_rows),
        "latest_day": report.get("latest_day"),
    }
