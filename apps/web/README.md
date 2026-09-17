# apps/web (L4)

Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts. One app
serves two surfaces that talk only to the console API:

1. **Ops console** — the fintech ops reviewer: users at risk, allocation, approval, measurement.
2. **Simulated client surface** — shows what the client app would display once a recommendation is `APPROVED`. It pulls approved recommendations; it never approves anything.

The dashboard is a read view over the same database state as the API (requirement 8), not a separate system.

## Layer rules
- Talks only to `NEXT_PUBLIC_API_BASE_URL` (`/console/v1`). No direct DB access.
- Fonts self-hosted in `public/fonts` (no Google Fonts at runtime, offline demo).
- Every screen that shows performance numbers shows the synthetic data banner (`NEXT_PUBLIC_SYNTHETIC_DATA_BANNER`).

## Files to implement

| File | What to implement |
|---|---|
| `app/layout.tsx` | Root layout, nav, synthetic-data banner, tenant switcher (wallet / paylater demo tenants). |
| `app/page.tsx` | Overview: pipeline run button + stage progress, counts by segment and pattern. |
| `app/users/[pseudonym]/page.tsx` | User detail: churn risk, `delta_stability` chart (Recharts), `pattern_type` badge, external signal context, impact segment, reasons. Demo beats 1–2. |
| `app/allocation/page.tsx` | Budget input, run allocation, selected vs excluded table with exclusion reasons and runner-ups. Demo beat 3. |
| `app/ops/recommendations/page.tsx` | Pending approval queue. |
| `app/ops/recommendations/[id]/page.tsx` | Detail with narration (LLM or TEMPLATE label), top pick + runner-up, approve / reject with note. Demo beat 4. |
| `app/client-surface/page.tsx` | Simulated fintech app screen showing approved incentives; sends delivery-ack. Demo beat 5. |
| `app/measurement/page.tsx` | Three-arm comparison (CONTROL / NAIVE / ENGINE), lift charts, "new labeled examples added" counter. Demo beat 6. |
| `lib/api.ts` | Typed fetch client for console endpoints, error envelope handling, cursor pagination. |
| `lib/types.ts` | TypeScript mirrors of API response shapes. |
| `components/` | Shared UI (see `components/README.md`). |

## Tests to write
- Playwright smoke test through the six demo beats against the seeded demo (optional if time allows).

## Related
Requirement 12 and demo narrative §7; DEMO_SCRIPT in the spec.
