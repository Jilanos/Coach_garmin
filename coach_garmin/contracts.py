from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class ArtifactRecord:
    dataset: str
    source_path: str
    stored_path: str
    file_format: str
    record_count: int
    content_hash: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class SyncManifest:
    run_id: str
    run_label: str
    source_kind: str
    source_path: str
    started_at: str
    finished_at: str
    artifact_count: int
    dataset_count: int
    total_records: int
    metadata: dict[str, object] = field(default_factory=dict)
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return payload
