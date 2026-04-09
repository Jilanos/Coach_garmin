from __future__ import annotations

from pathlib import Path

from coach_garmin.analytics import rebuild_analytics
from coach_garmin.contracts import ArtifactRecord, SyncManifest
from coach_garmin.storage import (
    compute_sha256,
    copy_raw_artifact,
    discover_supported_artifacts,
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
    supported_artifacts, unsupported_files = discover_supported_artifacts(source)
    if not supported_artifacts:
        raise ValueError(f"No supported Garmin export files found under {source}")

    artifacts: list[ArtifactRecord] = []
    datasets_seen: set[str] = set()
    total_records = 0

    for artifact in supported_artifacts:
        records = read_records(artifact.source_path, dataset=artifact.dataset)
        stored_path = copy_raw_artifact(artifact.source_path, data_dir, run_id, artifact.dataset)
        artifacts.append(
            ArtifactRecord(
                dataset=artifact.dataset,
                source_path=str(artifact.source_path.resolve()),
                stored_path=str(stored_path.resolve()),
                file_format=artifact.source_path.suffix.lower().lstrip("."),
                record_count=len(records),
                content_hash=compute_sha256(artifact.source_path),
                metadata={
                    "source_filename": artifact.source_path.name,
                    "source_parent": artifact.source_path.parent.name,
                    "source_kind": "manual-export",
                },
            )
        )
        datasets_seen.add(artifact.dataset)
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
        "coverage_report_path": analytics_summary.get("coverage_report_path"),
        "analytics": analytics_summary,
    }
