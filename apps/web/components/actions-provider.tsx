"use client";

// Shared console data: live recommendations grouped into "Actions", live
// segments, and which ones the reviewer accepted/dismissed. Accept/dismiss
// call the real console API (approve/reject every pending recommendation in
// the group); the per-action checklist has no backend equivalent, so it
// stays local, persisted in localStorage same as before.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  approveRecommendation,
  listIncentives,
  listRecommendations,
  listSegments,
  rejectRecommendation,
} from "@/lib/api";
import { computeChurnRiskSlices, computePortfolioRisk, forecastAction, sumRisk } from "@/lib/forecast";
import { buildActions, buildSegments } from "@/lib/live-data";
import type { ActionDefinition, ActionStatus, RiskCounts, Segment } from "@/lib/mock-data";
import type { Incentive, Recommendation, UserSegment } from "@/lib/types";

type LocalOverride = { completedSteps: number[]; forcedCompleted: boolean };

export type ActionView = ActionDefinition & { completedSteps: number[] };

export type RankedAction = ActionView & { rank: number };

type ActionsContextValue = {
  loading: boolean;
  error: string | null;
  segments: Segment[];
  portfolioRisk: RiskCounts;
  churnRiskSlices: ReturnType<typeof computeChurnRiskSlices>;
  totalCustomers: number;
  suggested: RankedAction[];
  ongoing: ActionView[];
  history: ActionView[];
  accept: (id: string) => void;
  dismiss: (id: string) => void;
  toggleStep: (id: string, step: number) => void;
  complete: (id: string) => void;
  reset: () => void;
  getForecast: (id: string) => ReturnType<typeof forecastAction>;
};

const STORAGE_KEY = "ada.actions.overrides.v1";

const ActionsContext = createContext<ActionsContextValue | null>(null);

export function ActionsProvider({ children }: { children: React.ReactNode }) {
  const [recommendations, setRecommendations] = useState<Recommendation[] | null>(null);
  const [rawSegments, setRawSegments] = useState<UserSegment[] | null>(null);
  const [incentives, setIncentives] = useState<Incentive[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, LocalOverride>>({});
  const [hydrated, setHydrated] = useState(false);

  const refetch = useCallback(async () => {
    try {
      const [recs, segs, incs] = await Promise.all([
        listRecommendations(["PENDING_APPROVAL", "APPROVED", "REJECTED", "DELIVERED"]),
        listSegments(),
        listIncentives(),
      ]);
      setRecommendations(recs);
      setRawSegments(segs);
      setIncentives(incs);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load console data");
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setOverrides(JSON.parse(stored));
    } catch {
      // Storage blocked or corrupt — start empty.
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
    } catch {
      // Ignore: overrides still work for this session.
    }
  }, [overrides, hydrated]);

  const setOverride = useCallback(
    (id: string, change: (current: LocalOverride) => LocalOverride) =>
      setOverrides((previous) => ({
        ...previous,
        [id]: change(previous[id] ?? { completedSteps: [], forcedCompleted: false }),
      })),
    [],
  );

  const accept = useCallback(
    (id: string) => {
      const pendingIds = (recommendations ?? [])
        .filter((r) => r.incentiveCode === id && r.status === "PENDING_APPROVAL")
        .map((r) => r.id);
      Promise.all(pendingIds.map((recId) => approveRecommendation(recId)))
        .then(refetch)
        .catch((err) => setError(err instanceof Error ? err.message : "Approve failed"));
    },
    [recommendations, refetch],
  );

  const dismiss = useCallback(
    (id: string) => {
      const pendingIds = (recommendations ?? [])
        .filter((r) => r.incentiveCode === id && r.status === "PENDING_APPROVAL")
        .map((r) => r.id);
      Promise.all(pendingIds.map((recId) => rejectRecommendation(recId)))
        .then(refetch)
        .catch((err) => setError(err instanceof Error ? err.message : "Reject failed"));
    },
    [recommendations, refetch],
  );

  const toggleStep = useCallback(
    (id: string, step: number) =>
      setOverride(id, (current) => ({
        ...current,
        completedSteps: current.completedSteps.includes(step)
          ? current.completedSteps.filter((item) => item !== step)
          : [...current.completedSteps, step],
      })),
    [setOverride],
  );

  const complete = useCallback(
    (id: string) => setOverride(id, (current) => ({ ...current, forcedCompleted: true })),
    [setOverride],
  );

  const reset = useCallback(() => setOverrides({}), []);

  const value = useMemo<ActionsContextValue>(() => {
    const segments = rawSegments ? buildSegments(rawSegments) : [];
    const actions =
      recommendations && incentives && rawSegments
        ? buildActions(recommendations, incentives, rawSegments)
        : [];

    const views: ActionView[] = actions.map((action) => {
      const override = overrides[action.id];
      const status: ActionStatus = override?.forcedCompleted ? "completed" : action.status;
      return {
        ...action,
        status,
        completedAt: override?.forcedCompleted ? (action.completedAt ?? new Date().toISOString().slice(0, 10)) : action.completedAt,
        completedSteps: override?.completedSteps ?? [],
      };
    });

    const forecasts = new Map(actions.map((action) => [action.id, forecastAction(action, segments)]));
    const getForecast = (id: string) =>
      forecasts.get(id) ?? { current: { low: 0, medium: 0, high: 0 }, forecast: { low: 0, medium: 0, high: 0 }, customersLeavingHighRisk: 0, highRiskReductionPp: 0, segments: [] };

    const suggested = views
      .filter((action) => action.status === "suggested")
      .sort((a, b) => getForecast(b.id).customersLeavingHighRisk - getForecast(a.id).customersLeavingHighRisk)
      .map((action, index) => ({ ...action, rank: index + 1 }));

    const ongoing = views
      .filter((action) => action.status === "ongoing")
      .sort((a, b) => (b.decidedAt ?? "").localeCompare(a.decidedAt ?? ""));

    const history = views
      .filter((action) => action.status === "completed" || action.status === "dismissed")
      .sort((a, b) => (b.completedAt ?? b.decidedAt ?? "").localeCompare(a.completedAt ?? a.decidedAt ?? ""));

    const portfolioRisk = computePortfolioRisk(segments);

    return {
      loading: recommendations === null || rawSegments === null || incentives === null,
      error,
      segments,
      portfolioRisk,
      churnRiskSlices: computeChurnRiskSlices(segments),
      totalCustomers: sumRisk(portfolioRisk),
      suggested,
      ongoing,
      history,
      accept,
      dismiss,
      toggleStep,
      complete,
      reset,
      getForecast,
    };
  }, [recommendations, rawSegments, incentives, overrides, error, accept, dismiss, toggleStep, complete, reset]);

  return <ActionsContext.Provider value={value}>{children}</ActionsContext.Provider>;
}

export function useActions() {
  const context = useContext(ActionsContext);
  if (!context) throw new Error("useActions must be used inside <ActionsProvider>.");
  return context;
}
