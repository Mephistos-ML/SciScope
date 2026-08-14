import { useEffect, useState } from "react";

import {
  beginGoogleSignIn,
  createSubscription,
  deleteSubscription,
  fetchMe,
  fetchSubscriptions,
  runExploreSearch,
  signOut,
} from "../lib/api";
import { AppHeader } from "../components/AppHeader";
import { ExplorePage } from "../pages/ExplorePage";
import { FeedPage } from "../pages/FeedPage";
import type {
  AiSearchPlanPayload,
  ExploreResultItem,
  SubscriptionItem,
  Viewer,
} from "../types/api";

type AppView = "explore" | "feed";

export function App() {
  const [activeView, setActiveView] = useState<AppView>("explore");
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [results, setResults] = useState<ExploreResultItem[]>([]);
  const [lastAiSearchPlan, setLastAiSearchPlan] = useState<AiSearchPlanPayload | null>(null);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [topicInput, setTopicInput] = useState("Paramagnetic NMR analysis workflows");
  const [signingIn, setSigningIn] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [searchPending, setSearchPending] = useState(false);
  const [createPending, setCreatePending] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
        setErrorMessage(error instanceof Error ? error.message : "Failed to load app state.");
      }
    }

    void loadInitialState();
  }, []);

  useEffect(() => {
    if (!viewer) {
      setSubscriptions([]);
      setSelectedSubscriptionId(null);
      return;
    }

    async function loadSubscriptions() {
      try {
        const payload = await fetchSubscriptions();
        setSubscriptions(payload.items);
        setSelectedSubscriptionId((currentId) => currentId ?? payload.items[0]?.subscriptionId ?? null);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load subscriptions.",
        );
      }
    }

    void loadSubscriptions();
  }, [viewer]);

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
      setActiveView("explore");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to sign out.");
    } finally {
      setSigningOut(false);
    }
  }

  async function handleRunSearch() {
    setSearchPending(true);
    setErrorMessage(null);
    try {
      const payload = await runExploreSearch({
        topicDescription: topicInput.trim(),
      });
      setResults(payload.items);
      setLastAiSearchPlan(payload.aiSearchPlan);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run search.");
    } finally {
      setSearchPending(false);
    }
  }

  async function handleSubscribe() {
    if (!viewer) {
      setErrorMessage("Sign in with Google before creating a subscription.");
      return;
    }

    setCreatePending(true);
    setErrorMessage(null);
    try {
      const subscription = await createSubscription({
        topicDescription: topicInput.trim(),
      });
      setSubscriptions((current) => [subscription, ...current]);
      setSelectedSubscriptionId(subscription.subscriptionId);
      setActiveView("feed");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create subscription.");
    } finally {
      setCreatePending(false);
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
    <>
      <AppHeader
        activeView={activeView}
        onNavigate={setActiveView}
        onSignIn={() => void handleSignIn()}
        onSignOut={() => void handleSignOut()}
        signingIn={signingIn}
        signingOut={signingOut}
        viewer={viewer}
      />

      {errorMessage ? <section className="error-banner global-banner">{errorMessage}</section> : null}
      {!viewer ? (
        <section className="info-banner global-banner">
          Explore mode is public. Sign in with Google to save subscriptions and build your feed.
        </section>
      ) : null}

      {activeView === "explore" ? (
        <ExplorePage
          canSubscribe={Boolean(viewer)}
          createPending={createPending}
          lastAiSearchPlan={lastAiSearchPlan}
          onRunSearch={() => void handleRunSearch()}
          onSubscribe={() => void handleSubscribe()}
          onTopicInputChange={setTopicInput}
          results={results}
          searchPending={searchPending}
          topicInput={topicInput}
          viewer={viewer}
        />
      ) : (
        <FeedPage
          deletePending={deletePending}
          selectedSubscriptionId={selectedSubscriptionId}
          subscriptions={subscriptions}
          viewer={viewer}
          onDeleteSubscription={(subscriptionId) => void handleDeleteSubscription(subscriptionId)}
          onSelectSubscription={(subscriptionId) => void handleSelectSubscription(subscriptionId)}
        />
      )}
    </>
  );
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
