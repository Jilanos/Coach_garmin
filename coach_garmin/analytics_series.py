from __future__ import annotations

import math
from typing import Any

from coach_garmin.analytics_support import (
    _first,
    _pace_min_per_km,
    _parse_float,
    _safe_json_loads,
)


def _percentile(values: list[float], percentile: float) -> float | None:
    filtered = sorted(value for value in values if value is not None)
    if not filtered:
        return None
    if len(filtered) == 1:
        return round(float(filtered[0]), 2)
    rank = (len(filtered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(float(filtered[int(rank)]), 2)
    lower_value = float(filtered[lower])
    upper_value = float(filtered[upper])
    return round(lower_value + (upper_value - lower_value) * (rank - lower), 2)


def _weighted_median(samples: list[tuple[float, float]]) -> float | None:
    filtered = [(float(value), max(float(weight), 0.0)) for value, weight in samples if value is not None and weight is not None]
    if not filtered:
        return None
    filtered.sort(key=lambda item: item[0])
    total_weight = sum(weight for _, weight in filtered)
    if total_weight <= 0:
        return round(filtered[len(filtered) // 2][0], 2)
    target = total_weight / 2.0
    cumulative = 0.0
    for value, weight in filtered:
        cumulative += weight
        if cumulative >= target:
            return round(value, 2)
    return round(filtered[-1][0], 2)


def _weighted_isotonic_non_decreasing(values: list[float], weights: list[float]) -> list[float]:
    if not values:
        return []
    blocks: list[list[float]] = []
    for value, weight in zip(values, weights):
        current_value = float(value)
        current_weight = max(float(weight), 0.0) or 1.0
        blocks.append([current_value, current_weight, 1.0])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            right_value, right_weight, right_count = blocks.pop()
            left_value, left_weight, left_count = blocks.pop()
            merged_weight = left_weight + right_weight
            merged_value = ((left_value * left_weight) + (right_value * right_weight)) / merged_weight
            blocks.append([merged_value, merged_weight, left_count + right_count])
    result: list[float] = []
    for value, _, count in blocks:
        result.extend([round(value, 2)] * max(1, int(count)))
    return result[: len(values)]


def _unwrap_split_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    current: Any = candidate
    for key in (
        "splitJsonData",
        "splitData",
        "measurement",
        "metrics",
        "data",
        "lapData",
        "lap",
    ):
        if isinstance(current, dict) and isinstance(current.get(key), dict):
            current = current[key]
    return current if isinstance(current, dict) else candidate


def _extract_running_cadence_spm(record: dict[str, Any]) -> float | None:
    double_cadence = _parse_float(
        _first(
            record,
            "avgDoubleCadence",
            "averageDoubleCadence",
            "WEIGHTED_MEAN_DOUBLE_CADENCE",
            "WEIGHTED_MEAN_DOUBLECADENCE",
            "doubleCadence",
        )
    )
    if double_cadence is not None:
        return round(double_cadence, 2)
    run_cadence = _parse_float(
        _first(
            record,
            "avgRunCadence",
            "averageRunCadence",
            "WEIGHTED_MEAN_RUNCADENCE",
            "WEIGHTED_MEAN_RUN_CADENCE",
            "runCadence",
            "cadence",
        )
    )
    if run_cadence is None:
        return None
    return round(run_cadence * 2.0, 2) if run_cadence <= 120 else round(run_cadence, 2)


def _is_running_type(activity_type: str | None) -> bool:
    normalized = (activity_type or "").lower()
    return normalized in {"running", "trail_running", "treadmill_running", "indoor_running"}


def _is_cycling_type(activity_type: str | None) -> bool:
    normalized = (activity_type or "").lower()
    return normalized in {
        "cycling",
        "bike",
        "biking",
        "road_biking",
        "mountain_biking",
        "indoor_cycling",
        "virtual_ride",
        "ebike",
        "gravel_cycling",
    }


def _is_strength_type(activity_type: str | None) -> bool:
    normalized = (activity_type or "").lower()
    return normalized in {
        "strength_training",
        "strength",
        "weight_training",
        "bodyweight",
        "cardio",
        "workout",
        "core_training",
        "pilates",
        "yoga",
    }


def _activity_curve_points(activity_row: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _safe_json_loads(activity_row.get("raw_payload"))
    if not payload:
        return []
    activity_type = str(activity_row.get("activity_type") or "").lower()
    if activity_type not in {"running", "trail_running"}:
        return []

    points: list[dict[str, Any]] = []
    started_at = activity_row.get("started_at")
    activity_date = activity_row.get("activity_date")
    summary_duration = _parse_float(activity_row.get("duration_seconds"))
    summary_distance = _parse_float(activity_row.get("distance_meters"))
    summary_hr = _parse_float(activity_row.get("average_hr"))
    summary_cadence = _extract_running_cadence_spm(payload)
    if (
        summary_duration is not None
        and summary_distance is not None
        and summary_duration >= 600
        and summary_distance >= 2000
        and summary_hr is not None
    ):
        pace = _pace_min_per_km(summary_duration / 60.0, summary_distance / 1000.0)
        if pace is not None and 2.5 <= pace <= 12.0:
            points.append(
                {
                    "pace_min_per_km": round(pace, 2),
                    "heart_rate": round(summary_hr, 1),
                    "cadence_spm": round(summary_cadence, 1) if summary_cadence is not None else None,
                    "duration_seconds": round(summary_duration, 1),
                    "distance_meters": round(summary_distance, 1),
                    "activity_date": activity_date,
                    "started_at": started_at,
                    "point_type": "summary",
                    "weight": max(summary_duration, 300.0),
                }
            )

    candidate_lists = []
    for key in ("splitSummaries", "splits", "lapDTOs", "activitySplits", "laps"):
        value = payload.get(key)
        if isinstance(value, list):
            candidate_lists.extend(item for item in value if isinstance(item, dict))

    for candidate in candidate_lists:
        item = _unwrap_split_candidate(candidate)
        duration_seconds = _parse_float(
            _first(
                item,
                "elapsedDuration",
                "durationSeconds",
                "duration",
                "splitTimeSeconds",
                "splitTime",
                "movingDuration",
                "time",
            )
        )
        distance_meters = _parse_float(
            _first(
                item,
                "distanceMeters",
                "distance",
                "splitDistance",
                "length",
                "distanceMetersCovered",
            )
        )
        if duration_seconds is not None and duration_seconds < 120 and (distance_meters is None or distance_meters < 500):
            continue
        speed_mps = _parse_float(
            _first(item, "WEIGHTED_MEAN_SPEED", "weightedMeanSpeed", "avgSpeed", "averageSpeed", "speed")
        )
        pace = None
        if duration_seconds is not None and distance_meters is not None and duration_seconds > 0 and distance_meters > 0:
            pace = _pace_min_per_km(duration_seconds / 60.0, distance_meters / 1000.0)
        elif speed_mps is not None and speed_mps > 0:
            pace = 16.6666667 / speed_mps
        heart_rate = _parse_float(
            _first(
                item,
                "WEIGHTED_MEAN_HEARTRATE",
                "weightedMeanHeartrate",
                "averageHR",
                "averageHr",
                "avgHr",
                "heartRate",
                "hr",
            )
        )
        cadence = _extract_running_cadence_spm(item)
        if pace is None or heart_rate is None:
            continue
        if not (2.5 <= pace <= 12.0 and 60 <= heart_rate <= 220):
            continue
        if cadence is not None and not (50 <= cadence <= 220):
            cadence = None
        points.append(
            {
                "pace_min_per_km": round(pace, 2),
                "heart_rate": round(heart_rate, 1),
                "cadence_spm": round(cadence, 1) if cadence is not None else None,
                "duration_seconds": round(duration_seconds, 1) if duration_seconds is not None else None,
                "distance_meters": round(distance_meters, 1) if distance_meters is not None else None,
                "activity_date": activity_date,
                "started_at": started_at,
                "point_type": "split",
                "weight": max(duration_seconds or 0.0, 90.0),
            }
        )
    return points


def _build_pace_hr_curve(points: list[dict[str, Any]], max_points: int = 18) -> list[dict[str, Any]]:
    valid_points = [
        point
        for point in points
        if point.get("pace_min_per_km") is not None and point.get("heart_rate") is not None
    ]
    if len(valid_points) < 3:
        return []

    paces = [float(point["pace_min_per_km"]) for point in valid_points]
    hr_values = [float(point["heart_rate"]) for point in valid_points]
    cadence_values = [float(point["cadence_spm"]) for point in valid_points if point.get("cadence_spm") is not None]
    pace_low = _percentile(paces, 0.1) or min(paces)
    pace_high = _percentile(paces, 0.9) or max(paces)
    if pace_high <= pace_low:
        pace_low, pace_high = min(paces), max(paces)
    pace_low = round(float(pace_low), 2)
    pace_high = round(float(pace_high), 2)
    if pace_high <= pace_low:
        pace_high = round(pace_low + 0.25, 2)
    bin_width = max(0.15, round((pace_high - pace_low) / max(6, min(max_points, len(valid_points))), 2))
    bins: dict[float, dict[str, Any]] = {}
    for point in valid_points:
        pace = float(point["pace_min_per_km"])
        clamped_pace = min(max(pace, pace_low), pace_high)
        bin_key = round(round(clamped_pace / bin_width) * bin_width, 2)
        bucket = bins.setdefault(
            bin_key,
            {"pace_samples": [], "hr_samples": [], "cadence_samples": [], "weight": 0.0, "point_count": 0},
        )
        weight = max(float(point.get("weight") or 1.0), 1.0)
        bucket["pace_samples"].append((pace, weight))
        bucket["hr_samples"].append((float(point["heart_rate"]), weight))
        cadence = point.get("cadence_spm")
        if cadence is not None:
            bucket["cadence_samples"].append((float(cadence), weight))
        bucket["weight"] += weight
        bucket["point_count"] += 1

    ordered_bins = sorted(bins.items(), key=lambda item: item[0], reverse=True)
    raw_hr = []
    raw_weights = []
    curve_rows: list[dict[str, Any]] = []
    for pace_bin, bucket in ordered_bins:
        hr_value = _weighted_median(bucket["hr_samples"])
        if hr_value is None:
            continue
        raw_hr.append(hr_value)
        raw_weights.append(bucket["weight"] or 1.0)
        curve_rows.append(
            {
                "pace_min_per_km": round(pace_bin, 2),
                "heart_rate": round(hr_value, 1),
                "cadence_spm": _weighted_median(bucket["cadence_samples"]),
                "support": round(bucket["weight"], 1),
                "point_count": bucket["point_count"],
            }
        )

    if len(curve_rows) < 3:
        return []

    smoothed_hr = _weighted_isotonic_non_decreasing(raw_hr, raw_weights)
    for index, row in enumerate(curve_rows):
        if index < len(smoothed_hr):
            row["heart_rate"] = round(float(smoothed_hr[index]), 1)
        zone = int(
            min(
                5,
                max(
                    1,
                    math.ceil(((row["heart_rate"] - min(raw_hr)) / max(max(raw_hr) - min(raw_hr), 1.0)) * 5),
                ),
            )
        )
        row["zone"] = zone
    return curve_rows[:max_points]


def _build_pace_hr_curve_diagnostics(points: list[dict[str, Any]], curve: list[dict[str, Any]]) -> dict[str, Any]:
    valid_points = [
        point
        for point in points
        if point.get("pace_min_per_km") is not None and point.get("heart_rate") is not None
    ]
    summary = {
        "input_points": len(points),
        "valid_points": len(valid_points),
        "curve_points": len(curve),
        "missing_pace_or_hr": 0,
        "missing_cadence": 0,
        "stability_threshold": {
            "min_points": 3,
            "min_duration_seconds": 600,
            "min_distance_meters": 2000,
        },
        "ready": len(curve) >= 3,
    }
    for point in points:
        if point.get("pace_min_per_km") is None or point.get("heart_rate") is None:
            summary["missing_pace_or_hr"] += 1
        if point.get("cadence_spm") is None:
            summary["missing_cadence"] += 1
    if not summary["ready"]:
        reasons = []
        if len(valid_points) < 3:
            reasons.append("Il faut au moins 3 sorties running stables avec allure et FC exploitables.")
        if summary["missing_pace_or_hr"]:
            reasons.append(f"{summary['missing_pace_or_hr']} activitÃ©(s) running n'ont pas d'allure ou de FC exploitable.")
        if summary["missing_cadence"]:
            reasons.append(f"{summary['missing_cadence']} activitÃ©(s) running n'ont pas de cadence exploitable.")
        reasons.append("Les Ã©chauffements, retours au calme et fractionnÃ©s trop courts sont sous-pondÃ©rÃ©s ou exclus.")
        reasons.append("Une activitÃ© doit durer au moins 10 min et 2 km environ pour peser dans la courbe.")
        summary["blocking_reasons"] = reasons
    else:
        summary["blocking_reasons"] = []
    return summary


def _build_cadence_daily_series(activities_rows: list[dict[str, Any]]) -> dict[str, float]:
    by_day: dict[str, list[tuple[float, float]]] = {}
    for row in activities_rows:
        if not _is_running_type(row["activity_type"]):
            continue
        activity_date = row.get("activity_date")
        cadence = _extract_running_cadence_spm(_safe_json_loads(row.get("raw_payload")))
        if activity_date is None or cadence is None:
            continue
        duration_seconds = _parse_float(row.get("duration_seconds")) or 0.0
        if duration_seconds <= 0:
            continue
        by_day.setdefault(str(activity_date), []).append((cadence, max(duration_seconds, 60.0)))
    daily: dict[str, float] = {}
    for metric_date, samples in by_day.items():
        total_weight = sum(weight for _, weight in samples)
        if total_weight <= 0:
            continue
        weighted = sum(value * weight for value, weight in samples) / total_weight
        daily[metric_date] = round(weighted, 1)
    return daily


def _build_running_daily_series(activities_rows: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, float]]:
    pace_by_day: dict[str, list[tuple[float, float]]] = {}
    hr_by_day: dict[str, list[tuple[float, float]]] = {}
    for row in activities_rows:
        if not _is_running_type(row.get("activity_type")):
            continue
        activity_date = row.get("activity_date")
        if activity_date is None:
            continue
        duration_seconds = _parse_float(row.get("duration_seconds")) or 0.0
        distance_meters = _parse_float(row.get("distance_meters")) or 0.0
        if duration_seconds <= 0 or distance_meters <= 0:
            continue
        pace = _pace_min_per_km(duration_seconds / 60.0, distance_meters / 1000.0)
        if pace is not None and 2.5 <= pace <= 12.0:
            pace_by_day.setdefault(str(activity_date), []).append((pace, max(duration_seconds, 60.0)))
        avg_hr = _parse_float(row.get("average_hr"))
        if avg_hr is not None and 60 <= avg_hr <= 220:
            hr_by_day.setdefault(str(activity_date), []).append((avg_hr, max(duration_seconds, 60.0)))
    pace_daily: dict[str, float] = {}
    hr_daily: dict[str, float] = {}
    for metric_date, samples in pace_by_day.items():
        total_weight = sum(weight for _, weight in samples)
        if total_weight <= 0:
            continue
        pace_daily[metric_date] = round(sum(value * weight for value, weight in samples) / total_weight, 2)
    for metric_date, samples in hr_by_day.items():
        total_weight = sum(weight for _, weight in samples)
        if total_weight <= 0:
            continue
        hr_daily[metric_date] = round(sum(value * weight for value, weight in samples) / total_weight, 1)
    return pace_daily, hr_daily


def _extract_zone_thresholds(heart_rate_zone_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = heart_rate_zone_rows or []
    row = next((item for item in rows if isinstance(item, dict)), {})
    floors = [
        _parse_float(row.get("zone1_floor")),
        _parse_float(row.get("zone2_floor")),
        _parse_float(row.get("zone3_floor")),
        _parse_float(row.get("zone4_floor")),
        _parse_float(row.get("zone5_floor")),
    ]
    max_hr = _parse_float(row.get("max_hr"))
    resting_hr = _parse_float(row.get("resting_hr"))
    return {
        "resting_hr": resting_hr,
        "max_hr": max_hr,
        "zone_floors": floors,
    }


def _zone_bucket_for_heart_rate(value: float | None, thresholds: dict[str, Any]) -> int | None:
    if value is None:
        return None
    floors = [floor for floor in thresholds.get("zone_floors", []) if floor is not None]
    if len(floors) >= 5:
        if value < floors[1]:
            return 1
        if value < floors[2]:
            return 2
        if value < floors[3]:
            return 3
        if value < floors[4]:
            return 4
        return 5
    max_hr = _parse_float(thresholds.get("max_hr"))
    if max_hr is not None and max_hr > 0:
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
    if value < 130:
        return 1
    if value < 145:
        return 2
    if value < 160:
        return 3
    if value < 175:
        return 4
    return 5


def _build_zone_duration_distribution(
    activities_rows: list[dict[str, Any]],
    thresholds: dict[str, Any],
    predicate,
) -> dict[str, Any]:
    zone_seconds = {f"zone_{index}": 0.0 for index in range(1, 6)}
    total_seconds = 0.0
    source_count = 0
    for row in activities_rows:
        if not predicate(row.get("activity_type")):
            continue
        duration_seconds = _parse_float(row.get("duration_seconds")) or 0.0
        avg_hr = _parse_float(row.get("average_hr"))
        zone = _zone_bucket_for_heart_rate(avg_hr, thresholds)
        if duration_seconds <= 0 or zone is None:
            continue
        zone_seconds[f"zone_{zone}"] += duration_seconds
        total_seconds += duration_seconds
        source_count += 1
    distribution: list[dict[str, Any]] = []
    for index in range(1, 6):
        seconds = zone_seconds[f"zone_{index}"]
        share = (seconds / total_seconds) if total_seconds else None
        distribution.append(
            {
                "zone": index,
                "seconds": round(seconds, 1),
                "minutes": round(seconds / 60.0, 1),
                "share": round(share, 3) if share is not None else None,
            }
        )
    return {
        "distribution": distribution,
        "total_seconds": round(total_seconds, 1),
        "source_count": source_count,
        "method": "Activity duration weighted by average HR zone",
    }
