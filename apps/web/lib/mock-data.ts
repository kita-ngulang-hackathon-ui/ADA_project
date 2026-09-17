// Mock console data. Replaced by lib/api.ts calls once the console API is wired.
// Everything derived (totals, forecasts, ranks) is computed in lib/forecast.ts so
// the numbers on every page agree with each other.

export type RiskBand = "low" | "medium" | "high";

export type RiskCounts = Record<RiskBand, number>;

// Status colors: reserved for risk bands, never reused as a series color.
export const RISK_BANDS: { key: RiskBand; label: string; color: string }[] = [
  { key: "low", label: "Low", color: "var(--status-good)" },
  { key: "medium", label: "Medium", color: "var(--status-warning)" },
  { key: "high", label: "High", color: "var(--status-critical)" },
];

// RFM-FCA hierarchical segmentation (six clusters).
export type SegmentId =
  | "high-rollers"
  | "big-spenders"
  | "moderate-spenders"
  | "low-spenders"
  | "lowest-spenders"
  | "frequent-buyers";

export type Segment = {
  id: SegmentId;
  name: string;
  risk: RiskCounts;
};

export const SEGMENTS: Segment[] = [
  { id: "high-rollers", name: "High Rollers", risk: { low: 1420, medium: 310, high: 130 } },
  { id: "big-spenders", name: "Big Spenders", risk: { low: 2780, medium: 820, high: 340 } },
  { id: "moderate-spenders", name: "Moderate Spenders", risk: { low: 4300, medium: 1650, high: 770 } },
  { id: "low-spenders", name: "Low Spenders", risk: { low: 4390, medium: 2350, high: 1110 } },
  { id: "lowest-spenders", name: "Lowest Spenders", risk: { low: 2630, medium: 1960, high: 1390 } },
  { id: "frequent-buyers", name: "Frequent Buyers", risk: { low: 3480, medium: 840, high: 400 } },
];

export type ActionStatus = "suggested" | "ongoing" | "completed" | "dismissed";

// Forecasted movement of customers between risk bands within one segment.
export type SegmentEffect = {
  segmentId: SegmentId;
  highToMedium: number;
  mediumToLow: number;
};

export type ActionDefinition = {
  id: string;
  title: string;
  summary: string;
  effects: SegmentEffect[];
  instructions: string[];
  seed: {
    status: ActionStatus;
    completedSteps?: number[];
    decidedAt?: string;
    completedAt?: string;
  };
  // Measured result, only for completed actions.
  outcome?: { actualHighToMedium: number };
};

export const ACTIONS: ActionDefinition[] = [
  {
    id: "act-dormant-push",
    title: "Re-engagement push for dormant Lowest Spenders",
    summary:
      "1,390 Lowest Spenders are high risk, most with no app session in 21+ days despite prior weekly use. A three-step notification sequence is forecast to bring them back before a call is needed.",
    effects: [
      { segmentId: "lowest-spenders", highToMedium: 310, mediumToLow: 180 },
      { segmentId: "low-spenders", highToMedium: 90, mediumToLow: 60 },
    ],
    instructions: [
      "Export the dormant high-risk list for Lowest Spenders and Low Spenders from the risk report.",
      "Schedule the three-message push sequence (day 0, day 3, day 7) in the notification tool.",
      "Exclude customers contacted by any campaign in the last 14 days.",
      "Check app re-open rate after day 7 and log it in the action notes.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-fee-waiver",
    title: "Transfer-fee waiver for Low Spenders with falling transaction counts",
    summary:
      "Low Spenders whose monthly transfers dropped by half over 60 days churn at twice the base rate. A 30-day fee waiver removes the most common reason given in exit surveys.",
    effects: [
      { segmentId: "low-spenders", highToMedium: 260, mediumToLow: 140 },
      { segmentId: "moderate-spenders", highToMedium: 60, mediumToLow: 30 },
    ],
    instructions: [
      "Confirm waiver budget with finance (30 days, transfer fees only).",
      "Apply the waiver flag to the eligible customer list.",
      "Send the in-app banner and email announcing the waiver.",
      "Review transaction counts at day 30 and decide whether to extend.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-cashback-streak",
    title: "Cashback streak for Frequent Buyers skipping weeks",
    summary:
      "Frequent Buyers who skipped two of the last four weeks are the fastest-growing high-risk group. A weekly cashback streak rewards returning to their usual rhythm.",
    effects: [
      { segmentId: "frequent-buyers", highToMedium: 150, mediumToLow: 120 },
      { segmentId: "moderate-spenders", highToMedium: 40, mediumToLow: 20 },
    ],
    instructions: [
      "Set up a four-week cashback streak (0.5% rising to 2%) in the rewards engine.",
      "Target Frequent Buyers with two or more skipped weeks in the last month.",
      "Announce the streak with a push notification and card on the home screen.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-paylater-review",
    title: "Paylater limit review for Moderate Spenders near their cap",
    summary:
      "Moderate Spenders repeatedly hitting their paylater limit move spend to competitors. A limit review for customers with clean repayment history is forecast to keep them.",
    effects: [{ segmentId: "moderate-spenders", highToMedium: 180, mediumToLow: 90 }],
    instructions: [
      "Pull Moderate Spenders at 90%+ of paylater limit for three consecutive cycles.",
      "Filter to customers with no late repayments in 12 months.",
      "Send the list to credit risk for limit review approval.",
      "Notify approved customers of their new limit in-app.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-savings-rate",
    title: "Savings-rate boost for declining-balance Big Spenders",
    summary:
      "340 Big Spenders show a balance decline over 60 days combined with 3+ years tenure. This pattern historically precedes churn in this segment.",
    effects: [
      { segmentId: "big-spenders", highToMedium: 120, mediumToLow: 80 },
      { segmentId: "high-rollers", highToMedium: 40, mediumToLow: 30 },
    ],
    instructions: [
      "Confirm the promotional rate (+0.75% for 90 days) with treasury.",
      "Enrol eligible customers automatically and send a personal email.",
      "Track balance trend weekly for the first month.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-onboarding-nudge",
    title: "In-app tutorial nudge for new Lowest Spenders",
    summary:
      "Customers under 90 days tenure who never set up a recurring payment make up a third of high-risk Lowest Spenders. A guided setup nudge is forecast to lift early engagement.",
    effects: [{ segmentId: "lowest-spenders", highToMedium: 120, mediumToLow: 70 }],
    instructions: [
      "Enable the recurring-payment tutorial for customers under 90 days tenure.",
      "Trigger the nudge on the third app session without a recurring payment.",
      "Report tutorial completion rate after two weeks.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-rm-call",
    title: "Relationship-manager call for at-risk High Rollers",
    summary:
      "130 High Rollers are high risk. Few customers, but each carries a large share of deposits, so a personal call from their relationship manager is worth the cost.",
    effects: [{ segmentId: "high-rollers", highToMedium: 85, mediumToLow: 60 }],
    instructions: [
      "Assign each high-risk High Roller to their relationship manager.",
      "Complete calls within 5 business days using the retention call guide.",
      "Log call outcome and any offer made in the CRM.",
      "Flag unresolved complaints to the service team.",
    ],
    seed: { status: "suggested" },
  },
  {
    id: "act-bill-reminder",
    title: "Bill-payment reminder series for Moderate Spenders",
    summary:
      "Moderate Spenders who stopped paying bills through the app show rising churn risk. A reminder series brings bill payments back into the app.",
    effects: [{ segmentId: "moderate-spenders", highToMedium: 140, mediumToLow: 100 }],
    instructions: [
      "Build the reminder audience from customers with no bill payment in 45 days.",
      "Schedule reminders two days before each customer's usual bill date.",
      "Add a one-tap 'pay again' shortcut to the reminder.",
      "Measure bill payments through the app after one billing cycle.",
    ],
    seed: { status: "ongoing", completedSteps: [0, 1], decidedAt: "2026-09-10" },
  },
  {
    id: "act-loyalty-double",
    title: "Double loyalty points for Big Spenders",
    summary:
      "Double points on card spend for Big Spenders whose spend dropped two months in a row.",
    effects: [{ segmentId: "big-spenders", highToMedium: 90, mediumToLow: 50 }],
    instructions: [
      "Enable double points for the eligible list.",
      "Announce by email and in-app card.",
      "Review spend after 3 weeks.",
    ],
    seed: {
      status: "completed",
      completedSteps: [0, 1, 2],
      decidedAt: "2026-08-12",
      completedAt: "2026-09-02",
    },
    outcome: { actualHighToMedium: 72 },
  },
  {
    id: "act-sms-blast",
    title: "Generic SMS win-back blast to all Lowest Spenders",
    summary: "One untargeted SMS to every Lowest Spender with a generic win-back message.",
    effects: [{ segmentId: "lowest-spenders", highToMedium: 60, mediumToLow: 20 }],
    instructions: ["Send the SMS to all Lowest Spenders."],
    seed: { status: "dismissed", decidedAt: "2026-08-28" },
  },
];

export const formatNumber = (value: number) =>
  new Intl.NumberFormat("en-US").format(value);

export const formatPercent = (value: number, total: number) =>
  `${((value / total) * 100).toFixed(1)}%`;

export const formatDate = (iso: string) =>
  new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(iso));
