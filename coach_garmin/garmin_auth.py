from __future__ import annotations

import importlib.metadata
import hashlib
import json
import traceback
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from coach_garmin.analytics import rebuild_analytics
from coach_garmin.config import (
    AUTHENTICATED_DATASETS,
    DEFAULT_ENV_FILE,
    DEFAULT_GARMIN_EMAIL_ENV,
    DEFAULT_GARMIN_LOOKBACK_DAYS,
    DEFAULT_GARMIN_PASSWORD_ENV,
    DEFAULT_GARMIN_TOKENSTORE,
)
from coach_garmin.contracts import ArtifactRecord, SyncManifest
from coach_garmin.env import resolve_secret
from coach_garmin.storage import ensure_data_dirs, new_run_id, now_utc, write_json, write_raw_payload
from coach_garmin.sync_state import load_sync_summary, lookup_artifact_index, record_sync_run
from coach_garmin.text_encoding import repair_text_tree


SYNC_DEBUG_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "garmin-sync-debug.jsonl"


class GarminClientProtocol(Protocol):
    def login(self, tokenstore: str | None = None) -> tuple[str | None, str | None]:
        ...

    def get_activities_by_date(
        self,
        startdate: str,
        enddate: str | None = None,
        activitytype: str | None = None,
        sortorder: str | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        ...

    def get_rhr_day(self, cdate: str) -> dict[str, Any]:
        ...

    def get_heart_rates(self, cdate: str) -> dict[str, Any]:
        ...

    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None:
        ...

    def get_stress_data(self, cdate: str) -> dict[str, Any]:
        ...

    def get_daily_steps(self, start: str, end: str) -> list[dict[str, Any]]:
        ...


ClientFactory = Callable[[str | None, str | None, Callable[[], str] | None], GarminClientProtocol]


def _default_client_factory(
    email: str | None,
    password: str | None,
    prompt_mfa: Callable[[], str] | None,
) -> GarminClientProtocol:
    return Garmin(email=email, password=password, prompt_mfa=prompt_mfa)


@dataclass(slots=True)
class SyncDateRange:
    start_date: date
    end_date: date

    @property
    def start_text(self) -> str:
        return self.start_date.isoformat()

    @property
    def end_text(self) -> str:
        return self.end_date.isoformat()


def _prompt_mfa() -> str:
    return input("Enter Garmin MFA code: ").strip()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def resolve_sync_range(
    start_date: str | None,
    end_date: str | None,
    days: int,
    today: date | None = None,
) -> SyncDateRange:
    anchor = today or datetime.now(UTC).date()
    end = _parse_date(end_date) if end_date else anchor
    start = _parse_date(start_date) if start_date else end - timedelta(days=max(days, 1) - 1)
    if start > end:
        raise ValueError("start_date cannot be after end_date")
    return SyncDateRange(start_date=start, end_date=end)


def _date_strings(window: SyncDateRange) -> list[str]:
    cursor = window.start_date
    values: list[str] = []
    while cursor <= window.end_date:
        values.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return values


def _hash_payload(payload: Any) -> str:
    serialized = json.dumps(repair_text_tree(payload), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _append_sync_debug_event(event: dict[str, Any]) -> None:
    SYNC_DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": now_utc().isoformat(),
        **repair_text_tree(event),
    }
    with SYNC_DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def describe_auth_environment(
    *,
    tokenstore_path: Path = DEFAULT_GARMIN_TOKENSTORE,
    env_file: Path = DEFAULT_ENV_FILE,
    email_env: str = DEFAULT_GARMIN_EMAIL_ENV,
    password_env: str = DEFAULT_GARMIN_PASSWORD_ENV,
) -> dict[str, Any]:
    tokenstore_path = tokenstore_path.resolve()
    tokenstore_exists = tokenstore_path.exists()
    tokenstore_size = tokenstore_path.stat().st_size if tokenstore_exists else None
    tokenstore_mtime = datetime.fromtimestamp(tokenstore_path.stat().st_mtime, UTC).isoformat() if tokenstore_exists else None
    email = resolve_secret(email_env, env_file=env_file)
    password = resolve_secret(password_env, env_file=env_file)
    try:
        package_version = importlib.metadata.version("garminconnect")
    except Exception:
        package_version = None
    return repair_text_tree({
        "package": "garminconnect",
        "package_version": package_version,
        "tokenstore_path": str(tokenstore_path),
        "tokenstore_exists": tokenstore_exists,
        "tokenstore_size": tokenstore_size,
        "tokenstore_mtime": tokenstore_mtime,
        "tokenstore_parent_exists": tokenstore_path.parent.exists(),
        "email_configured": bool(email),
        "password_configured": bool(password),
        "env_file": str(env_file),
        "login_strategy_hint": "mobile SSO / portal fallback via python-garminconnect",
    })


def log_auth_test_event(*, data_dir: Path, event: dict[str, Any]) -> None:
    _append_sync_debug_event({"event": "auth:test", "data_dir": str(data_dir), **event})


def _looks_rate_limited_or_blocked(message: str) -> bool:
    text = message.lower()
    return any(
        marker in text
        for marker in (
            "429",
            "403",
            "cloudflare",
            "too many requests",
            "rate limit",
            "blocking this request",
        )
    )


def _authenticate_client(
    *,
    tokenstore_path: Path,
    email: str | None,
    password: str | None,
    env_file: Path,
    email_env: str,
    password_env: str,
    client_factory: ClientFactory,
) -> tuple[GarminClientProtocol, bool]:
    has_tokenstore = tokenstore_path.exists()
    if not has_tokenstore and (not email or not password):
        raise ValueError(
            "Authenticated Garmin sync requires either an existing tokenstore or both "
            f"{email_env} and {password_env} in the environment or {env_file}."
        )

    tokenstore_path.parent.mkdir(parents=True, exist_ok=True)
    client = client_factory(email, password, _prompt_mfa)

    try:
        client.login(tokenstore=str(tokenstore_path))
    except GarminConnectTooManyRequestsError as exc:
        raise RuntimeError(
            "Garmin rate limited authentication (HTTP 429). Stop retries, keep the same "
            f"token store at {tokenstore_path}, and wait before retrying."
        ) from exc
    except GarminConnectAuthenticationError as exc:
        message = str(exc)
        if _looks_rate_limited_or_blocked(message):
            raise RuntimeError(
                "Garmin/Cloudflare blocked this authentication attempt (HTTP 403/429). "
                "Do not retry in a loop. Wait before retrying and reuse the same token "
                f"store path: {tokenstore_path}."
            ) from exc
        raise RuntimeError(
            "Garmin authentication failed. If the local token cache is stale, remove "
            f"{tokenstore_path} and re-run `coach-garmin auth init`. Original error: {message}"
        ) from exc
    except GarminConnectConnectionError as exc:
        message = str(exc)
        if _looks_rate_limited_or_blocked(message):
            raise RuntimeError(
                "Garmin/Cloudflare blocked the login flow before the session could be "
                "established. Do not keep retrying immediately. Wait, then retry with "
                f"the same token store path: {tokenstore_path}."
            ) from exc
        raise RuntimeError(
            f"Garmin authentication could not be established because of a connection or session error: {message}"
        ) from exc

    return client, has_tokenstore


def _find_key(payload: Any, candidates: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        for key in candidates:
            if key in payload and payload[key] not in (None, ""):
                return payload[key]
        for value in payload.values():
            found = _find_key(value, candidates)
            if found not in (None, ""):
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_key(item, candidates)
            if found not in (None, ""):
                return found
    return None


def _build_daily_record(calendar_date: str, payload: Any, **flattened: Any) -> dict[str, Any]:
    record = {"calendarDate": calendar_date, "payload": payload}
    for key, value in flattened.items():
        if value not in (None, ""):
            record[key] = value
    return record


def _fetch_activities(client: GarminClientProtocol, window: SyncDateRange, warnings: list[str]) -> list[dict[str, Any]]:
    try:
        activities = client.get_activities_by_date(window.start_text, window.end_text, sortorder="asc")
    except Exception as exc:
        warnings.append(f"activities:{window.start_text}:{window.end_text}: {exc}")
        return []
    normalized: list[dict[str, Any]] = []
    for activity in activities:
        activity_type = activity.get("activityType")
        if isinstance(activity_type, dict):
            activity = {
                **activity,
                "activityType": activity_type.get("typeKey")
                or activity_type.get("key")
                or activity_type.get("typeId"),
            }
        normalized.append(activity)
    return normalized


def _fetch_sleep(client: GarminClientProtocol, days: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for day in days:
        try:
            payload = client.get_sleep_data(day)
        except Exception as exc:
            warnings.append(f"sleep:{day}: {exc}")
            continue
        records.append(
            _build_daily_record(
                day,
                payload,
                sleepDurationSeconds=_find_key(payload, ("sleepTimeSeconds", "sleepDurationSeconds", "durationSeconds")),
            )
        )
    return records


def _fetch_heart_rate(client: GarminClientProtocol, days: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for day in days:
        rhr_payload: dict[str, Any] | None = None
        heart_rates_payload: dict[str, Any] | None = None
        try:
            rhr_payload = client.get_rhr_day(day)
        except Exception as exc:
            warnings.append(f"heart_rate.rhr:{day}: {exc}")
        try:
            heart_rates_payload = client.get_heart_rates(day)
        except Exception as exc:
            warnings.append(f"heart_rate.daily:{day}: {exc}")

        if not rhr_payload and not heart_rates_payload:
            continue

        records.append(
            {
                "calendarDate": day,
                "restingHeartRate": _find_key(rhr_payload or {}, ("restingHeartRate", "restingHR", "value")),
                "averageHeartRate": _find_key(
                    heart_rates_payload or {},
                    ("averageHeartRate", "averageHR", "allDayAvg", "allDayAverageHeartRate"),
                ),
                "rhr_payload": rhr_payload,
                "heart_rates_payload": heart_rates_payload,
            }
        )
    return records


def _fetch_hrv(client: GarminClientProtocol, days: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for day in days:
        try:
            payload = client.get_hrv_data(day) or {}
        except Exception as exc:
            warnings.append(f"hrv:{day}: {exc}")
            continue
        records.append(
            _build_daily_record(
                day,
                payload,
                hrv=_find_key(payload, ("lastNightAvg", "overnightAvg", "averageHrv", "hrvMs", "hrv")),
            )
        )
    return records


def _fetch_stress(client: GarminClientProtocol, days: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for day in days:
        try:
            payload = client.get_stress_data(day)
        except Exception as exc:
            warnings.append(f"stress:{day}: {exc}")
            continue
        records.append(
            _build_daily_record(
                day,
                payload,
                stressLevel=_find_key(payload, ("overallStressLevel", "averageStressLevel", "stressLevel", "stress")),
            )
        )
    return records


def _fetch_steps(client: GarminClientProtocol, window: SyncDateRange, warnings: list[str]) -> list[dict[str, Any]]:
    try:
        payload = client.get_daily_steps(window.start_text, window.end_text)
    except Exception as exc:
        warnings.append(f"steps:{window.start_text}:{window.end_text}: {exc}")
        return []

    records: list[dict[str, Any]] = []
    for row in payload:
        calendar_date = str(
            row.get("calendarDate")
            or row.get("date")
            or row.get("summaryDate")
            or row.get("metricDate")
            or ""
        )
        if not calendar_date:
            continue
        records.append(row)
    return records


def _store_dataset_artifact(
    data_dir: Path,
    run_id: str,
    dataset: str,
    payload: dict[str, Any],
    source_path: str,
    range_metadata: dict[str, object],
) -> ArtifactRecord:
    filename = f"{dataset}_{range_metadata['start_date']}_{range_metadata['end_date']}.json"
    stored_path = write_raw_payload(data_dir=data_dir, run_id=run_id, dataset=dataset, filename=filename, payload=payload)
    return ArtifactRecord(
        dataset=dataset,
        source_path=source_path,
        stored_path=str(stored_path.resolve()),
        file_format="json",
        record_count=len(payload.get("data", [])),
        content_hash=_hash_payload(payload),
        metadata={**range_metadata, "source_filename": filename, "source_kind": "garmin-authenticated-api"},
    )


def initialize_garmin_auth(
    tokenstore_path: Path = DEFAULT_GARMIN_TOKENSTORE,
    env_file: Path = DEFAULT_ENV_FILE,
    email_env: str = DEFAULT_GARMIN_EMAIL_ENV,
    password_env: str = DEFAULT_GARMIN_PASSWORD_ENV,
    client_factory: ClientFactory = _default_client_factory,
) -> dict[str, Any]:
    tokenstore_path = tokenstore_path.resolve()
    email = resolve_secret(email_env, env_file=env_file)
    password = resolve_secret(password_env, env_file=env_file)
    _, used_existing_tokenstore = _authenticate_client(
        tokenstore_path=tokenstore_path,
        email=email,
        password=password,
        env_file=env_file,
        email_env=email_env,
        password_env=password_env,
        client_factory=client_factory,
    )
    return repair_text_tree({
        "source_kind": "garmin-auth-init",
        "tokenstore_path": str(tokenstore_path),
        "used_existing_tokenstore": used_existing_tokenstore,
        "credentials_configured": bool(email and password),
    })


def test_garmin_auth(
    *,
    data_dir: Path,
    tokenstore_path: Path = DEFAULT_GARMIN_TOKENSTORE,
    env_file: Path = DEFAULT_ENV_FILE,
    email_env: str = DEFAULT_GARMIN_EMAIL_ENV,
    password_env: str = DEFAULT_GARMIN_PASSWORD_ENV,
    client_factory: ClientFactory = _default_client_factory,
) -> dict[str, Any]:
    auth_environment = describe_auth_environment(
        tokenstore_path=tokenstore_path,
        env_file=env_file,
        email_env=email_env,
        password_env=password_env,
    )
    try:
        payload = initialize_garmin_auth(
            tokenstore_path=tokenstore_path,
            env_file=env_file,
            email_env=email_env,
            password_env=password_env,
        )
        event = repair_text_tree({"status": "success", "result": payload, "auth_environment": auth_environment})
        log_auth_test_event(data_dir=data_dir, event=event)
        return repair_text_tree({"ok": True, "auth_environment": auth_environment, "result": payload, "debug_log_path": str(SYNC_DEBUG_LOG_PATH)})
    except Exception as exc:
        event = repair_text_tree({
            "status": "error",
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
            "auth_environment": auth_environment,
        })
        log_auth_test_event(data_dir=data_dir, event=event)
        return repair_text_tree({
            "ok": False,
            "auth_environment": auth_environment,
            "error": str(exc),
            "error_type": exc.__class__.__name__,
            "debug_log_path": str(SYNC_DEBUG_LOG_PATH),
        })


def run_authenticated_sync(
    data_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = DEFAULT_GARMIN_LOOKBACK_DAYS,
    run_label: str | None = None,
    tokenstore_path: Path = DEFAULT_GARMIN_TOKENSTORE,
    env_file: Path = DEFAULT_ENV_FILE,
    email_env: str = DEFAULT_GARMIN_EMAIL_ENV,
    password_env: str = DEFAULT_GARMIN_PASSWORD_ENV,
    client_factory: ClientFactory = _default_client_factory,
    today: date | None = None,
) -> dict[str, Any]:
    ensure_data_dirs(data_dir)
    sync_window = resolve_sync_range(start_date=start_date, end_date=end_date, days=days, today=today)
    tokenstore_path = tokenstore_path.resolve()
    email = resolve_secret(email_env, env_file=env_file)
    password = resolve_secret(password_env, env_file=env_file)
    run_id = new_run_id()
    started_at = now_utc()
    warnings: list[str] = []
    state_summary_before = load_sync_summary(data_dir)
    _append_sync_debug_event(
        {
            "event": "sync:start",
            "run_id": run_id,
            "data_dir": str(data_dir),
            "run_label": run_label or "garmin-auth",
            "start_date": sync_window.start_text,
            "end_date": sync_window.end_text,
            "tokenstore_path": str(tokenstore_path),
        }
    )
    client, used_existing_tokenstore = _authenticate_client(
        tokenstore_path=tokenstore_path,
        email=email,
        password=password,
        env_file=env_file,
        email_env=email_env,
        password_env=password_env,
        client_factory=client_factory,
    )

    day_list = _date_strings(sync_window)
    datasets_payloads: dict[str, dict[str, Any]] = {
        "activities": {
            "metadata": {"dataset": "activities", "start_date": sync_window.start_text, "end_date": sync_window.end_text},
            "data": _fetch_activities(client, sync_window, warnings),
        },
        "sleep": {
            "metadata": {"dataset": "sleep", "start_date": sync_window.start_text, "end_date": sync_window.end_text},
            "data": _fetch_sleep(client, day_list, warnings),
        },
        "heart_rate": {
            "metadata": {"dataset": "heart_rate", "start_date": sync_window.start_text, "end_date": sync_window.end_text},
            "data": _fetch_heart_rate(client, day_list, warnings),
        },
        "hrv": {
            "metadata": {"dataset": "hrv", "start_date": sync_window.start_text, "end_date": sync_window.end_text},
            "data": _fetch_hrv(client, day_list, warnings),
        },
        "stress": {
            "metadata": {"dataset": "stress", "start_date": sync_window.start_text, "end_date": sync_window.end_text},
            "data": _fetch_stress(client, day_list, warnings),
        },
        "steps": {
            "metadata": {"dataset": "steps", "start_date": sync_window.start_text, "end_date": sync_window.end_text},
            "data": _fetch_steps(client, sync_window, warnings),
        },
    }

    artifacts: list[ArtifactRecord] = []
    datasets_seen: set[str] = set()
    total_records = 0
    source_path = "https://connect.garmin.com/"

    for dataset in AUTHENTICATED_DATASETS:
        payload = datasets_payloads[dataset]
        data = payload["data"]
        if not data:
            continue
        payload_hash = _hash_payload(payload)
        range_metadata = {
            "start_date": sync_window.start_text,
            "end_date": sync_window.end_text,
            "source_kind": "garmin-authenticated-api",
            "tokenstore_path": str(tokenstore_path),
        }
        known_artifact = lookup_artifact_index(data_dir, dataset, payload_hash)
        if known_artifact and Path(str(known_artifact["stored_path"])).exists():
            stored_path = Path(str(known_artifact["stored_path"]))
            artifact = ArtifactRecord(
                dataset=dataset,
                source_path=source_path,
                stored_path=str(stored_path.resolve()),
                file_format="json",
                record_count=len(payload.get("data", [])),
                content_hash=payload_hash,
                metadata={**range_metadata, "source_filename": stored_path.name, "storage_state": "reused"},
            )
        else:
            artifact = _store_dataset_artifact(
                data_dir=data_dir,
                run_id=run_id,
                dataset=dataset,
                payload=payload,
                source_path=source_path,
                range_metadata=range_metadata,
            )
            artifact.metadata["storage_state"] = "copied"
        artifacts.append(artifact)
        datasets_seen.add(dataset)
        total_records += artifact.record_count

    if not artifacts:
        raise ValueError("No authenticated Garmin records were fetched for the selected range.")

    manifest = SyncManifest(
        run_id=run_id,
        run_label=run_label or "garmin-auth",
        source_kind="garmin-authenticated-api",
        source_path=source_path,
        started_at=started_at.isoformat(),
        finished_at=now_utc().isoformat(),
        artifact_count=len(artifacts),
        dataset_count=len(datasets_seen),
        total_records=total_records,
        metadata={
            "start_date": sync_window.start_text,
            "end_date": sync_window.end_text,
            "tokenstore_path": str(tokenstore_path),
            "used_existing_tokenstore": used_existing_tokenstore,
            "warnings": warnings,
            "state_before": state_summary_before,
        },
        artifacts=artifacts,
    )
    manifest_path = data_dir / "runs" / f"{run_id}.json"
    write_json(manifest_path, manifest.to_dict())
    state_summary_after = record_sync_run(
        data_dir,
        manifest=manifest.to_dict(),
        artifacts=[artifact.to_dict() for artifact in artifacts],
        pending_count=len(warnings),
    )
    analytics_summary = rebuild_analytics(data_dir)

    _append_sync_debug_event(
        {
            "event": "sync:success",
            "run_id": run_id,
            "data_dir": str(data_dir),
            "start_date": sync_window.start_text,
            "end_date": sync_window.end_text,
            "artifacts_imported": len(artifacts),
            "datasets_seen": sorted(datasets_seen),
            "warnings": warnings,
            "manifest_path": str(manifest_path),
            "tokenstore_path": str(tokenstore_path),
        }
    )

    return repair_text_tree({
        "run_id": run_id,
        "manifest_path": str(manifest_path),
        "debug_log_path": str(SYNC_DEBUG_LOG_PATH),
        "source_kind": "garmin-authenticated-api",
        "tokenstore_path": str(tokenstore_path),
        "used_existing_tokenstore": used_existing_tokenstore,
        "start_date": sync_window.start_text,
        "end_date": sync_window.end_text,
        "artifacts_imported": len(artifacts),
        "datasets_seen": sorted(datasets_seen),
        "total_records": total_records,
        "new_artifacts": state_summary_after.get("new_artifact_count"),
        "reused_artifacts": state_summary_after.get("reused_artifact_count"),
        "pending_count": state_summary_after.get("pending_count"),
        "warnings": warnings,
        "sync_state": state_summary_after,
        "coverage_report_path": analytics_summary.get("coverage_report_path"),
        "analytics": analytics_summary,
    })


def log_sync_error(*, data_dir: Path, error: Exception, context: dict[str, Any]) -> None:
    _append_sync_debug_event(
        {
            "event": "sync:error",
            "data_dir": str(data_dir),
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            **context,
        }
    )
