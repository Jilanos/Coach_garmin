from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from coach_garmin.config import DEFAULT_STATE_DB_PATH
from coach_garmin.storage import ensure_data_dirs


def default_state_db_path(data_dir: Path) -> Path:
    if data_dir == DEFAULT_STATE_DB_PATH.parent.parent:
        return DEFAULT_STATE_DB_PATH
    return data_dir / "state" / "coach_garmin.sqlite3"


def _connect(data_dir: Path) -> sqlite3.Connection:
    ensure_data_dirs(data_dir)
    db_path = default_state_db_path(data_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    _ensure_schema(con)
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            run_id TEXT PRIMARY KEY,
            run_label TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_path TEXT NOT NULL,
            state TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            dataset_count INTEGER NOT NULL,
            artifact_count INTEGER NOT NULL,
            total_records INTEGER NOT NULL,
            new_artifact_count INTEGER NOT NULL,
            reused_artifact_count INTEGER NOT NULL,
            pending_count INTEGER NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_artifacts (
            run_id TEXT NOT NULL,
            dataset TEXT NOT NULL,
            source_path TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            file_format TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            state TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            seen_at TEXT NOT NULL,
            PRIMARY KEY (run_id, dataset, content_hash)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS artifact_index (
            dataset TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            source_path TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            file_format TEXT NOT NULL,
            record_count INTEGER NOT NULL,
            source_kind TEXT NOT NULL,
            last_run_id TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            PRIMARY KEY (dataset, content_hash)
        )
        """
    )
    con.commit()


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def lookup_artifact_index(data_dir: Path, dataset: str, content_hash: str) -> dict[str, Any] | None:
    db_path = default_state_db_path(data_dir)
    if not db_path.exists():
        return None
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT dataset, content_hash, source_path, stored_path, file_format, record_count, source_kind,
                   last_run_id, last_seen_at, metadata_json
            FROM artifact_index
            WHERE dataset = ? AND content_hash = ?
            """,
            (dataset, content_hash),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def record_sync_run(
    data_dir: Path,
    *,
    manifest: dict[str, Any],
    artifacts: list[dict[str, Any]],
    pending_count: int = 0,
    state: str = "completed",
) -> dict[str, Any]:
    con = _connect(data_dir)
    try:
        new_artifact_count = 0
        reused_artifact_count = 0
        now = datetime.now(UTC).isoformat()
        for artifact in artifacts:
            metadata = artifact.get("metadata", {})
            storage_state = str(metadata.get("storage_state") or "new")
            if storage_state == "reused":
                reused_artifact_count += 1
            else:
                new_artifact_count += 1
            con.execute(
                """
                INSERT OR REPLACE INTO sync_artifacts (
                    run_id, dataset, source_path, stored_path, file_format, record_count, content_hash,
                    source_kind, state, metadata_json, seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest["run_id"],
                    artifact["dataset"],
                    artifact["source_path"],
                    artifact["stored_path"],
                    artifact["file_format"],
                    int(artifact.get("record_count", 0) or 0),
                    artifact["content_hash"],
                    str(metadata.get("source_kind") or manifest.get("source_kind") or "manual-export"),
                    storage_state,
                    _json(metadata),
                    now,
                ),
            )
            con.execute(
                """
                INSERT OR REPLACE INTO artifact_index (
                    dataset, content_hash, source_path, stored_path, file_format, record_count,
                    source_kind, last_run_id, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact["dataset"],
                    artifact["content_hash"],
                    artifact["source_path"],
                    artifact["stored_path"],
                    artifact["file_format"],
                    int(artifact.get("record_count", 0) or 0),
                    str(metadata.get("source_kind") or manifest.get("source_kind") or "manual-export"),
                    manifest["run_id"],
                    now,
                    _json(metadata),
                ),
            )

        con.execute(
            """
            INSERT OR REPLACE INTO sync_runs (
                run_id, run_label, source_kind, source_path, state, started_at, finished_at,
                dataset_count, artifact_count, total_records, new_artifact_count, reused_artifact_count,
                pending_count, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest["run_id"],
                manifest["run_label"],
                manifest["source_kind"],
                manifest["source_path"],
                state,
                manifest["started_at"],
                manifest["finished_at"],
                int(manifest.get("dataset_count", 0) or 0),
                int(manifest.get("artifact_count", 0) or 0),
                int(manifest.get("total_records", 0) or 0),
                new_artifact_count,
                reused_artifact_count,
                int(pending_count),
                _json(manifest.get("metadata", {})),
            ),
        )
        con.commit()
        return {
            "run_id": manifest["run_id"],
            "state": state,
            "new_artifact_count": new_artifact_count,
            "reused_artifact_count": reused_artifact_count,
            "pending_count": int(pending_count),
        }
    finally:
        con.close()


def load_sync_summary(data_dir: Path) -> dict[str, Any]:
    db_path = default_state_db_path(data_dir)
    if not db_path.exists():
        return {"available": False, "db_path": str(db_path)}

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        latest_run = con.execute(
            """
            SELECT *
            FROM sync_runs
            ORDER BY finished_at DESC, started_at DESC
            LIMIT 1
            """
        ).fetchone()
        totals = con.execute(
            """
            SELECT
                COUNT(*) AS run_count,
                COALESCE(SUM(artifact_count), 0) AS artifact_count,
                COALESCE(SUM(total_records), 0) AS total_records,
                COALESCE(SUM(new_artifact_count), 0) AS new_artifact_count,
                COALESCE(SUM(reused_artifact_count), 0) AS reused_artifact_count
            FROM sync_runs
            """
        ).fetchone()
        artifact_totals = con.execute(
            """
            SELECT COUNT(*) AS artifact_index_rows
            FROM artifact_index
            """
        ).fetchone()
        payload: dict[str, Any] = {
            "available": True,
            "db_path": str(db_path),
            "run_count": int(totals["run_count"] or 0) if totals else 0,
            "artifact_count": int(totals["artifact_count"] or 0) if totals else 0,
            "total_records": int(totals["total_records"] or 0) if totals else 0,
            "new_artifact_count": int(totals["new_artifact_count"] or 0) if totals else 0,
            "reused_artifact_count": int(totals["reused_artifact_count"] or 0) if totals else 0,
            "artifact_index_rows": int(artifact_totals["artifact_index_rows"] or 0) if artifact_totals else 0,
            "latest_run": dict(latest_run) if latest_run else None,
        }
        if latest_run:
            payload["latest_run"]["metadata"] = json.loads(latest_run["metadata_json"] or "{}")
        return payload
    finally:
        con.close()
