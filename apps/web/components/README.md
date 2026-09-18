# apps/web/components

Shared UI for the console.

## Built

- `app-shell` — top bar and sidebar.
- `actions-provider` — fetches recommendations, segments and incentives once, groups them, and exposes `accept` / `dismiss` against the real API.
- `action-badges` — `RankBadge` and `StatusBadge`; status is carried by icon and text, never colour alone.
- `suggested-actions-preview` — the dashboard's top-actions list.
- `charts/` — `donut-chart`, `risk-bars`, `segment-impact-chart`, `chart-tooltip`. Recharts, each with a "view as table" fallback for accessibility.

## Planned

For the routes that are still stubs:

- `PatternBadge` — `CIRCLE_SPECIFIC` / `MARKET_DRIVEN` / `STABLE`.
- `SegmentBadge` — `PERSUADABLE` / `SURE_THING` / `LOST_CAUSE` / `SLEEPING_DOG`.
- `StabilityChart` — neighbour activity ratio now vs 30 days ago.
- `LiftChart` — retention by arm.
- `ReasonList` — reason factors with narration source label (LLM / TEMPLATE).
- `ApprovalPanel` — per-recommendation approve / reject with note.
