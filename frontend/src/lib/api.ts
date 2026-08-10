import type {
  ExploreSearchPayload,
  SignalDetailPayload,
  SignalListPayload,
  StatusPayload,
  SubscriptionItem,
  SubscriptionListPayload,
  ViewerPayload,
} from "../types/api";
import { frontendConfig } from "./config";

type ApiErrorPayload = {
  error?: string;
  detail?: string;
};

class ApiError extends Error {
  constructor(message: string, readonly status: number | null = null) {
    super(message);
    this.name = "ApiError";
  }
}

function buildApiUrl(path: string): string {
  return `${frontendConfig.apiBaseUrl}${path}`;
}

async function parseResponseJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = await parseResponseJson<ApiErrorPayload>(response);
    if (typeof payload.error === "string" && payload.error.trim() !== "") {
      return payload.error;
    }

    if (typeof payload.detail === "string" && payload.detail.trim() !== "") {
      return payload.detail;
    }
  }

  return `Request failed with status ${response.status}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), frontendConfig.requestTimeoutMs);

  try {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");

    const response = await fetch(buildApiUrl(path), {
      ...init,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiError(await readErrorMessage(response), response.status);
    }

    return await parseResponseJson<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The API request timed out. Please try again.");
    }

    throw new ApiError("The SciScope API is unreachable right now. Please try again.");
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function fetchStatus(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/status");
}

export async function fetchMe(): Promise<ViewerPayload> {
  return requestJson<ViewerPayload>("/api/me");
}

export async function signInWithDevSession(): Promise<ViewerPayload> {
  return requestJson<ViewerPayload>("/api/auth/dev-login", {
    method: "POST",
  });
}

export async function signOut(): Promise<ViewerPayload> {
  return requestJson<ViewerPayload>("/api/logout", {
    method: "POST",
  });
}

export async function fetchSubscriptions(): Promise<SubscriptionListPayload> {
  return requestJson<SubscriptionListPayload>("/api/subscriptions");
}

export async function createSubscription(payload: {
  topicDescription: string;
  manualQueries: string[];
}): Promise<SubscriptionItem> {
  return requestJson<SubscriptionItem>("/api/subscriptions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function deleteSubscription(subscriptionId: string): Promise<{ deleted: true }> {
  return requestJson<{ deleted: true }>(`/api/subscriptions/${subscriptionId}`, {
    method: "DELETE",
  });
}

export async function runExploreSearch(payload: {
  topicDescription: string;
  manualQueries: string[];
}): Promise<ExploreSearchPayload> {
  return requestJson<ExploreSearchPayload>("/api/explore/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function fetchSignals(): Promise<SignalListPayload> {
  return requestJson<SignalListPayload>("/api/signals");
}

export async function fetchSignalDetail(itemId: string): Promise<SignalDetailPayload> {
  return requestJson<SignalDetailPayload>(`/api/signals/${itemId}`);
}

export async function startScan(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/start", {
    method: "POST",
  });
}

export async function stopScan(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/stop", {
    method: "POST",
  });
}
