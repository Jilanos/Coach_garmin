# Coaching Evaluation 2026-04-08

## Goal

Evaluate whether the current `coach chat` output is becoming materially more useful for running coaching, not just technically functional.

This evaluation was run after the history-aware and pace-aware delivery wave pushed in commit `2f49001`.

## Validation baseline

Automated baseline:

- `.venv\Scripts\python -m unittest discover -s tests -p "test_coach*.py" -v`
- result: `12/12 OK`

Repository safety baseline:

- `.venv\Scripts\python -m unittest discover -s tests -v`
- result: `17/17 OK`

## Evaluation method

The coaching evaluation used three realistic prompt families:

1. multi-goal runner returning from injury with a recent 10 km benchmark
2. single-goal 10 km progression case with recent benchmark and injury history
3. generic return-to-running case without an explicit race target in the prompt

For each case, we evaluated:

- whether the coach identifies a principal objective
- whether the coach uses benchmark or historical evidence
- whether the coach mentions a training phase
- whether the weekly sessions are specific enough to be actionable
- whether the density of quality work remains plausible for the scenario
- whether the output still drifts into generic wording or incoherent pace guidance

## Rubric

Scoring per scenario:

- `0`: poor
- `1`: weak
- `2`: acceptable
- `3`: good

Dimensions:

- principal-objective handling
- history usage
- pace usage
- injury-awareness
- session specificity
- weekly coherence

## Scenario 1

### Prompt family

Multi-goal return from injury with:

- recent 10 km around `42 min`
- periostitis history
- desire to improve 10 km and marathon

### Observed behavior

- the coach asked for the principal objective
- the coach used the stated 10 km benchmark
- the coach identified a rebuild or return-from-injury context
- the generated week contained:
  - easy runs with pace ceiling
  - one threshold session
  - one long run
  - several rest or adaptation days

### Assessment

- principal-objective handling: `3`
- history usage: `2`
- pace usage: `2`
- injury-awareness: `2`
- session specificity: `2`
- weekly coherence: `2`

### Notes

This scenario is materially better than the previous generic MVP.

Main gains:

- goal conflict is handled
- pace cues appear
- the week no longer collapses into vague filler only

Remaining weakness:

- some summaries are still phrased too generically by the local model
- some justifications remain thinner than a strong human coach would give

## Scenario 2

### Prompt family

Single-goal 10 km progression case with:

- recent 10 km around `42 min`
- target `sub 40`
- recent restricted training due to periostitis

### Observed behavior

- the coach treated `10 km` as the principal objective
- the coach derived threshold-style pace guidance from the benchmark
- the weekly structure stayed conservative:
  - easy runs
  - one quality session
  - long run
  - several recovery or rest days

### Assessment

- principal-objective handling: `3`
- history usage: `2`
- pace usage: `3`
- injury-awareness: `2`
- session specificity: `2`
- weekly coherence: `3`

### Notes

This is currently the strongest path.

Why:

- the prompt gives a clear benchmark
- the prompt gives a clear target event
- the deterministic layer now has enough structure to keep the plan plausible

## Scenario 3

### Prompt family

Generic return-to-running request with:

- no explicit race target
- no explicit benchmark
- desire to rebuild a routine without relapse

### Observed behavior

- the coach first asked what exact objective type to target
- the coach then asked timeline, weekly frequency, and constraints
- the resulting output was better than before, but still showed drift:
  - the top analysis remained somewhat generic
  - the model introduced one structured quality session with pace wording that did not fully align with the deterministic easy-pace context

### Assessment

- principal-objective handling: `2`
- history usage: `2`
- pace usage: `1`
- injury-awareness: `2`
- session specificity: `2`
- weekly coherence: `1`

### Notes

This is the main remaining weak zone.

The coach still needs a stronger deterministic rule for sparse-goal or vague-goal recovery scenarios, especially when no clear performance target should justify a hard session.

## Cross-scenario findings

### What is now clearly improved

1. The coach is no longer purely boilerplate.
2. It can use stated or observed benchmark performance.
3. It can ask for a principal objective when goals conflict.
4. It can derive pace-aware guidance.
5. It now prevents some obvious over-prescription of quality work.

### What remains weak

1. The top-level analysis text still depends too much on the local LLM style and can remain generic.
2. Sparse-goal or low-information recovery prompts still need stronger deterministic guardrails.
3. Some session wording still mixes good structure with slightly inconsistent pace details.
4. The current system is better for `10 km progression with a recent benchmark` than for broad `rebuild safely` coaching.

## Technical issue found during evaluation

One useful bug was found during the evaluation pass:

- a new coaching session could inherit target-event information from a previous saved goal profile

This was corrected during the same wave by restricting which saved goal-profile keys can carry over into a new session.

Regression coverage was added for that behavior.

## Current conclusion

Current coaching quality status:

- technically usable: yes
- materially better than the original generic MVP: yes
- reliable enough for nuanced human-level coaching: not yet

Best current use:

- semi-structured experimentation with realistic prompts
- manual review of the weekly plan
- iterative tuning of the coaching contract

Not yet strong enough for:

- blind trust
- fully autonomous progression planning
- nuanced recovery-only or injury-sensitive coaching without operator review

## Recommended next improvements

1. Add a stricter deterministic branch for `rebuild` and `return-from-injury` states so the model cannot smuggle in overly aggressive quality sessions.
2. Make the analytical summary partly deterministic instead of relying mostly on the LLM wording.
3. Add explicit coaching rules by phase:
   - rebuild
   - return-from-injury
   - 10 km progression
   - marathon base
4. Add a scoring harness so future coaching changes can be compared on the same scenario set.

## Suggested future evaluation loop

Reuse this three-layer test stack on every coaching iteration:

1. automated unit and integration tests
2. scenario prompts with captured outputs
3. manual scoring on the six-dimension rubric in this document

This keeps coaching work grounded in observable behavior instead of only intuition.
