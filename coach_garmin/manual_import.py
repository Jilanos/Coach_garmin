from __future__ import annotations

from pathlib import Path

from coach_garmin.analytics import rebuild_analytics
from coach_garmin.contracts import ArtifactRecord, SyncManifest
from coach_garmin.storage import (
    compute_sha256,
    copy_raw_artifact,
    discover_supported_artifacts,
    ensure_data_dirs,
    materialize_source_root,
    new_run_id,
    now_utc,
    read_records,
    write_json,
)
from coach_garmin.sync_state import load_sync_summary, lookup_artifact_index, record_sync_run


def run_import_export(source: Path, data_dir: Path, run_label: str | None = None) -> dict[str, object]:
    if not source.exists():
        raise FileNotFoundError(f"Source path does not exist: {source}")

    ensure_data_dirs(data_dir)
    state_summary_before = load_sync_summary(data_dir)
    run_id = new_run_id()
    started_at = now_utc()
    with materialize_source_root(source) as source_root:
        supported_artifacts, unsupported_files = discover_supported_artifacts(source_root)
        if not supported_artifacts:
            raise ValueError(f"No supported Garmin export files found under {source}")

        artifacts: list[ArtifactRecord] = []
        datasets_seen: set[str] = set()
        total_records = 0
        reused_artifacts = 0

        for artifact in supported_artifacts:
            records = read_records(artifact.source_path, dataset=artifact.dataset)
            content_hash = compute_sha256(artifact.source_path)
            known_artifact = lookup_artifact_index(data_dir, artifact.dataset, content_hash)
            if known_artifact and Path(str(known_artifact["stored_path"])).exists():
                stored_path = Path(str(known_artifact["stored_path"]))
                storage_state = "reused"
                reused_artifacts += 1
            else:
                stored_path = copy_raw_artifact(artifact.source_path, data_dir, run_id, artifact.dataset)
                storage_state = "copied"

            artifacts.append(
                ArtifactRecord(
                    dataset=artifact.dataset,
                    source_path=str(artifact.source_path.resolve()),
                    stored_path=str(stored_path.resolve()),
                    file_format=artifact.source_path.suffix.lower().lstrip("."),
                    record_count=len(records),
                    content_hash=content_hash,
                    metadata={
                        "source_filename": artifact.source_path.name,
                        "source_parent": artifact.source_path.parent.name,
                        "source_kind": "manual-export",
                        "storage_state": storage_state,
                        "baseline_source_path": str(source.resolve()),
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
            metadata={
                "supported_artifacts": len(artifacts),
                "reused_artifacts": reused_artifacts,
                "pending_files": len(unsupported_files),
                "state_before": state_summary_before,
            },
            artifacts=artifacts,
        )
    pending_count = len(unsupported_files)
    manifest_path = data_dir / "runs" / f"{run_id}.json"
    write_json(manifest_path, manifest.to_dict())
    state_summary_after = record_sync_run(
        data_dir,
        manifest=manifest.to_dict(),
        artifacts=[artifact.to_dict() for artifact in artifacts],
        pending_count=pending_count,
    )
    analytics_summary = rebuild_analytics(data_dir)

    return {
        "run_id": run_id,
        "manifest_path": str(manifest_path),
        "artifacts_imported": len(artifacts),
        "datasets_seen": sorted(datasets_seen),
        "total_records": total_records,
        "reused_artifacts": reused_artifacts,
        "pending_count": pending_count,
        "unsupported_files": [str(path) for path in unsupported_files],
        "coverage_report_path": analytics_summary.get("coverage_report_path"),
        "sync_state": state_summary_after,
        "analytics": analytics_summary,
    }
