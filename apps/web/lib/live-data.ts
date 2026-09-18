// Turns real console API data into the Segment[] / ActionDefinition[] shapes
// the dashboard and actions pages already render (lib/mock-data.ts types).
//
// Two real shapes get bridged onto ideas the pipeline itself doesn't have:
// - "Segment": the pipeline has no RFM-style clusters, only churn_risk and the
//   four IMPACT segments. lib/api.ts's segments come from a small additive
//   backend endpoint (services/api/.../console/segments.py) that buckets real
//   spend (canonical_events.amount_idr) and real churn_risk -- not invented.
// - "Action": the pipeline recommends per-user or per-circle, one incentive at
//   a time; there is no campaign object. Each Action here is a real group of
//   individual recommendations sharing one incentive_code, and every number
//   on it (customer count, current/forecast risk) is computed from the real
//   member recommendations and their real segment/risk lookup -- nothing here
//   is sampled or hand-authored, but the "one risk band per approval" model
//   is a simplification, not something the pipeline itself predicts.
import type { ActionDefinition, ActionStatus, RiskCounts, Segment, SegmentEffect, SegmentId } from "@/lib/mock-data";
import { SEGMENT_NAMES } from "@/lib/mock-data";
import type { Incentive, Recommendation, UserSegment } from "@/lib/types";

const SEGMENT_IDS: SegmentId[] = [
  "high-rollers",
  "big-spenders",
  "moderate-spenders",
  "low-spenders",
  "lowest-spenders",
  "frequent-buyers",
];

export function buildSegments(userSegments: UserSegment[]): Segment[] {
  const risk: Record<SegmentId, RiskCounts> = Object.fromEntries(
    SEGMENT_IDS.map((id) => [id, { low: 0, medium: 0, high: 0 }]),
  ) as Record<SegmentId, RiskCounts>;

  for (const user of userSegments) {
    for (const id of user.segmentIds) {
      if (!(id in risk)) continue;
      risk[id as SegmentId][user.riskBand] += 1;
    }
  }

  return SEGMENT_IDS.map((id) => ({ id, name: SEGMENT_NAMES[id], risk: risk[id] }));
}

const STATUS_ORDER: { statuses: Recommendation["status"][]; result: ActionStatus }[] = [
  { statuses: ["PENDING_APPROVAL"], result: "suggested" },
  { statuses: ["APPROVED"], result: "ongoing" },
  { statuses: ["DELIVERED"], result: "completed" },
  { statuses: ["REJECTED"], result: "dismissed" },
];

function groupStatus(members: Recommendation[]): ActionStatus {
  for (const { statuses, result } of STATUS_ORDER) {
    if (members.some((m) => statuses.includes(m.status))) return result;
  }
  return "dismissed";
}

function latestTimestamp(values: (string | null)[]): string | undefined {
  const present = values.filter((v): v is string => v !== null).sort();
  return present.length ? present[present.length - 1].slice(0, 10) : undefined;
}

// One targeted, currently-pending-or-approved customer is assumed to move
// down exactly one risk band if the offer lands -- high risk in this segment
// becomes one fewer, and one more medium (or medium -> low). This is a
// simplification for the forecast chart; the pipeline's own impact_score per
// user is the real prediction, this is a portfolio-level rollup of it.
export function buildActions(
  recommendations: Recommendation[],
  incentives: Incentive[],
  userSegments: UserSegment[],
): ActionDefinition[] {
  const incentiveByCode = new Map(incentives.map((i) => [i.code, i]));
  const segmentByUser = new Map(userSegments.map((u) => [u.userPseudonym, u]));

  const groups = new Map<string, Recommendation[]>();
  for (const rec of recommendations) {
    const list = groups.get(rec.incentiveCode) ?? [];
    list.push(rec);
    groups.set(rec.incentiveCode, list);
  }

  const actions: ActionDefinition[] = [];
  for (const [code, members] of groups) {
    const incentive = incentiveByCode.get(code);
    const displayName = incentive?.displayName ?? code;

    const effectsBySegment = new Map<SegmentId, SegmentEffect>();
    let targetedCount = 0;
    for (const rec of members) {
      if (!rec.userPseudonym) continue; // GROUP/circle recs have no per-user segment to attribute.
      const info = segmentByUser.get(rec.userPseudonym);
      if (!info) continue;
      targetedCount += 1;
      for (const segId of info.segmentIds) {
        if (!SEGMENT_IDS.includes(segId as SegmentId)) continue;
        const effect = effectsBySegment.get(segId as SegmentId) ?? {
          segmentId: segId as SegmentId,
          highToMedium: 0,
          mediumToLow: 0,
        };
        if (info.riskBand === "high") effect.highToMedium += 1;
        else if (info.riskBand === "medium") effect.mediumToLow += 1;
        effectsBySegment.set(segId as SegmentId, effect);
      }
    }

    // A handful of LLM narrations come back truncated or degenerate (e.g. a
    // bare number) -- real ones run 150+ chars, so a short floor filters
    // those out without needing to know the exact failure mode.
    const MIN_NARRATION_CHARS = 60;
    const isUsable = (text: string | null) => !!text && text.length >= MIN_NARRATION_CHARS;
    const narrated = members.find((m) => m.reasonSource === "LLM" && isUsable(m.reasonText));
    const anyReason = members.find((m) => isUsable(m.reasonText));
    const summary =
      narrated?.reasonText ??
      anyReason?.reasonText ??
      `${displayName} recommended for ${members.length} customer${members.length === 1 ? "" : "s"} by the retention pipeline.`;

    const groupCount = members.filter((m) => m.subjectType === "GROUP").length;
    const userCount = members.length - groupCount;

    actions.push({
      id: code,
      title: `${displayName} — ${members.length} recommendation${members.length === 1 ? "" : "s"}`,
      summary,
      effects: [...effectsBySegment.values()],
      instructions: [
        `Review the ${userCount} individual and ${groupCount} circle recommendation${groupCount === 1 ? "" : "s"} in this group.`,
        "Approve to move every pending recommendation to the delivery queue, or dismiss to reject them.",
        "Approved offers appear in bank_demo's Penawaran page and mobile offers rail within one poll interval.",
      ],
      status: groupStatus(members),
      decidedAt: latestTimestamp(members.map((m) => m.reviewedAt)),
      completedAt: latestTimestamp(members.map((m) => m.deliveredAt)),
    });
  }

  return actions.sort((a, b) => b.effects.length - a.effects.length);
}

export function memberIds(recommendations: Recommendation[], incentiveCode: string, statuses: Recommendation["status"][]) {
  return recommendations
    .filter((r) => r.incentiveCode === incentiveCode && statuses.includes(r.status))
    .map((r) => r.id);
}
