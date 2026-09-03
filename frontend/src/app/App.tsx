import { useEffect, useState } from "react";

import {
  ApiError,
  beginGoogleSignIn,
  createExploreSearchJob,
  createSubscription,
  deleteSubscription,
  fetchFeed,
  fetchExploreSearchJob,
  fetchMe,
  fetchSubscriptions,
  signOut,
} from "../lib/api";
import { frontendConfig } from "../lib/config";
import { AppShell } from "../components/AppShell";
import { AboutPage } from "../pages/AboutPage";
import { ExplorePage } from "../pages/ExplorePage";
import { FeedPage } from "../pages/FeedPage";
import { SubscriptionsPage } from "../pages/SubscriptionsPage";
import type {
  AiSearchPlanPayload,
  FeedEventItem,
  ExploreSearchJobPayload,
  ExploreSearchJobStatus,
  ExploreResultItem,
  SubscriptionItem,
  Viewer,
} from "../types/api";

type AppView = "explore" | "feed" | "subscriptions" | "about";

type ExploreSearchFeedback = {
  message: string;
  retryUntilEpochMs: number | null;
  signInSuggested: boolean;
  turnstileRequired: boolean;
};

export function App() {
  const [activeView, setActiveView] = useState<AppView>("explore");
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [results, setResults] = useState<ExploreResultItem[]>([]);
  const [lastAiSearchPlan, setLastAiSearchPlan] = useState<AiSearchPlanPayload | null>(null);
  const [feedEvents, setFeedEvents] = useState<FeedEventItem[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [topicInput, setTopicInput] = useState("");
  const [signingIn, setSigningIn] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [searchPending, setSearchPending] = useState(false);
  const [createPendingRepositoryId, setCreatePendingRepositoryId] = useState<string | null>(
    null,
  );
  const [deletePending, setDeletePending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [exploreSearchFeedback, setExploreSearchFeedback] = useState<ExploreSearchFeedback | null>(
    null,
  );
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [activeExploreJobId, setActiveExploreJobId] = useState<string | null>(null);
  const [lastCompletedExploreJobId, setLastCompletedExploreJobId] = useState<string | null>(null);
  const [activeExploreJobStatus, setActiveExploreJobStatus] =
    useState<ExploreSearchJobStatus | null>(null);
  const [betaMode, setBetaMode] = useState(false);

  useEffect(() => {
    const authError = readAuthErrorFromUrl();
    if (authError) {
      setErrorMessage(mapAuthErrorMessage(authError));
      clearAuthErrorFromUrl();
    }

    async function loadInitialState() {
      try {
        const viewerPayload = await fetchMe();
        setViewer(viewerPayload.user);
      } catch (error) {
        if (!isApiUnavailableError(error)) {
          setErrorMessage(error instanceof Error ? error.message : "Failed to load app state.");
        }
      }
    }

    void loadInitialState();
  }, []);

  useEffect(() => {
    if (!viewer) {
      setFeedEvents([]);
      setSubscriptions([]);
      setSelectedSubscriptionId(null);
      return;
    }

    async function loadViewerData() {
      try {
        const [subscriptionPayload, feedPayload] = await Promise.all([
          fetchSubscriptions(),
          fetchFeed(),
        ]);
        setSubscriptions(subscriptionPayload.items);
        setFeedEvents(feedPayload.items);
        setSelectedSubscriptionId(
          (currentId) => currentId ?? subscriptionPayload.items[0]?.subscriptionId ?? null,
        );
      } catch (error) {
        if (!isApiUnavailableError(error)) {
          setErrorMessage(
            error instanceof Error ? error.message : "Failed to load signed-in data.",
          );
        }
      }
    }

    void loadViewerData();
  }, [viewer]);

  useEffect(() => {
    if (!activeExploreJobId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const syncJob = async () => {
      try {
        const snapshot = await fetchExploreSearchJob(activeExploreJobId);
        if (cancelled) {
          return;
        }
        setActiveExploreJobStatus(snapshot.status);

        if (snapshot.status === "completed" || snapshot.status === "completed_partial") {
          applyExploreSearchJobSnapshot(snapshot);
          setLastCompletedExploreJobId(snapshot.jobId);
          setSearchPending(false);
          setActiveExploreJobId(null);
          setActiveExploreJobStatus(null);
          if (snapshot.status === "completed_partial" && snapshot.message) {
            setExploreSearchFeedback({
              message: snapshot.message,
              retryUntilEpochMs: null,
              signInSuggested: false,
              turnstileRequired: false,
            });
          }
          return;
        }

        if (snapshot.status === "failed") {
          setSearchPending(false);
          setActiveExploreJobId(null);
          setActiveExploreJobStatus(null);
          setExploreSearchFeedback({
            message: snapshot.error ?? "Failed to run search.",
            retryUntilEpochMs: null,
            signInSuggested: false,
            turnstileRequired: false,
          });
          return;
        }

        timeoutId = window.setTimeout(() => {
          void syncJob();
        }, 1000);
      } catch (error) {
        if (cancelled) {
          return;
        }

        setSearchPending(false);
        setActiveExploreJobId(null);
        setActiveExploreJobStatus(null);
        setExploreSearchFeedback({
          message: error instanceof Error ? error.message : "Failed to refresh search status.",
          retryUntilEpochMs: null,
          signInSuggested: false,
          turnstileRequired: false,
        });
      }
    };

    void syncJob();

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [activeExploreJobId]);

  async function handleSignIn() {
    setSigningIn(true);
    setErrorMessage(null);
    try {
      beginGoogleSignIn();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to sign in.");
      setSigningIn(false);
      return;
    } finally {
      window.setTimeout(() => setSigningIn(false), 1000);
    }
  }

  async function handleSignOut() {
    setSigningOut(true);
    setErrorMessage(null);
    try {
      const payload = await signOut();
      setViewer(payload.user);
      setBetaMode(false);
      setActiveView("explore");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to sign out.");
    } finally {
      setSigningOut(false);
    }
  }

  async function handleRunSearch() {
    if (!topicInput.trim()) {
      return;
    }

    setSearchPending(true);
    setErrorMessage(null);
    setResults([]);
    setLastCompletedExploreJobId(null);
    setLastAiSearchPlan(null);
    setExploreSearchFeedback(null);
    try {
      const job = await createExploreSearchJob({
        topicDescription: topicInput.trim(),
        turnstileToken,
        betaMode: betaMode && (viewer?.features.includes("explore_beta") ?? false),
      });
      setActiveExploreJobId(job.jobId);
      setActiveExploreJobStatus(job.status);
      setTurnstileToken(null);
      setTurnstileResetKey((current) => current + 1);
    } catch (error) {
      if (isApiUnavailableError(error)) {
        window.alert(error.message);
      } else if (error instanceof ApiError) {
        setExploreSearchFeedback({
          message: error.message,
          retryUntilEpochMs:
            error.retryAfterSeconds !== null ? Date.now() + error.retryAfterSeconds * 1000 : null,
          signInSuggested: error.signInSuggested,
          turnstileRequired: error.turnstileRequired,
        });
        if (error.turnstileRequired) {
          setTurnstileToken(null);
          setTurnstileResetKey((current) => current + 1);
        }
      } else {
        setExploreSearchFeedback({
          message: error instanceof Error ? error.message : "Failed to run search.",
          retryUntilEpochMs: null,
          signInSuggested: false,
          turnstileRequired: false,
        });
        setResults([]);
        setLastAiSearchPlan(null);
      }
      setActiveExploreJobId(null);
      setActiveExploreJobStatus(null);
      setSearchPending(false);
    }
  }

  function applyExploreSearchJobSnapshot(snapshot: ExploreSearchJobPayload) {
    setResults(snapshot.items);
    setLastAiSearchPlan(snapshot.aiSearchPlan);
    if (snapshot.status !== "failed" && snapshot.status !== "completed_partial") {
      setExploreSearchFeedback(null);
    }
  }

  async function handleSubscribe(result: ExploreResultItem) {
    if (!viewer) {
      setErrorMessage("Sign in with Google before creating a subscription.");
      return;
    }

    setCreatePendingRepositoryId(result.itemId);
    setErrorMessage(null);
    try {
      const subscription = await createSubscription({
        repository: {
          itemId: result.itemId,
          source: result.source,
          fullName: result.fullName,
          url: result.url,
        },
        selectedQuery: result.query,
      });
      setSubscriptions((current) => {
        const existingIndex = current.findIndex(
          (item) => item.repository.repositoryId === subscription.repository.repositoryId,
        );
        if (existingIndex >= 0) {
          const next = [...current];
          next[existingIndex] = subscription;
          return next;
        }
        return [subscription, ...current];
      });
      setSelectedSubscriptionId(subscription.subscriptionId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create subscription.");
    } finally {
      setCreatePendingRepositoryId(null);
    }
  }

  async function handleSelectSubscription(subscriptionId: string) {
    setSelectedSubscriptionId(subscriptionId);
  }

  async function handleDeleteSubscription(subscriptionId: string) {
    setDeletePending(true);
    setErrorMessage(null);

    try {
      await deleteSubscription(subscriptionId);
      const remainingSubscriptions = subscriptions.filter(
        (subscription) => subscription.subscriptionId !== subscriptionId,
      );
      setSubscriptions(remainingSubscriptions);
      setSelectedSubscriptionId((current) =>
        current === subscriptionId ? (remainingSubscriptions[0]?.subscriptionId ?? null) : current,
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete subscription.");
    } finally {
      setDeletePending(false);
    }
  }

  return (
    <AppShell
      activeView={activeView}
      onNavigate={setActiveView}
      onSignIn={() => void handleSignIn()}
      onSignOut={() => void handleSignOut()}
      signingIn={signingIn}
      signingOut={signingOut}
      viewer={viewer}
    >
      {errorMessage ? <section className="shell-alert shell-alert-error">{errorMessage}</section> : null}

      {activeView === "explore" ? (
        <ExplorePage
          canSubscribe={Boolean(viewer)}
          exploreSearchFeedback={exploreSearchFeedback}
          lastAiSearchPlan={lastAiSearchPlan}
          betaMode={betaMode}
          betaEnabled={viewer?.features.includes("explore_beta") ?? false}
          onBetaModeChange={setBetaMode}
          onRunSearch={() => void handleRunSearch()}
          onSignIn={() => void handleSignIn()}
          onSubscribe={(result) => void handleSubscribe(result)}
          onTopicInputChange={setTopicInput}
          onTurnstileTokenChange={setTurnstileToken}
          results={results}
          searchJobId={lastCompletedExploreJobId}
          searchPending={searchPending}
          subscribePendingRepositoryId={createPendingRepositoryId}
          subscribedRepositoryIds={subscriptions.map((item) => item.repository.repositoryId)}
          topicInput={topicInput}
          searchStageLabel={mapExploreJobStatusToStage(activeExploreJobStatus)}
          turnstileReady={Boolean(turnstileToken)}
          turnstileResetKey={turnstileResetKey}
          turnstileSiteKey={frontendConfig.turnstileSiteKey}
          viewer={viewer}
        />
      ) : null}
      {activeView === "feed" ? (
        <FeedPage
          feedEvents={feedEvents}
          viewer={viewer}
        />
      ) : null}
      {activeView === "subscriptions" ? (
        <SubscriptionsPage
          deletePending={deletePending}
          selectedSubscriptionId={selectedSubscriptionId}
          subscriptions={subscriptions}
          onDeleteSubscription={(subscriptionId) => void handleDeleteSubscription(subscriptionId)}
          onSelectSubscription={(subscriptionId) => void handleSelectSubscription(subscriptionId)}
          viewer={viewer}
        />
      ) : null}
      {activeView === "about" ? <AboutPage /> : null}
    </AppShell>
  );
}

function mapExploreJobStatusToStage(
  status: ExploreSearchJobStatus | null,
): string | null {
  if (status === "queued" || status === "planning") {
    return "Understanding your topic";
  }
  if (status === "retrieving") {
    return "Searching repositories";
  }
  return null;
}

function readAuthErrorFromUrl(): string | null {
  const currentUrl = new URL(window.location.href);
  const value = currentUrl.searchParams.get("authError")?.trim();
  return value || null;
}

function clearAuthErrorFromUrl(): void {
  const currentUrl = new URL(window.location.href);
  currentUrl.searchParams.delete("authError");
  window.history.replaceState({}, "", currentUrl.toString());
}

function mapAuthErrorMessage(authError: string): string {
  switch (authError) {
    case "google_access_denied":
      return "Google sign-in was cancelled before access was granted.";
    case "google_session_expired":
      return "Google sign-in expired before it completed. Please try again.";
    case "google_state_mismatch":
      return "Google sign-in could not be verified securely. Please try again.";
    case "google_missing_code":
      return "Google sign-in returned without an authorization code.";
    case "google_auth_failed":
      return "Google sign-in failed on the server. Please try again.";
    default:
      return "Google sign-in failed. Please try again.";
  }
}

function isApiUnavailableError(error: unknown): error is Error {
  return (
    error instanceof Error &&
    error.message === "The SciScope API is unreachable right now. Please try again."
  );
}
