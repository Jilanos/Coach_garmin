# Coach Garmin

Local-first Garmin data foundation for:

- manual sync/import of Garmin export files
- authenticated Garmin API sync with local token storage
- raw artifact preservation with provenance
- normalized local storage in DuckDB
- deterministic running and recovery metrics

## Quick start

1. Create a virtual environment:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e .
```

2. Import a local Garmin export directory:

```powershell
.venv\Scripts\python -m coach_garmin sync import-export --source C:\path\to\garmin-export
```

The manual import path now recognizes the first real Garmin Connect export slice directly from the full privacy export:

- `*_summarizedActivities.json` -> `activities`
- `*_sleepData.json` -> `sleep`
- `UDSFile_*.json` -> `steps`, `heart_rate`, `stress`
- `*_healthStatusData.json` -> `hrv`

Chunked Garmin export files are ingested independently and deduplicated downstream in the normalized layer.

Extended coverage now includes:

- `MetricsAcuteTrainingLoad_*.json` -> `acute_load` (normalized)
- `TrainingHistory_*.json` -> `training_history` (normalized)
- `user_profile.json` / social-profile files -> `profile` (normalized)
- `*_heartRateZones.json` -> `heart_rate_zones` (normalized)
- device backup/content files -> `device_raw` (raw-only)
- user settings/reminders files -> `settings_raw` (raw-only)

3. Initialize Garmin authentication once with local token storage:

```powershell
.venv\Scripts\python -m coach_garmin auth init --format json
```

4. Sync directly from Garmin Connect while reusing the same local token storage:

```powershell
.venv\Scripts\python -m coach_garmin sync garmin-auth --days 30 --format json
```

Expected secret configuration in `.env.local` or the process environment:

```text
COACH_GARMIN_GARMIN_EMAIL=you@example.com
COACH_GARMIN_GARMIN_PASSWORD=your-password
```

The authenticated token cache is stored locally under `.local/garmin/garmin_tokens.json` and is ignored by git.

5. Read the latest metrics report:

```powershell
.venv\Scripts\python -m coach_garmin report latest --format json
```
