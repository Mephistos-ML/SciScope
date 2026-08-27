export type StatusPayload = {
  subscriptionCount: number;
  subscriptions: StatusSubscriptionPayload[];
  autoScanStarted: boolean;
  autoScanIntervalSeconds: number;
  lastScanAt: string | null;
  lastScanError: string | null;
  watchedRepositories: WatchedRepositoryPayload[];
  sourceCheckpoints: SourceCheckpointPayload[];
  totalFeedEvents: number;
};

export type Viewer = {
  userId: string;
  email: string;
  displayName: string;
  avatarUrl?: string | null;
};

export type ViewerPayload = {
  user: Viewer | null;
};

export type StatusSubscriptionPayload = {
  subscriptionId: string;
  repositoryId: string;
  source: string;
  fullName: string;
  selectedQuery: string | null;
};

export type WatchedRepositoryPayload = {
  subscriptionId: string;
  repositoryId: string;
  source: string;
  fullName: string;
  url: string;
  selectedQuery: string | null;
  stars: number | null;
  language: string | null;
};

export type SourceCheckpointPayload = {
  subscriptionId: string;
  repositoryId: string;
  source: string;
  fullName: string;
  checkpointKey: string;
  checkpointValue: string | null;
  updatedAt: string | null;
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
};

export type FeedEventListPayload = {
  items: FeedEventItem[];
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
  query: string | null;
  score: number;
  reason: string;
  matchedTerms: string[];
};

export type ExploreSearchPayload = {
  topicDescription: string;
  aiSearchPlan: AiSearchPlanPayload;
  items: ExploreResultItem[];
  sourceStatuses?: SourceStatusPayload[];
  partial?: boolean;
  message?: string | null;
};

export type ExploreSearchJobStatus =
  | "queued"
  | "planning"
  | "retrieving"
  | "completed"
  | "completed_partial"
  | "failed";

export type ExploreSearchJobPayload = ExploreSearchPayload & {
  jobId: string;
  status: ExploreSearchJobStatus;
  error: string | null;
  message: string | null;
  createdAt: string;
  updatedAt: string;
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
