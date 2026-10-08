import type { ExploreSearchRunPayload, ExploreSearchRunStatus } from "../types/api";

type SearchRunPresentation =
  | { state: "pending"; stageLabel: string }
  | { state: "completed" }
  | { state: "error"; fallbackMessage: string };

export const searchRunPresentation = {
  queued: { state: "pending", stageLabel: "Waiting to start search" },
  running: { state: "pending", stageLabel: "Searching repositories" },
  completed: { state: "completed" },
  completed_partial: { state: "completed" },
  failed: { state: "error", fallbackMessage: "Failed to run search." },
  interrupted: {
    state: "error",
    fallbackMessage: "Search was interrupted. Start a new search.",
  },
} satisfies Record<ExploreSearchRunStatus, SearchRunPresentation>;

export function pollExploreSearchRun({
  fetchSnapshot,
  onSnapshot,
  onError,
}: {
  fetchSnapshot: () => Promise<ExploreSearchRunPayload>;
  onSnapshot: (snapshot: ExploreSearchRunPayload) => void;
  onError: (error: unknown) => void;
}): () => void {
  let cancelled = false;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  async function poll() {
    if (cancelled) {
      return;
    }
    try {
      const snapshot = await fetchSnapshot();
      if (cancelled) {
        return;
      }
      const presentation = searchRunPresentation[snapshot.status];
      onSnapshot(snapshot);
      if (!cancelled && presentation.state === "pending") {
        timeoutId = setTimeout(() => void poll(), 1000);
      }
    } catch (error) {
      if (!cancelled) {
        onError(error);
      }
    }
  }

  void poll();
  return () => {
    cancelled = true;
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
  };
}
