## adr_004_scientific_charts_for_sport_specific_volumes_and_data_recalculation - Scientific charts for sport specific volumes and data recalculation
> Date: 2026-04-14
> Status: Accepted
> Drivers: chart readability, sport separation, recalculation, local-first trust, stable derived metrics
> Related request: `req_015_scientific_charts_sport_specific_volumes_and_data_recalculation_controls`
> Related backlog: `item_015_scientific_charts_sport_specific_volumes_and_data_recalculation_controls`
> Related task: (none yet)
> Reminder: Update status, linked refs, decision rationale, consequences, migration plan, and follow-up work when you edit this doc.

# Overview
The analytics layer should emit clean sport-specific series and science-style chart data instead of leaving the UI to guess.
The dashboard needs axes, ticks, hover values, and separate sport totals so the user can trust what they see.
Derived data must be recalculable on demand without blocking the local-first app.

```mermaid
flowchart LR
    Current[Mixed raw metrics] --> Decision[Sport-specific analytics contract]
    Decision --> App[Scientific dashboard rendering]
    Decision --> Data[Filtered and recalculable series]
    Decision --> Ops[Non-blocking refresh]
    Decision --> Team[Safer coaching decisions]
```

# Context
The current dashboard implementation can only stay readable if the analytics layer prepares cleaner curves and sport-separated totals.
Running, cycling, and strength need different treatment.
The dashboard also needs a non-blocking refresh path so the user can ask for a recalculation when filtering changes or when the processed series look stale.

# Decision
Use the analytics layer as the source of truth for:
- sport-specific weekly volumes
- monotone curve data
- chart-ready values with axes and hover details
- a refresh/recalculate action that recomputes derived views without blocking the UI

Keep the UI focused on display and interaction, not on rebuilding the data model on every render.

# Alternatives considered
- Derive all chart details directly inside the UI.
- Keep running, cycling, and strength totals blended into one dashboard volume.
- Use minimal sparklines with no axes or hover values.

# Consequences
- The analytics contract becomes richer, but much easier to reuse.
- The UI becomes more readable and less error-prone.
- A recalculation button becomes meaningful because the series it refreshes are explicit and separate.
- Tests need to protect sport separation and graph readability expectations.

# Migration and rollout
- Keep fallbacks so the current UI still renders if the recalculation payload is missing.
- Add the scientific chart behavior incrementally, reusing the existing local dashboard shell.
- Validate the series shape and the sport split before closing the wave.

# References
- `req_015_scientific_charts_sport_specific_volumes_and_data_recalculation_controls`
- `item_015_scientific_charts_sport_specific_volumes_and_data_recalculation_controls`
- `prod_003_scientific_dashboard_charts_and_sport_specific_volume_filtering`

# Follow-up work
- Add a reusable chart component with axes, hover values, and consistent tick styles.
- Wire a recalculation button to analytics refresh and derived metric rebuilds.
- Tune sport filtering rules once the next batch of data is exercised.
