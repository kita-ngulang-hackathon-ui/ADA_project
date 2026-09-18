// TypeScript mirrors of console API responses (services/api/src/api/routers/console/*.py).

export type RecommendationStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "DELIVERED";

export type Recommendation = {
  id: string;
  allocationRunId: string;
  subjectType: "USER" | "GROUP";
  userPseudonym: string | null;
  circleId: string | null;
  incentiveCode: string;
  costIdr: number;
  priorityIdr: number;
  userRank: number;
  isRunnerUp: boolean;
  status: RecommendationStatus;
  reasonText: string | null;
  reasonSource: "LLM" | "TEMPLATE" | null;
  createdAt: string;
  submittedAt: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  reviewNote: string | null;
  deliveredAt: string | null;
};

export type Incentive = {
  code: string;
  displayName: string;
  costIdr: number;
  encouragesBorrowing: boolean;
  subjectType: "USER" | "GROUP";
  active: boolean;
};

export type RiskBand = "low" | "medium" | "high";

export type UserSegment = {
  userPseudonym: string;
  churnRisk: number | null;
  riskBand: RiskBand;
  segmentIds: string[];
};
