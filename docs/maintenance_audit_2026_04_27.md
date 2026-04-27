# Maintenance Audit - 2026-04-27

## Scope

This note captures the maintenance actions to keep the project baseline stable after the coaching and dashboard iterations.

## Encoding Baseline

- ADR 005 remains active: user-facing and workflow-facing text must be `UTF-8 + NFC`.
- Source correction is preferred over late mojibake repair.
- Runtime repair utilities remain useful only as compatibility fallback and test fixtures.
- The active anti-regression check is `tests.test_text_encoding`.

## Coaching Flow Split

- CLI coaching remains conversational and can request clarification when the goal is underspecified.
- PWA coaching is structured and field-driven:
  - objective is mandatory
  - health constraints, other constraints, and targeted questions are optional
  - field values are saved as they are edited
  - planning output and the latest question answer are persisted for app reopen
- This split is intentional until the PWA and CLI contracts are unified behind a shared coaching request model.

## Large Module Guardrail

Current high-risk files are large enough that future feature work should avoid adding broad responsibilities directly inside them:

- `coach_garmin/analytics_support.py`
- `coach_garmin/pwa_service_runtime_support.py`
- `coach_garmin/coach_chat_support.py`
- `web/app.js`
- `coach_garmin/pwa_service_support.py`

Recommended next slices:

- Extract PWA coaching state and rendering helpers from `web/app.js` before adding another coaching UI feature.
- Extract reset/cache and response-building helpers from `pwa_service_runtime_support.py` before adding another server endpoint.
- Keep analytics formulas and presentation text separated when touching `analytics_support.py`.

## Validation Baseline

Before committing maintenance changes, keep this minimum sequence:

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
node --check web/app.js
```

For text-related changes, also run:

```powershell
.venv\Scripts\python -m unittest tests.test_text_encoding -v
```
