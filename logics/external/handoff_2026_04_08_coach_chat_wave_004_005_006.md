# Handoff 2026-04-08 - Coach chat wave 004-005-006

## Scope covered

This handoff covers the delivery wave completed and pushed on `master` up to commit `d5df4bf` on April 8, 2026.

Included workflow slices:

- `req_004_build_a_local_first_coach_garmin_chat_cli`
- `item_004_build_a_local_first_coach_garmin_chat_cli`
- `task_004_build_a_local_first_coach_garmin_chat_cli`
- `req_005_harden_real_export_normalization_and_clean_repo_delivery_artifacts`
- `item_005_correct_real_garmin_activity_normalization_and_coaching_plausibility_on_local_exports`
- `task_005_correct_real_garmin_activity_normalization_and_coaching_plausibility_on_local_exports`
- `item_006_clean_local_validation_artifacts_and_logics_delivery_hygiene`
- `task_006_clean_local_validation_artifacts_and_logics_delivery_hygiene`

Workflow status at handoff time:

- `req_004`: request still marked `Ready`, but its backlog and task are delivered in practice
- `item_004`: `Done`
- `task_004`: `Done`
- `req_005`: `Done`
- `item_005`: `Done`
- `task_005`: `Done`
- `item_006`: `Done`
- `task_006`: `Done`

## Delivered outcome

The repository now contains a first local-first coaching surface for running, backed by local Garmin-derived data and Ollama, plus the real-export hardening needed to keep the coaching output plausible on actual Garmin export files.

Main product outcome:

- a CLI coaching chat is available through `python -m coach_garmin coach chat`
- the coaching loop asks clarification questions in French
- the chat uses local tools for `metrics`, `goals`, `plan`, and `history`
- weekly plans are persisted locally under `data/reports/`
- real Garmin `summarizedActivities` exports are now normalized with the correct unit repair path when they use milliseconds and centimeters
- local-only Garmin validation data handling is now explicit and safer

## Code changes delivered

### CLI and coaching modules

Added or updated:

- `coach_garmin/cli.py`
- `coach_garmin/config.py`
- `coach_garmin/coach_chat.py`
- `coach_garmin/coach_ollama.py`
- `coach_garmin/coach_tools.py`

What these do:

- add a new `coach` CLI namespace
- implement `coach chat`
- connect the chat to Ollama locally
- capture and persist a goal profile
- summarize local metrics and recent history
- generate and save a structured weekly plan
- normalize weak model outputs into a full 7-day plan skeleton when needed

### Normalization and plausibility hardening

Updated:

- `coach_garmin/analytics.py`

What changed:

- added activity plausibility rules by sport type
- added tolerant-first activity repair logic
- detects real Garmin summary-unit exports when raw `distance / duration` matches raw `avgSpeed`
- converts:
  - milliseconds to seconds
  - centimeters to meters
- preserves a fallback correction path for malformed rows that remain recoverable
- avoids propagating clearly implausible activities downstream

### Coaching history behavior

Updated:

- `coach_garmin/coach_tools.py`

What changed:

- running coaching summaries now prioritize running-like activities over the full mixed activity set
- recent running history used by the coach no longer gets dominated by cycling-heavy periods
- both filtered running counts and all-activity counts remain visible

### Documentation and workflow

Updated or created:

- `README.md`
- `logics/request/req_004_build_a_local_first_coach_garmin_chat_cli.md`
- `logics/backlog/item_004_build_a_local_first_coach_garmin_chat_cli.md`
- `logics/tasks/task_004_build_a_local_first_coach_garmin_chat_cli.md`
- `logics/request/req_005_harden_real_export_normalization_and_clean_repo_delivery_artifacts.md`
- `logics/backlog/item_005_correct_real_garmin_activity_normalization_and_coaching_plausibility_on_local_exports.md`
- `logics/tasks/task_005_correct_real_garmin_activity_normalization_and_coaching_plausibility_on_local_exports.md`
- `logics/backlog/item_006_clean_local_validation_artifacts_and_logics_delivery_hygiene.md`
- `logics/tasks/task_006_clean_local_validation_artifacts_and_logics_delivery_hygiene.md`

### Tests

Added:

- `tests/test_coach_chat.py`

Coverage includes:

- local tool behavior
- clarification flow
- Ollama provider failure handling
- partial weekly-plan normalization to a full 7-day structure
- CLI JSON mode
- tolerant repair of real-shape Garmin activity units
- history prioritization for running coaching
- long-run capping for weekly plan generation

## Validation completed

Automated validation run successfully:

- `.venv\Scripts\python -m unittest discover -s tests -p "test_coach*.py" -v`
- `.venv\Scripts\python -m unittest discover -s tests -v`
- `.venv\Scripts\python logics\skills\logics.py lint --require-status`

Observed final automated result before handoff:

- targeted coach suite: `8/8` tests passing
- full repository suite: `14/14` tests passing
- Logics lint: `OK`

## Real Garmin export validation

Local validation source used:

- `data/sources/garmin-export`

Important rule:

- this copied export is local-only and must not be pushed

Real import summary previously observed on the copied export:

- `artifacts_imported: 89`
- `datasets_seen: activities, acute_load, device_raw, heart_rate, heart_rate_zones, hrv, profile, settings_raw, sleep, steps, stress, training_history`
- `total_records: 11833`
- `latest_day: 2026-04-07`

### Before the hardening fix

The real export produced absurd downstream coaching values such as:

- `1197.13 km` over the recent running window
- `6166.2 min` of duration
- `131.46 km` observed long run
- weekly plan long runs in the hundreds of minutes

### After the hardening fix

The same validation path produced plausible values:

- `119.71 km` over 21 days
- `616.6 min`
- `13.15 km` observed long run
- semi-marathon weekly plan with a Saturday long run of `70 min`

This is the core signal that the real-data coaching substrate is now usable again for MVP experimentation.

## Local-only data handling

Final local-only handling after cleanup:

- `data/` is ignored by git and intentionally local-only
- `data/sources/garmin-export` is retained as the local validation source of truth
- `data/validation_real_export` was removed because it is a disposable derived validation workspace
- `README.md` now documents how to regenerate `data/validation_real_export` locally if needed

Regeneration command:

```powershell
.venv\Scripts\python -m coach_garmin sync import-export --source "data/sources/garmin-export" --data-dir "data/validation_real_export" --format json
```

## Current operator commands

### Run the latest metrics report

```powershell
.venv\Scripts\python -m coach_garmin report latest --format json
```

### Start the coach chat

```powershell
.venv\Scripts\python -m coach_garmin coach chat --goal "Je vise un semi en 1h45"
```

### Re-run local real-export validation

```powershell
.venv\Scripts\python -m coach_garmin sync import-export --source "data/sources/garmin-export" --data-dir "data/validation_real_export" --format json
```

## Runtime and environment notes

At handoff time:

- Ollama is installed locally
- the repo-level hybrid assist runtime reported the configured shared profile `deepseek-coder-v2:16b` as missing in Ollama, so handoff packet generation degraded to the Codex fallback path
- the coaching implementation itself was developed and validated against local Ollama `qwen2.5:7b`

This means there are two separate concerns:

- the product coaching path can run against `qwen2.5:7b`
- the shared Logics hybrid runtime currently expects a different local model profile and may degrade unless that profile is installed or reconfigured

## Remaining known limits

### Product limits

- the coach is still an MVP focused on a one-week plan, not multi-week progression
- the model can still produce thin wording or weak session labels, so the deterministic skeleton remains important
- the coaching layer is still conservative and intentionally bounded

### Data limits

- Garmin exports may contain more shape variants over time than the ones already repaired
- the current tolerant repair path is strong for the observed `summarizedActivities` issue, but future export variants may need new explicit rules

### Workflow limits

- `req_004` remains marked `Ready` even though `item_004` and `task_004` are done; this is a workflow coherence cleanup candidate for a future pass
- no dedicated product brief exists yet for the coaching direction
- no focused ADR has been added yet for the long-term coaching contract or storage semantics

## Suggested next steps

### Highest value next

1. Run a first real user goal through `coach chat` and review the quality of clarification questions and weekly-plan usefulness.
2. Capture a few real coaching transcripts and derive concrete UX issues:
   - weak questions
   - overlong answers
   - missing signals
   - awkward session wording
3. Decide whether the next slice is:
   - coaching quality iteration
   - daily check-in flow
   - multi-week progression
   - stronger structured output contract

### Technical follow-ups

1. Align the shared hybrid runtime's expected Ollama profile with the actually installed local model, or install the expected profile.
2. Consider closing or updating `req_004` so the request status matches the delivered backlog and task state.
3. Consider adding a product brief for the coaching experience before expanding the feature set.
4. Consider adding a small anomaly-report surface for future Garmin real-export debugging.

## Reference commits

Key commits relevant to this handoff:

- `88fe2ac` pushed earlier for task 003 dataset coverage
- `d5df4bf` pushed on April 8, 2026 for coach chat, real-export hardening, and cleanup

## Repository state at handoff creation

Expected repo state before pushing this handoff:

- clean or nearly clean except for this handoff artifact itself

This document is intended as the main passation artifact for the completed coaching MVP plus real-export stabilization wave.
