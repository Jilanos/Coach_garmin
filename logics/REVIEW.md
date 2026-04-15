# Logics Global Review

_Generated: 2026-04-14 19:09 UTC_

## Snapshot

- Architecture decisions: 6
- Product briefs: 4
- Requests: 16
- Backlog items: 17
- Tasks: 18
- Specs: 0
- Archived requests hidden: yes

## Findings

- Template placeholders remaining: 0
- Indicators with unknown values (`??%`): 0

### Task progress distribution

| Bucket | Count |
|---|---:|
| (missing) | 0 |
| ??% | 0 |
| 0% | 0 |
| 1-49% | 0 |
| 50-99% | 0 |
| 100% | 18 |
| (invalid) | 0 |

### Backlog progress distribution

| Bucket | Count |
|---|---:|
| (missing) | 0 |
| ??% | 0 |
| 0% | 0 |
| 1-49% | 0 |
| 50-99% | 0 |
| 100% | 17 |
| (invalid) | 0 |

## Recommendations (prioritized)

1. Replace template placeholders in active docs and remove `??%` indicators once the scope is understood.
2. Ensure each backlog item has measurable acceptance criteria and a clear priority (Impact/Urgency).
3. Ensure each task has a step-by-step plan and at least 1-2 concrete validation commands.
4. Keep relationships explicit: link request -> backlog -> task (and spec when useful).
5. Generate supporting views when the doc set grows: `logics/INDEX.md` + `logics/RELATIONSHIPS.md`.

## Suggested commands

- `python logics/skills/logics-doc-linter/scripts/logics_lint.py`
- `python logics/skills/logics-indexer/scripts/generate_index.py --out logics/INDEX.md`
- `python logics/skills/logics-relationship-linker/scripts/link_relations.py --out logics/RELATIONSHIPS.md`
- `python logics/skills/logics-duplicate-detector/scripts/find_duplicates.py --min-score 0.55`
