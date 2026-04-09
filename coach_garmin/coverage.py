from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any


def build_feature_coverage_report(
    *,
    sync_runs: list[dict[str, Any]],
    artifact_inventory_rows: list[dict[str, Any]],
    activities_rows: list[dict[str, Any]],
    wellness_rows: list[dict[str, Any]],
    acute_load_rows: list[dict[str, Any]],
    training_history_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
    heart_rate_zone_rows: list[dict[str, Any]],
    lineage_rows: list[dict[str, Any]],
    metrics_rows: list[dict[str, Any]],
    latest_report: dict[str, Any],
) -> dict[str, Any]:
    dataset_counts = Counter(str(row.get("dataset", "")) for row in artifact_inventory_rows if row.get("dataset"))
    source_kind_counts = Counter(str(run.get("source_kind", "")) for run in sync_runs if run.get("source_kind"))

    latest_metrics = latest_report.get("latest_metrics", {}) if isinstance(latest_report, dict) else {}
    latest_metric_keys = set(latest_metrics) if isinstance(latest_metrics, dict) else set()

    normalized_table_counts = {
        "activities": len(activities_rows),
        "wellness_daily": len(wellness_rows),
        "acute_load_daily": len(acute_load_rows),
        "training_history_daily": len(training_history_rows),
        "profile_snapshots": len(profile_rows),
        "heart_rate_zones": len(heart_rate_zone_rows),
        "normalized_lineage": len(lineage_rows),
        "derived_daily_metrics": len(metrics_rows),
    }

    coach_signal_rules: list[tuple[str, bool]] = [
        ("activities_history", len(activities_rows) > 0),
        ("running_history", any(str(row.get("activity_type", "")).lower() in {"running", "trail_running"} for row in activities_rows)),
        ("latest_metrics", bool(latest_metric_keys)),
        ("acute_load", len(acute_load_rows) > 0 or "load_7d" in latest_metric_keys),
        ("training_history", len(training_history_rows) > 0),
        ("profile", len(profile_rows) > 0),
        ("heart_rate_zones", len(heart_rate_zone_rows) > 0),
        ("lineage", len(lineage_rows) > 0),
        ("fatigue_flag", "fatigue_flag" in latest_metric_keys),
        ("overreaching_flag", "overreaching_flag" in latest_metric_keys),
        ("sleep_hours_7d", "sleep_hours_7d" in latest_metric_keys),
        ("resting_hr_7d", "resting_hr_7d" in latest_metric_keys),
        ("hrv_7d", "hrv_7d" in latest_metric_keys),
    ]
    available_coach_signals = [name for name, is_available in coach_signal_rules if is_available]
    missing_coach_signals = [name for name, is_available in coach_signal_rules if not is_available]

    normalized_presence = {
        table: {"rows": count, "available": count > 0}
        for table, count in normalized_table_counts.items()
    }

    feature_coverage = {
        "derived_daily_metrics": {
            "rows": len(metrics_rows),
            "available": len(metrics_rows) > 0,
            "latest_keys": sorted(latest_metric_keys),
        },
        "wellness_signals": {
            "rows": len(wellness_rows),
            "available": len(wellness_rows) > 0,
        },
        "performance_signals": {
            "acute_load_rows": len(acute_load_rows),
            "training_history_rows": len(training_history_rows),
            "heart_rate_zone_rows": len(heart_rate_zone_rows),
            "available": any(
                [len(acute_load_rows) > 0, len(training_history_rows) > 0, len(heart_rate_zone_rows) > 0]
            ),
        },
    }

    total_signals = len(coach_signal_rules)
    available_ratio = round(len(available_coach_signals) / total_signals, 3) if total_signals else 0.0

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "raw": {
            "sync_runs": len(sync_runs),
            "artifacts": len(artifact_inventory_rows),
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "source_kind_counts": dict(sorted(source_kind_counts.items())),
        },
        "normalized": normalized_presence,
        "features": feature_coverage,
        "coach": {
            "available_signals": available_coach_signals,
            "missing_signals": missing_coach_signals,
            "coverage_ratio": available_ratio,
            "latest_metric_keys": sorted(latest_metric_keys),
        },
        "lineage": {
            "rows": len(lineage_rows),
            "available": len(lineage_rows) > 0,
        },
    }
