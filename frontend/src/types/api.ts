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
  beta?: ExploreBetaDiagnostic;
};

export type ExploreBetaDiagnostic = {
  decision: {
    status: "gate_rejected" | "admission_rejected" | "below_cutoff" | "included";
    admissionBucket: string;
    label: string;
  };
  retrievalOrigin: {
    kind: "catalog" | "provider" | "catalog_and_provider";
    label: string;
  };
  scoreBreakdown: {
    strongestMatchQuality: number;
    strongestMatchPoints: number;
    corroborationQuality: number;
    corroborationPoints: number;
    matchedQueryCount: number;
    totalQueryCount: number;
    evidenceCount: number;
    hitCount: number;
  };
};

export type ExploreBetaPayload = {
  enabled: true;
  candidateCount: number;
  relevanceCutoff: number;
  execution?: {
    executedQueries: string[];
    pendingQueryCount: number;
    attempts: Array<{
      query: string;
      attempt: number;
      status: "completed" | "timed_out";
      durationMs: number;
      candidateCount: number;
    }>;
  };
  timings?: ExploreSearchTimingPayload;
};

export type ExploreSearchTimingPayload = {
  aiPlanningDurationMs: number;
  retrievalDurationMs: number;
  evaluationDurationMs: number;
  responseBuildDurationMs: number;
  totalDurationMs: number;
};

export type ExploreSearchPayload = {
  topicDescription: string;
  aiSearchPlan: AiSearchPlanPayload;
  items: ExploreResultItem[];
  sourceStatuses?: SourceStatusPayload[];
  partial?: boolean;
  canExpand?: boolean;
  message?: string | null;
  beta?: ExploreBetaPayload | null;
};

export type ExploreSearchRunStatus =
  | "queued"
  | "planning"
  | "retrieving"
  | "completed"
  | "completed_partial"
  | "failed";

export type ExploreSearchRunPayload = ExploreSearchPayload & {
  runId: string;
  status: ExploreSearchRunStatus;
  error: string | null;
  message: string | null;
  createdAt: string;
  updatedAt: string;
  responseMode: "canonical" | "beta";
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
