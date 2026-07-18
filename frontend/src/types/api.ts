export type StatusPayload = {
  topicSlug: string;
  topicLabel: string;
  autoScanStarted: boolean;
  autoScanIntervalSeconds: number;
  lastScanAt: string | null;
  lastScanError: string | null;
  totalSignals: number;
  matchedSignals: number;
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
