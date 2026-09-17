"use client";

// Shared action state for the console: which suggested actions were accepted,
// dismissed or completed, and progress on ongoing ones. Mock only — persisted in
// localStorage until the console API exists.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ACTIONS, type ActionDefinition, type ActionStatus } from "@/lib/mock-data";
import { getForecast } from "@/lib/forecast";

type ActionState = {
  status: ActionStatus;
  completedSteps: number[];
  decidedAt?: string;
  completedAt?: string;
};

export type ActionView = ActionDefinition & ActionState;

export type RankedAction = ActionView & { rank: number };

type ActionsContextValue = {
  suggested: RankedAction[];
  ongoing: ActionView[];
  history: ActionView[];
  accept: (id: string) => void;
  dismiss: (id: string) => void;
  toggleStep: (id: string, step: number) => void;
  complete: (id: string) => void;
  reset: () => void;
};

const STORAGE_KEY = "ada.actions.v1";

const today = () => new Date().toISOString().slice(0, 10);

function seedState(): Record<string, ActionState> {
  return Object.fromEntries(
    ACTIONS.map((action) => [
      action.id,
      {
        status: action.seed.status,
        completedSteps: action.seed.completedSteps ?? [],
        decidedAt: action.seed.decidedAt,
        completedAt: action.seed.completedAt,
      },
    ]),
  );
}

const ActionsContext = createContext<ActionsContextValue | null>(null);

export function ActionsProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<Record<string, ActionState>>(seedState);
  const [hydrated, setHydrated] = useState(false);

  // Restore after mount so server and first client render match.
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        // Merge onto the seed so actions added to the mock data still appear.
        setState({ ...seedState(), ...JSON.parse(stored) });
      }
    } catch {
      // Storage blocked or corrupt — keep the seed.
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Ignore: state still works for this session.
    }
  }, [state, hydrated]);

  const update = useCallback(
    (id: string, change: (current: ActionState) => ActionState) =>
      setState((previous) => ({ ...previous, [id]: change(previous[id]) })),
    [],
  );

  const accept = useCallback(
    (id: string) =>
      update(id, (current) => ({ ...current, status: "ongoing", decidedAt: today() })),
    [update],
  );

  const dismiss = useCallback(
    (id: string) =>
      update(id, (current) => ({ ...current, status: "dismissed", decidedAt: today() })),
    [update],
  );

  const toggleStep = useCallback(
    (id: string, step: number) =>
      update(id, (current) => ({
        ...current,
        completedSteps: current.completedSteps.includes(step)
          ? current.completedSteps.filter((item) => item !== step)
          : [...current.completedSteps, step],
      })),
    [update],
  );

  const complete = useCallback(
    (id: string) =>
      update(id, (current) => ({ ...current, status: "completed", completedAt: today() })),
    [update],
  );

  const reset = useCallback(() => setState(seedState()), []);

  const value = useMemo<ActionsContextValue>(() => {
    const views: ActionView[] = ACTIONS.map((action) => ({ ...action, ...state[action.id] }));

    // Rank pending actions by forecasted customers leaving high risk.
    const suggested = views
      .filter((action) => action.status === "suggested")
      .sort(
        (a, b) =>
          getForecast(b.id).customersLeavingHighRisk -
          getForecast(a.id).customersLeavingHighRisk,
      )
      .map((action, index) => ({ ...action, rank: index + 1 }));

    const ongoing = views
      .filter((action) => action.status === "ongoing")
      .sort((a, b) => (b.decidedAt ?? "").localeCompare(a.decidedAt ?? ""));

    const history = views
      .filter((action) => action.status === "completed" || action.status === "dismissed")
      .sort((a, b) =>
        (b.completedAt ?? b.decidedAt ?? "").localeCompare(a.completedAt ?? a.decidedAt ?? ""),
      );

    return { suggested, ongoing, history, accept, dismiss, toggleStep, complete, reset };
  }, [state, accept, dismiss, toggleStep, complete, reset]);

  return <ActionsContext.Provider value={value}>{children}</ActionsContext.Provider>;
}

export function useActions() {
  const context = useContext(ActionsContext);
  if (!context) throw new Error("useActions must be used inside <ActionsProvider>.");
  return context;
}
