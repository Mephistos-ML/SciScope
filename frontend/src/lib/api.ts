import type {
  ExploreAccessErrorPayload,
  FeedGroupDetailPayload,
  FeedGroupItem,
  FeedGroupListPayload,
  SearchDiagnosticsReport,
  ExploreSearchRunPayload,
  ExploreSearchRunCreatedPayload,
  ExploreSearchPayload,
  SubscriptionItem,
  SubscriptionListPayload,
  ViewerPayload,
} from "../types/api";
import { frontendConfig } from "./config";

const demoViewerPayload: ViewerPayload = {
  user: {
    userId: "demo_account",
    email: "ernest@example.com",
    displayName: "Ernest Borysenko",
    avatarUrl: null,
    features: [],
  },
};

type ApiErrorPayload = {
  error?: string;
  detail?: string;
  code?: string;
  retryAfterSeconds?: number;
  signInSuggested?: boolean;
  turnstileRequired?: boolean;
};

export class ApiError extends Error {
  readonly code: string | null;
  readonly retryAfterSeconds: number | null;
  readonly signInSuggested: boolean;
  readonly turnstileRequired: boolean;

  constructor(
    message: string,
    readonly status: number | null = null,
    options: {
      code?: string | null;
      retryAfterSeconds?: number | null;
      signInSuggested?: boolean;
      turnstileRequired?: boolean;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.signInSuggested = options.signInSuggested ?? false;
    this.turnstileRequired = options.turnstileRequired ?? false;
  }
}

function buildApiUrl(path: string): string {
  return `${frontendConfig.apiBaseUrl}${path}`;
}

async function parseResponseJson<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

async function readErrorPayload(response: Response): Promise<ExploreAccessErrorPayload | null> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = await parseResponseJson<ApiErrorPayload>(response);
    if (typeof payload.error === "string" && payload.error.trim() !== "") {
      return {
        error: payload.error,
        code: typeof payload.code === "string" && payload.code.trim() ? payload.code.trim() : undefined,
        retryAfterSeconds:
          typeof payload.retryAfterSeconds === "number" ? payload.retryAfterSeconds : undefined,
        signInSuggested: payload.signInSuggested === true,
        turnstileRequired: payload.turnstileRequired === true,
      };
    }

    if (typeof payload.detail === "string" && payload.detail.trim() !== "") {
      return { error: payload.detail };
    }
  }

  return null;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const abortRequest = () => controller.abort();
  init?.signal?.addEventListener("abort", abortRequest, { once: true });
  if (init?.signal?.aborted) controller.abort();
  const timeoutId = window.setTimeout(() => controller.abort(), frontendConfig.requestTimeoutMs);

  try {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");

    const response = await fetch(buildApiUrl(path), {
      ...init,
      credentials: "include",
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorPayload = await readErrorPayload(response);
      throw new ApiError(
        errorPayload?.error ?? `Request failed with status ${response.status}`,
        response.status,
        {
          code: errorPayload?.code ?? null,
          retryAfterSeconds: errorPayload?.retryAfterSeconds ?? null,
          signInSuggested: errorPayload?.signInSuggested ?? false,
          turnstileRequired: errorPayload?.turnstileRequired ?? false,
        },
      );
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
    init?.signal?.removeEventListener("abort", abortRequest);
  }
}

export async function fetchMe(): Promise<ViewerPayload> {
  if (import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE === "true") {
    return demoViewerPayload;
  }
  return requestJson<ViewerPayload>("/api/me");
}

export function beginGoogleSignIn(): void {
  window.location.assign(buildApiUrl("/api/auth/google/start"));
}

export async function signOut(): Promise<ViewerPayload> {
  return requestJson<ViewerPayload>("/api/logout", {
    method: "POST",
  });
}

export async function deleteAccount(): Promise<{ deleted: true }> {
  return requestJson<{ deleted: true }>("/api/account", { method: "DELETE" });
}

export async function fetchSubscriptions(): Promise<SubscriptionListPayload> {
  return requestJson<SubscriptionListPayload>("/api/subscriptions");
}

export async function createSubscription(payload: {
  repository: {
    itemId: string;
  };
  selectedQuery: string | null;
}): Promise<Omit<SubscriptionItem, "unreadGroupCount">> {
  return requestJson<Omit<SubscriptionItem, "unreadGroupCount">>("/api/subscriptions", {
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
  turnstileToken?: string | null;
}): Promise<ExploreSearchPayload> {
  return requestJson<ExploreSearchPayload>("/api/explore/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function createExploreSearchRun(payload: {
  topicDescription: string;
  turnstileToken?: string | null;
}): Promise<ExploreSearchRunCreatedPayload> {
  return requestJson<ExploreSearchRunCreatedPayload>("/api/explore/search-runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function fetchExploreSearchRun(
  runId: string,
  guestAccessToken: string | null,
): Promise<ExploreSearchRunPayload> {
  return requestJson<ExploreSearchRunPayload>(`/api/explore/search-runs/${encodeURIComponent(runId)}`, {
    headers: guestAccessToken ? { "X-Search-Run-Token": guestAccessToken } : undefined,
  });
}

export async function expandExploreSearchRun(
  runId: string,
  guestAccessToken: string | null,
  turnstileToken: string | null,
): Promise<ExploreSearchRunPayload> {
  return requestJson<ExploreSearchRunPayload>(`/api/explore/search-runs/${encodeURIComponent(runId)}/expand`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(guestAccessToken ? { "X-Search-Run-Token": guestAccessToken } : {}),
    },
    body: JSON.stringify({ turnstileToken }),
  });
}

export async function fetchSearchDiagnosticsReport(runId: string): Promise<SearchDiagnosticsReport> {
  return requestJson<SearchDiagnosticsReport>(
    `/api/internal/search-runs/${encodeURIComponent(runId)}/report`,
  );
}

export async function fetchFeedGroups(options: { cursor?: string; state?: "all" | "unread"; subscriptionId?: string; limit?: number } = {}): Promise<FeedGroupListPayload> {
  const parameters = new URLSearchParams({ limit: String(options.limit ?? 20), state: options.state ?? "all" });
  if (options.cursor) parameters.set("cursor", options.cursor);
  if (options.subscriptionId) parameters.set("subscription_id", options.subscriptionId);
  return requestJson<FeedGroupListPayload>(`/api/feed/groups?${parameters}`);
}

export async function fetchFeedGroup(groupId: string, options: { cursor?: string; signal?: AbortSignal } = {}): Promise<FeedGroupDetailPayload> {
  const parameters = new URLSearchParams({ limit: "10" });
  if (options.cursor) parameters.set("cursor", options.cursor);
  return requestJson<FeedGroupDetailPayload>(`/api/feed/groups/${encodeURIComponent(groupId)}?${parameters}`, { signal: options.signal });
}

export async function markFeedGroupRead(groupId: string): Promise<FeedGroupItem> {
  return requestJson<FeedGroupItem>(`/api/feed/groups/${encodeURIComponent(groupId)}`, { method: "PATCH" });
}

export async function markAllFeedEventsRead(): Promise<{ updatedCount: number }> {
  return requestJson<{ updatedCount: number }>("/api/feed/read-all", {
    method: "POST",
  });
}
