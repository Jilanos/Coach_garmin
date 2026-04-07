from __future__ import annotations

from pathlib import Path

from coach_garmin.analytics import rebuild_analytics
from coach_garmin.contracts import ArtifactRecord, SyncManifest
from coach_garmin.storage import (
    compute_sha256,
    copy_raw_artifact,
    detect_dataset,
    discover_supported_files,
    ensure_data_dirs,
    new_run_id,
    now_utc,
    read_records,
    write_json,
)


def run_import_export(source: Path, data_dir: Path, run_label: str | None = None) -> dict[str, object]:
    if not source.exists():
        raise FileNotFoundError(f"Source path does not exist: {source}")

    ensure_data_dirs(data_dir)
    run_id = new_run_id()
    started_at = now_utc()
    supported_files, unsupported_files = discover_supported_files(source)
    if not supported_files:
        raise ValueError(f"No supported Garmin export files found under {source}")

    artifacts: list[ArtifactRecord] = []
    datasets_seen: set[str] = set()
    total_records = 0

    for candidate in supported_files:
        dataset = detect_dataset(candidate)
        if dataset is None:
            continue
        records = read_records(candidate)
        stored_path = copy_raw_artifact(candidate, data_dir, run_id, dataset)
        artifacts.append(
            ArtifactRecord(
                dataset=dataset,
                source_path=str(candidate.resolve()),
                stored_path=str(stored_path.resolve()),
                file_format=candidate.suffix.lower().lstrip("."),
                record_count=len(records),
                content_hash=compute_sha256(candidate),
            )
        )
        datasets_seen.add(dataset)
        total_records += len(records)

    manifest = SyncManifest(
        run_id=run_id,
        run_label=run_label or "manual-import",
        source_kind="manual-export",
        source_path=str(source.resolve()),
        started_at=started_at.isoformat(),
        finished_at=now_utc().isoformat(),
        artifact_count=len(artifacts),
        dataset_count=len(datasets_seen),
        total_records=total_records,
        artifacts=artifacts,
    )
    manifest_path = data_dir / "runs" / f"{run_id}.json"
    write_json(manifest_path, manifest.to_dict())
    analytics_summary = rebuild_analytics(data_dir)

    return {
        "run_id": run_id,
        "manifest_path": str(manifest_path),
        "artifacts_imported": len(artifacts),
        "datasets_seen": sorted(datasets_seen),
        "total_records": total_records,
        "unsupported_files": [str(path) for path in unsupported_files],
        "analytics": analytics_summary,
    }
