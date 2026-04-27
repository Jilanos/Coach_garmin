# Coach Garmin

Local-first Garmin data foundation for:

- manual sync/import of Garmin export files
- authenticated Garmin API sync with local token storage
- raw artifact preservation with provenance
- normalized local storage in DuckDB
- deterministic running and recovery metrics
- local coaching chat backed by Ollama and local Garmin-derived signals
- local-first PWA shell named Coach ultra perso with chat, import, and dashboard entrypoints

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

6. Read the latest feature coverage report:

```powershell
.venv\Scripts\python -m coach_garmin report coverage --format json
```

7. Start the local-first coach chat:

```powershell
.venv\Scripts\python -m coach_garmin coach chat --goal "Je vise un semi en 1h45"
```

To force a provider:

```powershell
.venv\Scripts\python -m coach_garmin coach chat --provider ollama --goal "Je vise un semi en 1h45"
.venv\Scripts\python -m coach_garmin coach chat --provider gemini --goal "Je vise un semi en 1h45"
```

The coach chat:

- runs in French by default
- uses Ollama locally with `qwen2.5:7b` by default
- can switch to Gemini when `GEMINI_API_KEY` is available in the environment or `.env.local`
- asks clarification questions when the goal is underspecified
- reads local metrics, goals, benchmark performances, and training history
- consumes the coverage report to avoid overclaiming missing signals
- analyzes `21j / 90j / 365j` windows before prescribing the week
- chooses a principal objective when several goals are given
- uses pace-aware workout guidance when recent race or benchmark evidence is available
- saves a versioned weekly plan under `data/reports/weekly_plan_<timestamp>.json`

CLI/PWA coaching note:

- the CLI keeps the conversational coaching flow and may ask clarification questions when a goal is underspecified
- the PWA coaching flow is field-driven: objective is mandatory, constraints and targeted questions are persisted when edited, and the UI sends the available structured context directly to the provider without an extra clarification step

8. Start the local-first PWA shell:

```powershell
.venv\Scripts\python -m coach_garmin web serve --web-root web --data-dir data
```

On Windows, you can also double-click:

```text
Start Coach Garmin PWA.cmd
```

The PWA shell:

- runs offline-first in a local browser tab
- uses a left sidebar with Import, Dashboard, Chat, Terminal, and Settings
- keeps the last local workspace and shows data freshness directly in the UI
- stores workspace preferences locally in the browser
- lets you choose the AI provider between Ollama, Gemini, and OpenAI
- offers a dashboard with clickable cards and a full-screen detail modal
- exposes a filtered terminal view for logs, actions, and provider debugging
- exposes the same local import and coaching flows through `/api/*`
- is intentionally simple in the first version so it can later be wrapped for desktop or Android

## Local-only data hygiene

- Everything under `data/` is intentionally ignored by git and should remain local to the machine.
- A copied real export can live under `data/sources/garmin-export` for local validation only.
- Regenerable validation outputs such as `data/validation_real_export` should be treated as disposable local artifacts rather than push-ready project files.
- To rebuild a real-export validation workspace locally:

```powershell
.venv\Scripts\python -m coach_garmin sync import-export --source "data/sources/garmin-export" --data-dir "data/validation_real_export" --format json
```
