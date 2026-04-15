# AGENTS

## Active text policy

- `ADR 005` is an active project constraint:
  - [logics/architecture/adr_005_choose_end_to_end_utf_8_and_nfc_text_policy.md](c:/Users/paulm/Documents/GitHub/Coach_garmin/logics/architecture/adr_005_choose_end_to_end_utf_8_and_nfc_text_policy.md)
- All user-facing and workflow-facing text must be handled as `UTF-8 + NFC` end to end.
- French accented characters are a default requirement, not a follow-up bugfix.

## Practical rule for future changes

- Any new or updated text in the project must preserve correct French accents by default.
- This applies to:
  - PWA UI
  - chart titles, axes, legends, tooltips, and helper copy
  - CLI output
  - logs
  - JSON payloads
  - HTML
  - Markdown
  - Windows launcher scripts
- Do not rely only on late mojibake repair after rendering; prefer correct encoding and normalization at the source, during storage, and at render time.

## Expected implementation discipline

- Prefer UTF-8-safe file writes and reads.
- Normalize text to NFC before persistence and before provider calls when relevant.
- Treat any new mojibake or broken French string as a regression against ADR 005.
