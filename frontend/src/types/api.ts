export type StatusPayload = {
  topicSlug: string;
  topicLabel: string;
  autoScanStarted: boolean;
  autoScanIntervalSeconds: number;
  lastScanAt: string | null;
  lastScanError: string | null;
  lastDiscoveryAt: string | null;
  lastDiscoveryError: string | null;
  lastDiscoveryResult: DiscoveryResultPayload | null;
  discoveryQueries: string[];
  watchedRepositories: WatchedRepositoryPayload[];
  releaseCheckpoints: ReleaseCheckpointPayload[];
  totalSignals: number;
  matchedSignals: number;
};

export type DiscoveryResultPayload = {
  topicSlug: string;
  queries: string[];
  candidateCount: number;
  entityCount: number;
  matchedEntityCount: number;
};

export type WatchedRepositoryPayload = {
  entityId: string;
  repo: string | null;
  url: string;
  stars: number | null;
  query: string | null;
  language: string | null;
};

export type ReleaseCheckpointPayload = {
  entityId: string;
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
