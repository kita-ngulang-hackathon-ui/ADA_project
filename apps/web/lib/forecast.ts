// Derived numbers: portfolio totals and per-action churn forecasts. Segments
// and actions come from live data (components/actions-provider.tsx) rather
// than a static import, so every function here takes them as arguments.
import { RISK_BANDS, type ActionDefinition, type RiskCounts, type Segment } from "@/lib/mock-data";

export const sumRisk = (risk: RiskCounts) => risk.low + risk.medium + risk.high;

const addRisk = (a: RiskCounts, b: RiskCounts): RiskCounts => ({
  low: a.low + b.low,
  medium: a.medium + b.medium,
  high: a.high + b.high,
});

const ZERO: RiskCounts = { low: 0, medium: 0, high: 0 };

export function computePortfolioRisk(segments: Segment[]): RiskCounts {
  return segments.reduce((total, segment) => addRisk(total, segment.risk), ZERO);
}

export function computeChurnRiskSlices(segments: Segment[]) {
  const portfolio = computePortfolioRisk(segments);
  return RISK_BANDS.map((band) => ({
    label: band.label,
    users: portfolio[band.key],
    color: band.color,
  }));
}

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

export function forecastAction(action: ActionDefinition, segments: Segment[]): ActionForecast {
  const portfolioRisk = computePortfolioRisk(segments);
  const totalCustomers = sumRisk(portfolioRisk) || 1;

  const segmentForecasts = segments.map((segment) => {
    const after = applyEffect(segment, action);
    const size = sumRisk(segment.risk) || 1;
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

  const forecast = segmentForecasts.reduce((total, item) => addRisk(total, item.after), ZERO);
  const customersLeavingHighRisk = portfolioRisk.high - forecast.high;

  return {
    current: portfolioRisk,
    forecast,
    customersLeavingHighRisk,
    highRiskReductionPp: (customersLeavingHighRisk / totalCustomers) * 100,
    segments: segmentForecasts.map(({ after: _after, ...rest }) => rest),
  };
}

// A reduction in high-risk share, shown as a signed change: 1.3 -> "−1.3pp".
export const formatReductionPp = (reduction: number) =>
  `${reduction > 0 ? "−" : reduction < 0 ? "+" : ""}${Math.abs(reduction).toFixed(1)}pp`;
