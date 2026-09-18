# apps/web (L4)

The ops console. Next.js 15 (App Router), React 19, TypeScript, Tailwind 4, Recharts.

Talks only to the console API (`/console/v1`) over `NEXT_PUBLIC_API_BASE_URL`, defaulting to `http://localhost:8000`. No direct database access. It is a read-and-approve view over the same state the API serves (requirement 8), not a separate system.

```bash
pnpm install
pnpm dev          # http://localhost:3000
pnpm typecheck
pnpm build
```

The console signs in automatically as the first reviewer in `CONSOLE_DEMO_REVIEWERS` for the demo tenant; there is no login screen yet.

## Wired to live data

| Route | What it shows |
|---|---|
| `/dashboard` | Churn-risk donut and the segment split, both computed from real churn scores and real 30-day transaction volume. Plus the top-ranked pending actions. |
| `/suggested-actions` | Pending recommendation groups, ranked. Expanding one shows its forecast effect on churn risk and per segment. **Accept** approves every pending recommendation in the group through the real API; **Dismiss** rejects them. |
| `/actions` | Accepted groups with their checklists, and the history of completed and dismissed ones. |

## Still stubs

`/allocation`, `/measurement`, `/client-surface`, `/ops/recommendations`, `/ops/recommendations/[id]`, `/users/[pseudonym]` render a placeholder. They are not linked in the sidebar.

## How live data reaches the screens

The pipeline recommends per user or per circle, one incentive at a time; it has no notion of a "campaign" or of RFM segments. Two adapters bridge that gap, and both are honest about it:

```
lib/api.ts           typed fetch client, session bootstrap, error envelope -> ApiError
lib/types.ts         TypeScript mirrors of the console API responses
lib/live-data.ts     API shapes -> Segment[] / ActionDefinition[]
lib/forecast.ts      portfolio totals and per-action forecasts
lib/mock-data.ts     shared types, segment names, formatters (no data)
components/actions-provider.tsx   fetches once, groups, exposes accept/dismiss
```

- **Segments** come from `GET /console/v1/segments`, which buckets real churn risk into terciles and real `canonical_events.amount_idr` into spend tiers. The RFM-style names are a presentation choice over real numbers.
- **Actions** are real recommendations grouped by `incentive_code`. Member counts, costs and statuses are real; the summary text is the real LLM or template narration attached to a member recommendation. The "customers leaving high risk" forecast assumes one risk-band improvement per targeted customer — a portfolio rollup for the chart, not a prediction the pipeline makes.
- The per-action checklist has no backend equivalent and is stored in `localStorage`.

## Related

Requirement 12 and the demo narrative in the spec.
