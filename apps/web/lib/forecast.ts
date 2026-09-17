// Derived numbers: portfolio totals and per-action churn forecasts.
import {
  ACTIONS,
  RISK_BANDS,
  SEGMENTS,
  type ActionDefinition,
  type RiskCounts,
  type Segment,
} from "@/lib/mock-data";

export const sumRisk = (risk: RiskCounts) => risk.low + risk.medium + risk.high;

const addRisk = (a: RiskCounts, b: RiskCounts): RiskCounts => ({
  low: a.low + b.low,
  medium: a.medium + b.medium,
  high: a.high + b.high,
});

const ZERO: RiskCounts = { low: 0, medium: 0, high: 0 };

export const PORTFOLIO_RISK: RiskCounts = SEGMENTS.reduce(
  (total, segment) => addRisk(total, segment.risk),
  ZERO,
);

export const TOTAL_CUSTOMERS = sumRisk(PORTFOLIO_RISK);

// Slices for the churn risk donut.
export const CHURN_RISK_SLICES = RISK_BANDS.map((band) => ({
  label: band.label,
  users: PORTFOLIO_RISK[band.key],
  color: band.color,
}));

// Apply an action's forecast movements to one segment's risk counts.
function applyEffect(segment: Segment, action: ActionDefinition): RiskCounts {
  const effect = action.effects.find((item) => item.segmentId === segment.id);
  if (!effect) return segment.risk;
  return {
    low: segment.risk.low + effect.mediumToLow,
    medium: segment.risk.medium + effect.highToMedium - effect.mediumToLow,
    high: segment.risk.high - effect.highToMedium,
  };
}

export type SegmentForecast = {
  segment: Segment;
  currentHighPct: number;
  forecastHighPct: number;
  reductionPp: number;
};

export type ActionForecast = {
  current: RiskCounts;
  forecast: RiskCounts;
  customersLeavingHighRisk: number;
  highRiskReductionPp: number;
  segments: SegmentForecast[];
};

export function forecastAction(action: ActionDefinition): ActionForecast {
  const segments = SEGMENTS.map((segment) => {
    const after = applyEffect(segment, action);
    const size = sumRisk(segment.risk);
    const currentHighPct = (segment.risk.high / size) * 100;
    const forecastHighPct = (after.high / size) * 100;
    return {
      segment,
      after,
      currentHighPct,
      forecastHighPct,
      reductionPp: currentHighPct - forecastHighPct,
    };
  });

  const forecast = segments.reduce((total, item) => addRisk(total, item.after), ZERO);
  const customersLeavingHighRisk = PORTFOLIO_RISK.high - forecast.high;

  return {
    current: PORTFOLIO_RISK,
    forecast,
    customersLeavingHighRisk,
    highRiskReductionPp: (customersLeavingHighRisk / TOTAL_CUSTOMERS) * 100,
    segments: segments.map(({ after: _after, ...rest }) => rest),
  };
}

const FORECASTS = new Map(ACTIONS.map((action) => [action.id, forecastAction(action)]));

export const getForecast = (id: string) => FORECASTS.get(id)!;

// A reduction in high-risk share, shown as a signed change: 1.3 -> "−1.3pp".
export const formatReductionPp = (reduction: number) =>
  `${reduction > 0 ? "−" : reduction < 0 ? "+" : ""}${Math.abs(reduction).toFixed(1)}pp`;
