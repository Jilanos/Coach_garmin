from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coach_garmin.config import DATASET_ALIASES, DEFAULT_DATA_DIR, DEFAULT_DB_PATH, DEFAULT_REPORT_PATH


@dataclass(frozen=True, slots=True)
class SupportedArtifact:
    source_path: Path
    dataset: str


def ensure_data_dirs(data_dir: Path) -> dict[str, Path]:
    paths = {
        "root": data_dir,
        "raw": data_dir / "raw",
        "runs": data_dir / "runs",
        "normalized": data_dir / "normalized",
        "reports": data_dir / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_run_id() -> str:
    return now_utc().strftime("sync_%Y%m%dT%H%M%S%fZ")


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_or_csv(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    raise ValueError(f"Unsupported file type for {path}")


def _flatten_dict_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        if isinstance(payload.get("rows"), list):
            return [item for item in payload["rows"] if isinstance(item, dict)]
        return [payload]
    raise ValueError("Unsupported payload")


def _extract_health_metric(record: dict[str, Any], metric_type: str) -> float | None:
    metrics = record.get("metrics")
    if not isinstance(metrics, list):
        return None
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        if str(metric.get("type", "")).upper() != metric_type:
            continue
        value = metric.get("value")
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None
    return None


def read_records(path: Path, dataset: str | None = None) -> list[dict[str, Any]]:
    payload = _load_json_or_csv(path)
    if dataset is None:
        return _flatten_dict_records(payload)

    lower_name = path.name.lower()

    if dataset == "activities" and "summarizedactivities" in lower_name:
        rows: list[dict[str, Any]] = []
        for item in _flatten_dict_records(payload):
            exported = item.get("summarizedActivitiesExport")
            if isinstance(exported, list):
                rows.extend([entry for entry in exported if isinstance(entry, dict)])
            else:
                rows.append(item)
        return rows

    if dataset == "sleep":
        return _flatten_dict_records(payload)

    if dataset in {"steps", "heart_rate", "stress"} and "udsfile" in lower_name:
        rows = _flatten_dict_records(payload)
        if dataset == "steps":
            return rows
        if dataset == "heart_rate":
            return rows
        transformed: list[dict[str, Any]] = []
        for row in rows:
            stress = row.get("allDayStress")
            if not isinstance(stress, dict):
                continue
            aggregators = stress.get("aggregatorList")
            if not isinstance(aggregators, list):
                continue
            total = next(
                (
                    item
                    for item in aggregators
                    if isinstance(item, dict) and str(item.get("type", "")).upper() == "TOTAL"
                ),
                None,
            )
            if total is None:
                continue
            transformed.append(
                {
                    "calendarDate": row.get("calendarDate"),
                    "stressLevel": total.get("averageStressLevel"),
                }
            )
        return transformed

    if dataset == "hrv" and "healthstatusdata" in lower_name:
        transformed = []
        for row in _flatten_dict_records(payload):
            transformed.append(
                {
                    "calendarDate": row.get("calendarDate"),
                    "hrv": _extract_health_metric(row, "HRV"),
                }
            )
        return transformed

    if dataset in {"acute_load", "training_history", "heart_rate_zones"}:
        return _flatten_dict_records(payload)

    if dataset in {"profile", "device_raw", "settings_raw"}:
        rows = _flatten_dict_records(payload)
        return rows if rows else [{"raw_payload": payload}]

    return _flatten_dict_records(payload)


def copy_raw_artifact(source: Path, data_dir: Path, run_id: str, dataset: str) -> Path:
    destination_dir = data_dir / "raw" / run_id / dataset
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    shutil.copy2(source, destination)
    return destination


def write_raw_payload(
    data_dir: Path,
    run_id: str,
    dataset: str,
    filename: str,
    payload: Any,
) -> Path:
    destination_dir = data_dir / "raw" / run_id / dataset
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    write_json(destination, payload)
    return destination


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def detect_dataset(path: Path) -> str | None:
    candidates = [path.stem.lower(), path.parent.name.lower()]
    normalized_candidates: list[str] = []
    for candidate in candidates:
        normalized_candidates.append(candidate.replace("-", "").replace("_", "").replace(" ", ""))
        normalized_candidates.append(candidate.replace("-", "_").replace(" ", "_"))
    for candidate in normalized_candidates:
        if candidate in DATASET_ALIASES:
            return DATASET_ALIASES[candidate]
    return None


def detect_datasets(path: Path) -> list[str]:
    direct = detect_dataset(path)
    if direct is not None:
        return [direct]

    lower_name = path.name.lower()
    if "summarizedactivities" in lower_name:
        return ["activities"]
    if "sleepdata" in lower_name:
        return ["sleep"]
    if "healthstatusdata" in lower_name:
        return ["hrv"]
    if "metricsacutetrainingload" in lower_name:
        return ["acute_load"]
    if "traininghistory" in lower_name:
        return ["training_history"]
    if "user_profile" in lower_name or "social-profile" in lower_name:
        return ["profile"]
    if "heartratezones" in lower_name:
        return ["heart_rate_zones"]
    if "devicebackups" in lower_name or "devicesandcontent" in lower_name:
        return ["device_raw"]
    if "user_settings" in lower_name or "user_reminders" in lower_name:
        return ["settings_raw"]
    if "udsfile" in lower_name:
        return ["heart_rate", "steps", "stress"]
    return []


def discover_supported_artifacts(source: Path) -> tuple[list[SupportedArtifact], list[Path]]:
    if source.is_file():
        datasets = detect_datasets(source)
        if not datasets:
            return [], [source]
        return [SupportedArtifact(source_path=source, dataset=dataset) for dataset in datasets], []

    supported: list[SupportedArtifact] = []
    unsupported: list[Path] = []
    for candidate in sorted(source.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in {".json", ".csv"}:
            continue
        datasets = detect_datasets(candidate)
        if datasets:
            supported.extend(SupportedArtifact(source_path=candidate, dataset=dataset) for dataset in datasets)
        else:
            unsupported.append(candidate)
    return supported, unsupported


def discover_supported_files(source: Path) -> tuple[list[Path], list[Path]]:
    supported_artifacts, unsupported = discover_supported_artifacts(source)
    supported_paths: list[Path] = []
    seen: set[Path] = set()
    for artifact in supported_artifacts:
        if artifact.source_path in seen:
            continue
        supported_paths.append(artifact.source_path)
        seen.add(artifact.source_path)
    return supported_paths, unsupported


def default_db_path(data_dir: Path) -> Path:
    if data_dir == DEFAULT_DATA_DIR:
        return DEFAULT_DB_PATH
    return data_dir / "normalized" / "coach_garmin.duckdb"


def default_report_path(data_dir: Path) -> Path:
    if data_dir == DEFAULT_DATA_DIR:
        return DEFAULT_REPORT_PATH
    return data_dir / "reports" / "latest_metrics.json"
