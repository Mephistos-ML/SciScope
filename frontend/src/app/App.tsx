import { useEffect, useState } from "react";

import {
  createSubscription,
  deleteSubscription,
  fetchMe,
  fetchSubscriptions,
  runExploreSearch,
  signInWithDevSession,
  signOut,
} from "../lib/api";
import { frontendConfig } from "../lib/config";
import { AppHeader } from "../components/AppHeader";
import { ExplorePage } from "../pages/ExplorePage";
import { FeedPage } from "../pages/FeedPage";
import type {
  ExploreResultItem,
  SubscriptionItem,
  Viewer,
} from "../types/api";

type AppView = "explore" | "feed";

export function App() {
  const { authMode } = frontendConfig;
  const [activeView, setActiveView] = useState<AppView>("explore");
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [results, setResults] = useState<ExploreResultItem[]>([]);
  const [lastQueries, setLastQueries] = useState<string[]>([]);
  const [lastQueryStrategy, setLastQueryStrategy] = useState<"generated" | "override" | null>(
    null,
  );
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [topicInput, setTopicInput] = useState("Paramagnetic NMR analysis workflows");
  const [queryOverridesInput, setQueryOverridesInput] = useState("");
  const [signingIn, setSigningIn] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [searchPending, setSearchPending] = useState(false);
  const [createPending, setCreatePending] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
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
    if (authMode !== "dev") {
      setErrorMessage("Authentication is not enabled in this environment yet.");
      return;
    }

    setSigningIn(true);
    setErrorMessage(null);
    try {
      const payload = await signInWithDevSession();
      setViewer(payload.user);
      setActiveView("explore");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to sign in.");
    } finally {
      setSigningIn(false);
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
        queryOverrides: parseQueryOverrides(queryOverridesInput),
      });
      setResults(payload.items);
      setLastQueries(payload.queries);
      setLastQueryStrategy(payload.queryStrategy);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run search.");
    } finally {
      setSearchPending(false);
    }
  }

  async function handleSubscribe() {
    if (!viewer) {
      setErrorMessage(
        authMode === "dev"
          ? "Sign in before creating a subscription."
          : "Authentication is not enabled in this environment yet.",
      );
      return;
    }

    setCreatePending(true);
    setErrorMessage(null);
    try {
      const subscription = await createSubscription({
        topicDescription: topicInput.trim(),
        queryOverrides: parseQueryOverrides(queryOverridesInput),
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
        authMode={authMode}
        onNavigate={setActiveView}
        onSignIn={() => void handleSignIn()}
        onSignOut={() => void handleSignOut()}
        signingIn={signingIn}
        signingOut={signingOut}
        viewer={viewer}
      />

      {errorMessage ? <section className="error-banner global-banner">{errorMessage}</section> : null}
      {!viewer && authMode !== "dev" ? (
        <section className="info-banner global-banner">
          Explore mode is public. Saved subscriptions will unlock after the real authentication flow is added.
        </section>
      ) : null}

      {activeView === "explore" ? (
        <ExplorePage
          authMode={authMode}
          canSubscribe={Boolean(viewer)}
          createPending={createPending}
          lastQueries={lastQueries}
          lastQueryStrategy={lastQueryStrategy}
          onQueryOverridesInputChange={setQueryOverridesInput}
          onRunSearch={() => void handleRunSearch()}
          onSubscribe={() => void handleSubscribe()}
          onTopicInputChange={setTopicInput}
          queryOverridesInput={queryOverridesInput}
          results={results}
          searchPending={searchPending}
          topicInput={topicInput}
          viewer={viewer}
        />
      ) : (
        <FeedPage
          authMode={authMode}
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

function parseQueryOverrides(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}
