from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coach_garmin.config import DATASET_ALIASES, DEFAULT_DATA_DIR, DEFAULT_DB_PATH, DEFAULT_REPORT_PATH


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


def read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                return [item for item in payload["data"] if isinstance(item, dict)]
            if isinstance(payload.get("rows"), list):
                return [item for item in payload["rows"] if isinstance(item, dict)]
            return [payload]
        raise ValueError(f"Unsupported JSON payload in {path}")

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    raise ValueError(f"Unsupported file type for {path}")


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


def discover_supported_files(source: Path) -> tuple[list[Path], list[Path]]:
    if source.is_file():
        supported = [source] if detect_dataset(source) else []
        unsupported = [] if supported else [source]
        return supported, unsupported

    supported: list[Path] = []
    unsupported: list[Path] = []
    for candidate in sorted(source.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in {".json", ".csv"}:
            continue
        if detect_dataset(candidate):
            supported.append(candidate)
        else:
            unsupported.append(candidate)
    return supported, unsupported


def default_db_path(data_dir: Path) -> Path:
    if data_dir == DEFAULT_DATA_DIR:
        return DEFAULT_DB_PATH
    return data_dir / "normalized" / "coach_garmin.duckdb"


def default_report_path(data_dir: Path) -> Path:
    if data_dir == DEFAULT_DATA_DIR:
        return DEFAULT_REPORT_PATH
    return data_dir / "reports" / "latest_metrics.json"
