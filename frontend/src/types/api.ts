export type StatusPayload = {
  topicSlug: string | null;
  topicLabel: string | null;
  autoScanStarted: boolean;
  autoScanIntervalSeconds: number;
  lastScanAt: string | null;
  lastScanError: string | null;
  lastDiscoveryAt: string | null;
  lastDiscoveryError: string | null;
  lastDiscoveryResult: DiscoveryResultPayload | null;
  discoveryQueries: string[];
  watchedEntities: WatchedEntityPayload[];
  sourceCheckpoints: SourceCheckpointPayload[];
  totalSignals: number;
  matchedSignals: number;
};

export type Viewer = {
  userId: string;
  email: string;
  displayName: string;
};

export type ViewerPayload = {
  user: Viewer | null;
};

export type DiscoveryResultPayload = {
  topicSlug: string;
  queries: string[];
  candidateCount: number;
  entityCount: number;
  matchedEntityCount: number;
};

export type WatchedEntityPayload = {
  entityId: string;
  source: string;
  repo: string | null;
  url: string;
  stars: number | null;
  query: string | null;
  language: string | null;
};

export type SourceCheckpointPayload = {
  entityId: string;
  source: string;
  repo: string | null;
  checkpointKey: string;
  checkpointValue: string | null;
  updatedAt: string | null;
};

export type SignalListItem = {
  itemId: string;
  title: string;
  source: string;
  signalKind: string;
  url: string;
  matched: boolean;
  score: number;
  reason: string;
  isNew: boolean;
};

export type SignalListPayload = {
  items: SignalListItem[];
};

export type SignalDetailPayload = {
  itemId: string;
  title: string;
  source: string;
  signalKind: string;
  url: string;
  matched: boolean;
  score: number;
  reason: string;
  matchedTerms: string[];
  excludedTerms: string[];
  rawText: string;
  normalizedText: string;
  metadata: Record<string, unknown>;
  isNew: boolean;
};

export type SubscriptionItem = {
  subscriptionId: string;
  topicDescription: string;
  queryStrategy: "profile_terms" | "pending_ai";
  queries: string[];
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
  queryStrategy: "profile_terms" | "pending_ai";
  queries: string[];
  items: ExploreResultItem[];
};
