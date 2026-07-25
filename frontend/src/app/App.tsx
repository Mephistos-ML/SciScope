import { useEffect, useState } from "react";

import {
  createSubscription,
  deleteSubscription,
  fetchMe,
  fetchSubscriptions,
  runExploreSearch,
  signInDev,
  signOut,
} from "../lib/api";
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
  const [activeView, setActiveView] = useState<AppView>("explore");
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [results, setResults] = useState<ExploreResultItem[]>([]);
  const [lastQueries, setLastQueries] = useState<string[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [topicInput, setTopicInput] = useState("Paramagnetic NMR analysis workflows");
  const [queryInput, setQueryInput] = useState("pcs, paramagnetic nmr, tensor fitting");
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
    setSigningIn(true);
    setErrorMessage(null);
    try {
      const payload = await signInDev();
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
        manualQueries: queryInput
          .split(",")
          .map((term) => term.trim())
          .filter(Boolean),
      });
      setResults(payload.items);
      setLastQueries(payload.queries);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to run search.");
    } finally {
      setSearchPending(false);
    }
  }

  async function handleSubscribe() {
    if (!viewer) {
      return;
    }

    setCreatePending(true);
    setErrorMessage(null);
    try {
      const subscription = await createSubscription({
        topicDescription: topicInput.trim(),
        manualQueries: queryInput
          .split(",")
          .map((term) => term.trim())
          .filter(Boolean),
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

      {activeView === "explore" ? (
        <ExplorePage
          canSubscribe={Boolean(viewer)}
          createPending={createPending}
          queryInput={queryInput}
          lastQueries={lastQueries}
          onQueryInputChange={setQueryInput}
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
