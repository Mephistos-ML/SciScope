export type Viewer = {
  userId: string;
  email: string;
  displayName: string;
  avatarUrl?: string | null;
  features: string[];
};

export type ViewerPayload = {
  user: Viewer | null;
};

export type FeedEventItem = {
  eventId: string;
  subscriptionId: string;
  repositoryId: string;
  repositoryFullName: string;
  repositorySource: string;
  repositoryUrl: string;
  selectedQuery: string | null;
  title: string;
  summary: string;
  source: string;
  signalKind: string;
  url: string;
  publishedAt: string | null;
  createdAt: string | null;
  readAt: string | null;
};

export type FeedEventListPayload = {
  items: FeedEventItem[];
  nextCursor: string | null;
  hasMore: boolean;
  unreadCount: number;
};

export type FeedEventDetailPayload = FeedEventItem & {
  rawText: string;
  normalizedText: string;
  metadata: Record<string, unknown>;
};

export type RepositorySummary = {
  repositoryId: string;
  source: string;
  fullName: string;
  url: string;
};

export type SubscriptionItem = {
  subscriptionId: string;
  repository: RepositorySummary;
  selectedQuery: string | null;
  createdAt: string;
  unreadEventCount: number;
};

export type SubscriptionListPayload = {
  items: SubscriptionItem[];
};

export type ExploreResultItem = {
  itemId: string;
  source: string;
  fullName: string;
  url: string;
  description: string;
  language: string | null;
  stars: number | null;
  providerUpdatedAt: string | null;
  query: string | null;
  score: number;
  reason: string;
};

export type ExploreSearchPayload = {
  topicDescription: string;
  aiSearchPlan: AiSearchPlanPayload;
  items: ExploreResultItem[];
  sourceStatuses?: SourceStatusPayload[];
  partial?: boolean;
  canExpand?: boolean;
  message?: string | null;
};

export type ExploreSearchRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_partial"
  | "failed"
  | "interrupted";

export type ExploreSearchRunPayload = ExploreSearchPayload & {
  runId: string;
  status: ExploreSearchRunStatus;
  error: string | null;
  message: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ExploreSearchRunCreatedPayload = ExploreSearchRunPayload & {
  guestAccessToken?: string;
};

export type ExploreAccessErrorPayload = {
  error: string;
  code?: string;
  retryAfterSeconds?: number;
  signInSuggested?: boolean;
  turnstileRequired?: boolean;
};

export type AiSearchPlanPayload = {
  status: "pending" | "ready";
  queries: string[];
};

export type SourceStatusPayload = {
  source: string;
  status: string;
  candidateCount: number;
  error: string | null;
};

export type SearchDiagnosticsReport = {
  run: SearchDiagnosticsRun;
  stages: SearchDiagnosticsStage[];
  providerOutcomes: SearchDiagnosticsProviderOutcome[];
  rankingSnapshots: SearchDiagnosticsRankingSnapshot[];
};

export type SearchDiagnosticsRun = {
  runId: string;
  topicDescription: string;
  status: string;
  plannerMode: string;
  plannerModel: string | null;
  plannerReasoningEffort: string | null;
  rankingPolicyVersion: string;
  backendRevision: string;
  partial: boolean;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
};

export type SearchDiagnosticsStage = {
  stageNumber: number;
  operationId: string;
  status: string;
  executedQueries: string[];
  candidateCounts: {
    retrieved: number;
    admitted: number;
    visible: number;
  };
  timings: Record<string, number>;
};

export type SearchDiagnosticsProviderOutcome = {
  stageNumber: number;
  source: string;
  channel: string;
  query: string;
  attempt: number;
  status: string;
  candidateCount: number;
  durationMs: number;
  retryAfterSeconds: number | null;
  errorCode: string | null;
  errorMessage: string | null;
};

export type SearchDiagnosticsRankingSnapshot = {
  stageNumber: number;
  repositoryId: string;
  repositorySource: string;
  rankPosition: number;
  finalScore: number;
  candidateFacts: Record<string, unknown>;
  retrievalFacts: Record<string, unknown>;
  admissionFacts: Record<string, unknown>;
  rankingFeatures: Record<string, unknown>;
  scoreBreakdown: Record<string, unknown>;
};
