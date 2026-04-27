# Logics Relationships

_Refreshed: 2026-04-27_

## Summary

- This focused relationship view tracks the active dashboard continuity and ADR 005 cleanup wave.
- The earlier broad generated file was stale and noisy because it contained many truncated unresolved refs from older doc shapes.
- The delivery story now separates:
  - absorbed predecessor work
  - delivered chart and analytics waves
  - delivered coaching persistence/UI wave
  - delivered source-text and workflow-reconciliation cleanup

## Delivered cleanup chain

- `req_024_finish_adr_005_source_text_cleanup_and_reconcile_dashboard_logics_continuity`
  - derives `item_026_finish_adr_005_source_text_cleanup_and_reconcile_dashboard_logics_continuity`
  - executes through `task_027_finish_adr_005_source_text_cleanup_and_reconcile_dashboard_logics_continuity`
  - is governed by:
    - `adr_005_choose_end_to_end_utf_8_and_nfc_text_policy`
    - `adr_006_choose_dynamic_chart_windows_and_cadence_normalization`
  - reuses product framing from:
    - `prod_003_scientific_dashboard_charts_and_sport_specific_volume_filtering`
    - `prod_004_scientific_chart_centering_and_timeframe_selector`

## Delivered coaching chain

- `req_025_expand_coaching_inputs_persist_constraints_and_add_targeted_training_questions_flow`
  - derives `item_027_expand_coaching_inputs_persist_constraints_and_add_targeted_training_questions_flow`
  - executes through `task_028_expand_coaching_inputs_persist_constraints_and_add_targeted_training_questions_flow`
  - covers:
    - automatic persistence of coaching context edits
    - persistence of the latest generated plan after reopening the PWA
    - persistence of the latest targeted question answer
    - removal of the manual context-save action
    - hidden first-glance presentation of provider input signals

## Absorbed predecessor chain

- `req_017_scientific_charts_centered_timeframe_selector_and_french_text_fixes`
  - remains for traceability only
  - links to `item_017_scientific_charts_centered_timeframe_selector_and_french_text_fixes`
  - links to `task_018_scientific_charts_centered_timeframe_selector_and_french_text_fixes`
- `item_017` and `task_018` are now marked `Obsolete`
  - their scope was absorbed by later bounded waves rather than executed directly as one standalone slice

## Successor waves that absorbed req 017

- `req_018_dynamic_chart_timeframes_and_cadence_unit_correction`
  - delivered through `item_018` and `task_019`
  - covered:
    - chart timeframe switching
    - y-axis rescaling
    - cadence normalization
- `req_022_refine_scientific_chart_semantics_unsmoothed_wellness_views_and_cadence_zone_repairs`
  - delivered through:
    - `item_023` -> `task_024`
    - `item_024` -> `task_025`
  - covered:
    - volume chart semantics
    - zone display simplification
    - raw wellness views
    - cadence diagnostics
    - combined pace / cadence / HR chart
- `req_023_refine_dashboard_zone_load_session_typing_and_metric_documentation`
  - delivered through `item_025` and `task_026`
  - covered:
    - load semantics
    - session typing
    - session distribution
    - technical metric documentation
- `req_024` and `task_027`
  - keep the last remaining source-text cleanup and workflow reconciliation separate from those product waves

## Practical reading order

1. Read `adr_005` for the text policy constraint.
2. Read `adr_006` for the chart-window contract that replaced the older static view.
3. Read `req_022` and `req_023` to understand what was actually delivered in the chart waves.
4. Read `req_024`, `item_026`, and `task_027` for the text cleanup and continuity work.
5. Read `req_025`, `item_027`, and `task_028` for the current coaching persistence and UI behavior.

## Remainder after reconciliation

- No new dashboard feature request is opened by this relationship update.
- Any remaining work after `task_027` should be created as a new sibling request or backlog item, not reopened through `req_017` / `item_017` / `task_018`.
