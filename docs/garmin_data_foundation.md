# Garmin Data Foundation

## First-wave scope

This repository now supports a first local-first data pipeline for Garmin exports:

- manual import from local JSON or CSV exports
- authenticated Garmin Connect API sync with local token storage
- raw artifact preservation under `data/raw/<run_id>/...`
- sync provenance manifests under `data/runs/<run_id>.json`
- normalized analytical storage in `data/normalized/coach_garmin.duckdb`
- deterministic summary metrics written to `data/reports/latest_metrics.json`

## Manual sync entrypoint

```powershell
.venv\Scripts\python -m coach_garmin sync import-export --source C:\path\to\garmin-export --format json
```

## Authenticated Garmin sync entrypoint

```powershell
.venv\Scripts\python -m coach_garmin sync garmin-auth --days 30 --format json
```

Optional range-based sync:

```powershell
.venv\Scripts\python -m coach_garmin sync garmin-auth --start-date 2026-03-01 --end-date 2026-03-31 --format json
```

Authenticated sync expectations:

- Credentials come from `COACH_GARMIN_GARMIN_EMAIL` and `COACH_GARMIN_GARMIN_PASSWORD`.
- Values can live in `.env.local` or in the process environment.
- The Garmin token cache is stored under `.local/garmin/garmin_tokens.json` by default.
- The first authenticated slice focuses on:
  - `activities`
  - `sleep`
  - `heart_rate`
  - `hrv`
  - `stress`
  - `steps`

Supported file stems or parent folder names:

- `activities`
- `sleep`
- `heart_rate`
- `hrv`
- `stress`
- `body_battery`
- `steps`
- `intensity_minutes`
- `training_readiness`
- `recovery_time`

## Storage contract

- Raw files are copied unchanged into `data/raw/<run_id>/<dataset>/`.
- Authenticated payloads are written as JSON artifacts under the same raw contract, with dataset wrappers under `data/raw/<run_id>/<dataset>/`.
- Every sync writes a manifest with:
  - `run_id`
  - source path and source kind
  - start/end timestamps
  - imported artifacts
  - dataset coverage
  - total imported record count
- Authenticated sync manifests also record range metadata, tokenstore path, and warnings when some dataset fetches fail without aborting the whole run.
- Analytics are rebuilt from manifests and raw artifacts, which keeps raw data as the long-term source of truth.

## Normalized model

- `sync_runs`: sync metadata and provenance
- `activities`: normalized activity rows
- `wellness_daily`: normalized daily wellness rows across sleep, HR, HRV, stress, Body Battery, steps, intensity minutes, readiness, and recovery
- `derived_daily_metrics`: deterministic daily summary outputs

## Deterministic metrics

- `load_7d`: sum of daily activity load over the trailing 7 days
- `load_28d`: sum of daily activity load over the trailing 28 days
- `load_ratio_7_28`: `load_7d / load_28d`
- `sleep_hours_7d`: trailing 7-day average sleep duration
- `resting_hr_7d`: trailing 7-day average resting HR
- `hrv_7d`: trailing 7-day average HRV
- `progression_delta`: `current_7d_load - previous_7d_load`
- `fatigue_flag`: true when sleep is low or HRV is degraded against the trailing 28-day baseline
- `overreaching_flag`: true when recent load is elevated and recovery signals are degraded

## Known gaps

- Real-account validation still depends on a local Garmin credential or tokenstore being available on the machine running the sync.
- Garmin payload shapes vary; normalization now supports both fixture-style exports and the first authenticated API slice, but some edge fields can still require follow-up hardening.
- Vendor-computed Garmin scores are stored as contextual fields only; they are not the primary analytical basis.
