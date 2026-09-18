// Typed client for the console API (/console/v1). Browser-only: relies on the
// httpOnly session cookie the API sets, so every call goes through fetch with
// credentials, never server-side.
import type { Incentive, Recommendation, RecommendationStatus, UserSegment } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// No login page exists yet (apps/web/README.md gap). The demo has exactly one
// tenant and reviewer allow-list (CONSOLE_DEMO_REVIEWERS), so the console
// signs in as the first one automatically.
const DEMO_TENANT_SLUG = "demo-wallet";
const DEMO_REVIEWER_ID = "ops_reviewer_1";

export class ApiError extends Error {
  code: string;
  requestId?: string;
  status: number;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

let sessionReady: Promise<void> | null = null;

function ensureSession(): Promise<void> {
  sessionReady ??= fetch(`${API_BASE}/console/v1/session`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant_slug: DEMO_TENANT_SLUG, reviewer_id: DEMO_REVIEWER_ID }),
  }).then((response) => {
    if (!response.ok) throw new Error(`console session failed: HTTP ${response.status}`);
  });
  return sessionReady;
}

async function apiFetch<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  await ensureSession();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (response.status === 401 && !retried) {
    // Session cookie expired mid-visit: re-mint once and retry this call.
    sessionReady = null;
    return apiFetch<T>(path, init, true);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const envelope = body?.error;
    throw new ApiError(
      response.status,
      envelope?.code ?? "UNKNOWN",
      envelope?.message ?? `HTTP ${response.status}`,
      envelope?.request_id,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function toRecommendation(row: any): Recommendation {
  return {
    id: row.id,
    allocationRunId: row.allocation_run_id,
    subjectType: row.subject_type,
    userPseudonym: row.user_pseudonym,
    circleId: row.circle_id,
    incentiveCode: row.incentive_code,
    costIdr: row.cost_idr,
    priorityIdr: row.priority_idr,
    userRank: row.user_rank,
    isRunnerUp: row.is_runner_up,
    status: row.status,
    reasonText: row.reason_text,
    reasonSource: row.reason_source,
    createdAt: row.created_at,
    submittedAt: row.submitted_at,
    reviewedBy: row.reviewed_by,
    reviewedAt: row.reviewed_at,
    reviewNote: row.review_note,
    deliveredAt: row.delivered_at,
  };
}

export async function listRecommendations(statuses: RecommendationStatus[]): Promise<Recommendation[]> {
  const params = new URLSearchParams();
  statuses.forEach((s) => params.append("status", s));
  params.set("limit", "500");
  const data = await apiFetch<{ items: any[] }>(`/console/v1/recommendations?${params.toString()}`);
  return data.items.map(toRecommendation);
}

export async function approveRecommendation(id: string, note?: string): Promise<Recommendation> {
  const row = await apiFetch<any>(`/console/v1/recommendations/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ note: note ?? null }),
  });
  return toRecommendation(row);
}

export async function rejectRecommendation(id: string, note?: string): Promise<Recommendation> {
  const row = await apiFetch<any>(`/console/v1/recommendations/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ note: note ?? null }),
  });
  return toRecommendation(row);
}

export async function listIncentives(): Promise<Incentive[]> {
  const rows = await apiFetch<any[]>("/console/v1/incentives");
  return rows.map((r) => ({
    code: r.code,
    displayName: r.display_name,
    costIdr: r.cost_idr,
    encouragesBorrowing: r.encourages_borrowing,
    subjectType: r.subject_type,
    active: r.active,
  }));
}

export async function listSegments(): Promise<UserSegment[]> {
  const data = await apiFetch<{ items: any[] }>("/console/v1/segments");
  return data.items.map((r) => ({
    userPseudonym: r.user_pseudonym,
    churnRisk: r.churn_risk,
    riskBand: r.risk_band,
    segmentIds: r.segment_ids,
  }));
}
