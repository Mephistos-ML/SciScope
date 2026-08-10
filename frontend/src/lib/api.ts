import type {
  ExploreSearchPayload,
  SignalDetailPayload,
  SignalListPayload,
  StatusPayload,
  SubscriptionItem,
  SubscriptionListPayload,
  ViewerPayload,
} from "../types/api";

const API_BASE_URL = readApiBaseUrl();

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

function readApiBaseUrl(): string {
  const value = import.meta.env.VITE_API_BASE_URL;
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error("Missing required frontend environment variable: VITE_API_BASE_URL");
  }

  return value.replace(/\/+$/, "");
}

function buildApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function fetchStatus(): Promise<StatusPayload> {
  const response = await fetch(buildApiUrl("/api/status"));
  return readJson<StatusPayload>(response);
}

export async function fetchMe(): Promise<ViewerPayload> {
  const response = await fetch(buildApiUrl("/api/me"));
  return readJson<ViewerPayload>(response);
}

export async function signInDev(): Promise<ViewerPayload> {
  const response = await fetch(buildApiUrl("/api/auth/dev-login"), {
    method: "POST",
  });
  return readJson<ViewerPayload>(response);
}

export async function signOut(): Promise<ViewerPayload> {
  const response = await fetch(buildApiUrl("/api/logout"), {
    method: "POST",
  });
  return readJson<ViewerPayload>(response);
}

export async function fetchSubscriptions(): Promise<SubscriptionListPayload> {
  const response = await fetch(buildApiUrl("/api/subscriptions"));
  return readJson<SubscriptionListPayload>(response);
}

export async function createSubscription(payload: {
  topicDescription: string;
  manualQueries: string[];
}): Promise<SubscriptionItem> {
  const response = await fetch(buildApiUrl("/api/subscriptions"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<SubscriptionItem>(response);
}

export async function deleteSubscription(subscriptionId: string): Promise<{ deleted: true }> {
  const response = await fetch(buildApiUrl(`/api/subscriptions/${subscriptionId}`), {
    method: "DELETE",
  });
  return readJson<{ deleted: true }>(response);
}

export async function runExploreSearch(payload: {
  topicDescription: string;
  manualQueries: string[];
}): Promise<ExploreSearchPayload> {
  const response = await fetch(buildApiUrl("/api/explore/search"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return readJson<ExploreSearchPayload>(response);
}

export async function fetchSignals(): Promise<SignalListPayload> {
  const response = await fetch(buildApiUrl("/api/signals"));
  return readJson<SignalListPayload>(response);
}

export async function fetchSignalDetail(itemId: string): Promise<SignalDetailPayload> {
  const response = await fetch(buildApiUrl(`/api/signals/${itemId}`));
  return readJson<SignalDetailPayload>(response);
}

export async function startScan(): Promise<StatusPayload> {
  const response = await fetch(buildApiUrl("/api/start"), {
    method: "POST",
  });
  return readJson<StatusPayload>(response);
}

export async function stopScan(): Promise<StatusPayload> {
  const response = await fetch(buildApiUrl("/api/stop"), {
    method: "POST",
  });
  return readJson<StatusPayload>(response);
}
