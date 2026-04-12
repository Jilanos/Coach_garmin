## task_011_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation - Refresh Garmin export via incremental sync and harden training data foundation
> From version: 0.1.0
> Schema version: 1.0
> Status: Done
> Understanding: 96
> Confidence: 93
> Progress: 100%
> Complexity: High
> Theme: Health
> Reminder: Update status/understanding/confidence/progress and linked request/backlog references when you edit this doc.

# Context
- Derived from backlog item `item_011_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation`.
- Source file: `logics/backlog/item_011_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation.md`.
- Related request(s): `req_010_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation`.
- The project already supports a stable local Garmin ZIP export import and local analytics, but the data foundation still needs a stronger freshness story and a cleaner split between operational sync state and training analytics.
- The current problem is not the existence of local data; it is how to keep a trusted baseline export current with later Garmin data without turning the sync layer into a fragile all-or-nothing auth path.
- This task keeps the ZIP export as the baseline source of truth, adds incremental refresh, and hardens the sync/analytics split needed by the coach.

```mermaid
%% logics-kind: task
%% logics-signature: task|refresh-garmin-export-via-incremental-sy|item-011-refresh-garmin-export-via-incre|1-implement-the-zip-baseline-plus|run-the-relevant-automated-tests-for
stateDiagram-v2
    state "item 011 baseline refresh slice" as Backlog
    state "1. Implement ZIP baseline plus refresh" as Build
    state "2. Add SQLite sync state and DuckDB analytics split" as State
    state "3. Add pace and benchmark intelligence" as Signals
    state "4. Validate import and refresh paths" as Validate
    state "Done report" as Done
    [*] --> Backlog
    Backlog --> Build
    Build --> State
    State --> Signals
    Signals --> Validate
    Validate --> Done
    Done --> [*]
```

# Plan
- [ ] 1. Implement the ZIP baseline plus incremental refresh path for newer Garmin data while keeping provenance intact.
- [ ] 2. Add or harden the SQLite sync state layer so incremental updates can record what was seen, refreshed, or still pending.
- [ ] 3. Keep DuckDB as the main analytics engine and wire the refreshed data into the derived training features used by the coach.
- [ ] 4. Add or harden the pace and benchmark engine so recent performances and race benchmarks can inform coaching outputs.
- [ ] 5. Keep the experimental auth backend behind an adapter boundary so the project still works when auth is unavailable.
- [ ] 6. Validate the baseline import, a refresh case, and the coaching-relevant signal outputs on local data.
- [ ] CHECKPOINT: leave the wave in a commit-ready state and update the linked Logics docs before continuing.
- [ ] CHECKPOINT: if the shared AI runtime is active and healthy, run `python logics/skills/logics.py flow assist commit-all` for the current step, item, or wave checkpoint.
- [ ] GATE: do not close the task until the relevant automated tests and quality checks have passed.
- [ ] FINAL: capture the validation evidence and close the task only when the implementation is ready.

# Delivery checkpoints
- Keep the ZIP export as the baseline source of truth.
- Incremental refreshes should merge into the same local workspace and preserve traceability.
- SQLite is for sync state and checkpoints; DuckDB is for analytics and derived features.
- The refresh path must remain useful even if the experimental auth path is missing or unavailable.
- Pace and benchmark intelligence should prefer recent benchmark races first, with quality sessions as secondary evidence.
- This task should leave the repository in a coherent, commit-ready state at the end of the wave.

# AC Traceability
- AC1 -> Build: The project can ingest a local Garmin ZIP export as the baseline source of truth. Proof: capture validation evidence in this doc.
- AC2 -> Build: The project can refresh or extend that baseline with newer Garmin data and activities when available. Proof: capture validation evidence in this doc.
- AC3 -> State: The sync flow has an explicit state layer that records what was already seen, what was refreshed, and what remains pending. Proof: capture validation evidence in this doc.
- AC4 -> State: The project supports both Garmin-provided load and a derived local load model. Proof: capture validation evidence in this doc.
- AC5 -> Signals: The coach can access pace and benchmark intelligence from recent training history and recent race or workout data. Proof: capture validation evidence in this doc.
- AC6 -> State: SQLite is used for operational state if needed, and DuckDB remains the primary analytics engine. Proof: capture validation evidence in this doc.
- AC7 -> Build: The incremental refresh path remains local-first and does not require a cloud dependency to function at baseline. Proof: capture validation evidence in this doc.
- AC8 -> Validate: Tests cover at least one baseline ZIP import case, one incremental refresh case, and one coaching-relevant pace or benchmark signal case. Proof: capture validation evidence in this doc.
- AC9 -> Validate: The implementation preserves provenance and traceability across baseline and refreshed data. Proof: capture validation evidence in this doc.

# Validation
- Run the relevant automated tests for the import and refresh path.
- Run the relevant automated tests for the pace and benchmark signal path.
- Run the relevant lint or quality checks before closing the task.
- Confirm the completed wave leaves the repository in a commit-ready state.
- Finish workflow executed on 2026-04-12.
- Linked backlog/request close verification passed.

# Definition of Done (DoD)
- [x] Scope implemented and acceptance criteria covered.
- [x] Validation commands executed and results captured.
- [x] No wave or step was closed before the relevant automated tests and quality checks passed.
- [x] Linked request/backlog/task docs updated during completed waves and at closure.
- [x] Each completed wave left a commit-ready checkpoint or an explicit exception is documented.
- [x] Status is `Done` and progress is `100%`.

# Links
- Product brief(s): `logics/product/prod_000_local_first_pwa_coach_dashboard.md`
- Architecture decision(s): `logics/architecture/adr_001_choose_local_pwa_storage_and_provider_integration.md`
- Backlog item: `logics/backlog/item_011_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation.md`
- Request(s): `logics/request/req_010_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation.md`

# Notes
- Derived from backlog item `item_011_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation`.
- Keep this task bounded to the incremental refresh foundation; if readiness/body battery/recovery is revisited later, split it into a separate backlog item.
- Keep the implementation local-first and preserve the ZIP baseline as the anchor for future refreshes.

# Report
- Finished on 2026-04-12.
- Linked backlog item(s): `item_011_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation`
- Related request(s): `req_010_refresh_garmin_export_via_incremental_sync_and_harden_training_data_foundation`
