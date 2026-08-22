import type {
  ExploreAccessErrorPayload,
  ExploreSearchJobPayload,
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
  }
}

export async function fetchStatus(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/status");
}

export async function fetchMe(): Promise<ViewerPayload> {
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

export async function fetchSubscriptions(): Promise<SubscriptionListPayload> {
  return requestJson<SubscriptionListPayload>("/api/subscriptions");
}

export async function createSubscription(payload: {
  repository: {
    itemId: string;
    source: string;
    fullName: string;
    url: string;
  };
  selectedQuery: string | null;
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

export async function createExploreSearchJob(payload: {
  topicDescription: string;
  turnstileToken?: string | null;
}): Promise<ExploreSearchJobPayload> {
  return requestJson<ExploreSearchJobPayload>("/api/explore/search-jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export async function fetchExploreSearchJob(jobId: string): Promise<ExploreSearchJobPayload> {
  return requestJson<ExploreSearchJobPayload>(`/api/explore/search-jobs/${jobId}`);
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
