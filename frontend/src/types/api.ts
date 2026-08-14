export type StatusPayload = {
  subscriptionCount: number;
  subscriptions: StatusSubscriptionPayload[];
  autoScanStarted: boolean;
  autoScanIntervalSeconds: number;
  lastScanAt: string | null;
  lastScanError: string | null;
  watchedRepositories: WatchedRepositoryPayload[];
  sourceCheckpoints: SourceCheckpointPayload[];
  totalSignals: number;
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

export type SignalListItem = {
  itemId: string;
  viewId: string;
  subscriptionId: string;
  repositoryId: string;
  repositoryFullName: string;
  selectedQuery: string | null;
  title: string;
  source: string;
  signalKind: string;
  url: string;
  publishedAt: string | null;
  isNew: boolean;
};

export type SignalListPayload = {
  items: SignalListItem[];
};

export type SignalDetailPayload = {
  itemId: string;
  viewId: string;
  subscriptionId: string;
  repositoryId: string;
  repositoryFullName: string;
  selectedQuery: string | null;
  title: string;
  source: string;
  signalKind: string;
  url: string;
  publishedAt: string | null;
  rawText: string;
  normalizedText: string;
  metadata: Record<string, unknown>;
  isNew: boolean;
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
