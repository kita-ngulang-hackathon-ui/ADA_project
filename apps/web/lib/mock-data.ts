// Shared presentational constants, shape types and formatters for the console.
// Live data comes from lib/api.ts; lib/live-data.ts turns it into the shapes
// declared here. Everything derived (totals, forecasts, ranks) is computed in
// lib/forecast.ts so the numbers on every page agree with each other.

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

export const SEGMENT_NAMES: Record<SegmentId, string> = {
  "high-rollers": "High Rollers",
  "big-spenders": "Big Spenders",
  "moderate-spenders": "Moderate Spenders",
  "low-spenders": "Low Spenders",
  "lowest-spenders": "Lowest Spenders",
  "frequent-buyers": "Frequent Buyers",
};

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
  status: ActionStatus;
  decidedAt?: string;
  completedAt?: string;
  // Measured result, only for completed actions. Not populated until the
  // console can attach an experiment_id to a recommendation (apps/web/README.md gap).
  outcome?: { actualHighToMedium: number };
};

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
