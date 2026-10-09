import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  beginGoogleSignIn,
  createExploreSearchRun,
  createSubscription,
  deleteAccount,
  deleteSubscription,
  fetchFeedGroups,
  fetchExploreSearchRun,
  fetchSearchDiagnosticsReport,
  expandExploreSearchRun,
  fetchMe,
  fetchSubscriptions,
  markAllFeedEventsRead,
  markFeedGroupRead,
  signOut,
} from "../lib/api";
import { frontendConfig } from "../lib/config";
import { pollExploreSearchRun, searchRunPresentation } from "../lib/searchRuns";
import { AppShell } from "../components/AppShell";
import { AboutPage } from "../pages/AboutPage";
import { AccountPage } from "../pages/AccountPage";
import { ExplorePage } from "../pages/ExplorePage";
import { FeedPage } from "../pages/FeedPage";
import { PrivacyPage, TermsPage } from "../pages/LegalPages";
import { SubscriptionsPage } from "../pages/SubscriptionsPage";
import type {
  AiSearchPlanPayload,
  FeedGroupItem,
  ExploreSearchRunPayload,
  ExploreSearchRunStatus,
  ExploreResultItem,
  SearchDiagnosticsReport,
  SubscriptionItem,
  Viewer,
} from "../types/api";

type AppView = "explore" | "feed" | "subscriptions" | "about" | "account" | "privacy" | "terms";
type BootstrapStatus = "loading" | "ready" | "error";

const VIEW_PATHS: Record<AppView, string> = {
  explore: "/",
  feed: "/feed",
  subscriptions: "/subscriptions",
  about: "/about",
  account: "/account",
  privacy: "/privacy",
  terms: "/terms",
};

type ExploreSearchFeedback = {
  message: string;
  retryUntilEpochMs: number | null;
  signInSuggested: boolean;
  turnstileRequired: boolean;
};

export function App() {
  const [activeView, setActiveView] = useState<AppView>(() => viewFromPath(window.location.pathname));
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus>("loading");
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [results, setResults] = useState<ExploreResultItem[]>([]);
  const [lastAiSearchPlan, setLastAiSearchPlan] = useState<AiSearchPlanPayload | null>(null);
  const [feedGroups, setFeedGroups] = useState<FeedGroupItem[]>([]);
  const [unreadFeedCount, setUnreadFeedCount] = useState(0);
  const [feedState, setFeedState] = useState<"all" | "unread">("all");
  const [feedSubscriptionId, setFeedSubscriptionId] = useState<string | null>(null);
  const [feedNextCursor, setFeedNextCursor] = useState<string | null>(null);
  const [feedHasMore, setFeedHasMore] = useState(false);
  const [feedLoadPending, setFeedLoadPending] = useState(false);
  const [subscriptions, setSubscriptions] = useState<SubscriptionItem[]>([]);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [topicInput, setTopicInput] = useState("");
  const [signingIn, setSigningIn] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [searchPending, setSearchPending] = useState(false);
  const [isExpandingSearch, setIsExpandingSearch] = useState(false);
  const [canExpandSearch, setCanExpandSearch] = useState(false);
  const [createPendingRepositoryId, setCreatePendingRepositoryId] = useState<string | null>(
    null,
  );
  const [deletePending, setDeletePending] = useState(false);
  const [accountDeletePending, setAccountDeletePending] = useState(false);
  const [feedUpdatePending, setFeedUpdatePending] = useState(false);
  const feedRequestVersion = useRef(0);
  const pendingFeedNavigation = useRef<number | null>(null);
  const feedReadRevision = useRef(0);
  const feedVisibility = useRef(feedState);
  feedVisibility.current = feedState;
  const feedMutationPending = useRef(false);
  const feedUserId = useRef<string | null>(null);
  feedUserId.current = viewer?.userId ?? null;
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [exploreSearchFeedback, setExploreSearchFeedback] = useState<ExploreSearchFeedback | null>(
    null,
  );
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [turnstileResetKey, setTurnstileResetKey] = useState(0);
  const [exploreGuestAccessToken, setExploreGuestAccessToken] = useState<string | null>(null);
  const [activeExploreJobId, setActiveExploreJobId] = useState<string | null>(null);
  const [lastCompletedExploreJobId, setLastCompletedExploreJobId] = useState<string | null>(null);
  const [activeExploreJobStatus, setActiveExploreJobStatus] =
    useState<ExploreSearchRunStatus | null>(null);
  const [searchDiagnosticsRequested, setSearchDiagnosticsRequested] = useState(
    () => isSearchDiagnosticsRequested(window.location.search),
  );
  const [searchDiagnosticsReport, setSearchDiagnosticsReport] =
    useState<SearchDiagnosticsReport | null>(null);
  const [searchDiagnosticsLoading, setSearchDiagnosticsLoading] = useState(false);
  const [searchDiagnosticsUnavailable, setSearchDiagnosticsUnavailable] = useState(false);
  const [lastCompletedExploreRunVersion, setLastCompletedExploreRunVersion] = useState<string | null>(
    null,
  );
  const hasSearchDiagnosticsAccess = viewer?.features.includes("search_diagnostics") === true;
  const searchDiagnosticsActive = hasSearchDiagnosticsAccess && searchDiagnosticsRequested;

  useEffect(() => {
    const authError = readAuthErrorFromUrl();
    if (authError) {
      setErrorMessage(mapAuthErrorMessage(authError));
      clearAuthErrorFromUrl();
    }

    let cancelled = false;
    async function loadInitialState() {
      try {
        const viewerPayload = await fetchMe();
        if (cancelled) return;
        setViewer(viewerPayload.user);
        if (viewerPayload.user) {
          const [subscriptionPayload, feedPayload] = await Promise.all([
            fetchSubscriptions(),
            fetchFeedGroups(),
          ]);
          if (cancelled) return;
          setSubscriptions(subscriptionPayload.items);
          setFeedGroups(feedPayload.items);
          setUnreadFeedCount(feedPayload.unreadCount);
          setFeedState("all");
          setFeedNextCursor(feedPayload.nextCursor);
          setFeedHasMore(feedPayload.hasMore);
          setSelectedSubscriptionId(subscriptionPayload.items[0]?.subscriptionId ?? null);
        }
        if (!cancelled) setBootstrapStatus("ready");
      } catch {
        if (!cancelled) setBootstrapStatus("error");
      }
    }

    void loadInitialState();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const syncViewFromHistory = () => {
      const nextView = viewFromPath(window.location.pathname);
      cancelPendingFeedNavigation();
      if (activeView === "feed" && nextView !== "feed" && feedSubscriptionId) {
        void restoreGlobalFeed();
      }
      setActiveView(nextView);
      setSearchDiagnosticsRequested(isSearchDiagnosticsRequested(window.location.search));
    };
    window.addEventListener("popstate", syncViewFromHistory);
    return () => window.removeEventListener("popstate", syncViewFromHistory);
  }, [activeView, feedSubscriptionId, feedState]);

  useEffect(() => {
    if (viewer) {
      return;
    }

    feedRequestVersion.current += 1;
    setFeedLoadPending(false);
    setFeedSubscriptionId(null);
    setFeedGroups([]);
    setUnreadFeedCount(0);
    setFeedState("all");
    setFeedNextCursor(null);
    setFeedHasMore(false);
    setSubscriptions([]);
    setSelectedSubscriptionId(null);
  }, [viewer]);

  useEffect(() => {
    if (!searchDiagnosticsActive || !lastCompletedExploreJobId || !lastCompletedExploreRunVersion) {
      setSearchDiagnosticsReport(null);
      setSearchDiagnosticsLoading(false);
      setSearchDiagnosticsUnavailable(false);
      return;
    }

    let cancelled = false;
    setSearchDiagnosticsLoading(true);
    setSearchDiagnosticsUnavailable(false);

    void fetchSearchDiagnosticsReport(lastCompletedExploreJobId)
      .then((report) => {
        if (!cancelled) {
          setSearchDiagnosticsReport(report);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSearchDiagnosticsReport(null);
          setSearchDiagnosticsUnavailable(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSearchDiagnosticsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    lastCompletedExploreJobId,
    lastCompletedExploreRunVersion,
    searchDiagnosticsActive,
  ]);

  useEffect(() => {
    if (!activeExploreJobId) {
      return;
    }

    return pollExploreSearchRun({
      fetchSnapshot: () => fetchExploreSearchRun(activeExploreJobId, exploreGuestAccessToken),
      onSnapshot: (snapshot) => {
        setActiveExploreJobStatus(snapshot.status);
        const presentation = searchRunPresentation[snapshot.status];

        if (presentation.state === "completed") {
          applyExploreSearchRunSnapshot(snapshot);
          setLastCompletedExploreJobId(snapshot.runId);
          setLastCompletedExploreRunVersion(snapshot.updatedAt);
          setSearchPending(false);
          setCanExpandSearch(snapshot.canExpand === true);
          setActiveExploreJobId(null);
          setActiveExploreJobStatus(null);
          if (isExpandingSearch) {
            setExploreSearchFeedback({
              message: snapshot.message ?? "Search expanded with another scientific angle.",
              retryUntilEpochMs: null,
              signInSuggested: false,
              turnstileRequired: false,
            });
            setIsExpandingSearch(false);
          } else if (snapshot.status === "completed_partial" && snapshot.message) {
            setExploreSearchFeedback({
              message: snapshot.message,
              retryUntilEpochMs: null,
              signInSuggested: false,
              turnstileRequired: false,
            });
          }
          return;
        }

        if (presentation.state === "error") {
          setLastCompletedExploreJobId(snapshot.runId);
          setLastCompletedExploreRunVersion(snapshot.updatedAt);
          setSearchPending(false);
          setIsExpandingSearch(false);
          setCanExpandSearch(false);
          setActiveExploreJobId(null);
          setActiveExploreJobStatus(null);
          setExploreSearchFeedback({
            message: snapshot.error ?? presentation.fallbackMessage,
            retryUntilEpochMs: null,
            signInSuggested: false,
            turnstileRequired: false,
          });
          return;
        }
      },
      onError: (error) => {
        if (error instanceof ApiError && error.status === 404) {
          clearUnavailableExploreRun();
        }
        setSearchPending(false);
        setIsExpandingSearch(false);
        setActiveExploreJobId(null);
        setActiveExploreJobStatus(null);
        setExploreSearchFeedback({
          message: error instanceof ApiError && error.status === 404
            ? "This search is no longer available. Start a new search."
            : error instanceof Error ? error.message : "Failed to refresh search status.",
          retryUntilEpochMs: null,
          signInSuggested: false,
          turnstileRequired: false,
        });
      },
    });
  }, [activeExploreJobId, exploreGuestAccessToken, isExpandingSearch]);

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
      navigateTo("explore");
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
    setIsExpandingSearch(false);
    setCanExpandSearch(false);
    setErrorMessage(null);
    setResults([]);
    setActiveExploreJobId(null);
    setExploreGuestAccessToken(null);
    setLastCompletedExploreJobId(null);
    setLastCompletedExploreRunVersion(null);
    setLastAiSearchPlan(null);
    setExploreSearchFeedback(null);
    try {
      const job = await createExploreSearchRun({
        topicDescription: topicInput.trim(),
        turnstileToken,
      });
      setExploreGuestAccessToken(job.guestAccessToken ?? null);
      setActiveExploreJobId(job.runId);
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

  async function handleExpandSearch() {
    if (!lastCompletedExploreJobId || searchPending || !canExpandSearch) {
      return;
    }

    setSearchPending(true);
    setIsExpandingSearch(true);
    setLastCompletedExploreRunVersion(null);
    setExploreSearchFeedback(null);
    try {
      const job = await expandExploreSearchRun(lastCompletedExploreJobId, exploreGuestAccessToken, turnstileToken);
      setTurnstileToken(null);
      setTurnstileResetKey((current) => current + 1);
      setActiveExploreJobId(job.runId);
      setActiveExploreJobStatus(job.status);
    } catch (error) {
      setSearchPending(false);
      setIsExpandingSearch(false);
      if (error instanceof ApiError && error.status === 404) {
        clearUnavailableExploreRun();
      }
      if (turnstileToken || (error instanceof ApiError && error.turnstileRequired)) {
        setTurnstileToken(null);
        setTurnstileResetKey((current) => current + 1);
      }
      setExploreSearchFeedback({
        message: error instanceof ApiError && error.status === 404
          ? "This search is no longer available. Start a new search."
          : error instanceof Error ? error.message : "Could not expand search.",
        retryUntilEpochMs: error instanceof ApiError && error.retryAfterSeconds !== null
          ? Date.now() + error.retryAfterSeconds * 1000 : null,
        signInSuggested: error instanceof ApiError && error.signInSuggested,
        turnstileRequired: error instanceof ApiError && error.turnstileRequired,
      });
    }
  }

  function clearUnavailableExploreRun() {
    setCanExpandSearch(false);
    setActiveExploreJobId(null);
    setActiveExploreJobStatus(null);
    setLastCompletedExploreJobId(null);
    setLastCompletedExploreRunVersion(null);
    setExploreGuestAccessToken(null);
  }

  function applyExploreSearchRunSnapshot(snapshot: ExploreSearchRunPayload) {
    setResults(snapshot.items);
    setLastAiSearchPlan(snapshot.aiSearchPlan);
    setCanExpandSearch(snapshot.canExpand === true);
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
        },
        selectedQuery: result.query,
      });
      setSubscriptions((current) => {
        const existingIndex = current.findIndex(
          (item) => item.repository.repositoryId === subscription.repository.repositoryId,
        );
        if (existingIndex >= 0) {
          const next = [...current];
          next[existingIndex] = { ...subscription, unreadGroupCount: current[existingIndex].unreadGroupCount };
          return next;
        }
        return [{ ...subscription, unreadGroupCount: 0 }, ...current];
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

  async function handleDeleteAccount() {
    setAccountDeletePending(true);
    setErrorMessage(null);
    try {
      await deleteAccount();
      setViewer(null);
      navigateTo("explore");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to delete account.");
    } finally {
      setAccountDeletePending(false);
    }
  }

  async function refreshFeedReadCounts(userId: string | null) {
    const [feed, saved] = await Promise.all([fetchFeedGroups({ limit: 1 }), fetchSubscriptions()]);
    if (feedUserId.current !== userId) return;
    setUnreadFeedCount(feed.unreadCount);
    setSubscriptions(saved.items);
  }

  async function handleMarkFeedGroupRead(groupId: string) {
    if (feedMutationPending.current || feedLoadPending) return;
    feedMutationPending.current = true;
    feedRequestVersion.current += 1;
    const userId = feedUserId.current;
    setFeedUpdatePending(true);
    setErrorMessage(null);
    let marked = false;
    try {
      const group = await markFeedGroupRead(groupId);
      if (feedUserId.current !== userId) return;
      marked = true;
      feedReadRevision.current += 1;
      setFeedGroups((current) => feedVisibility.current === "unread"
        ? current.filter((item) => item.groupId !== groupId)
        : current.map((item) => item.groupId === groupId ? group : item));
      await refreshFeedReadCounts(userId);
    } catch (error) {
      if (feedUserId.current === userId) {
        setErrorMessage(marked ? "Update marked read, but counts could not be refreshed. Reload the page."
          : error instanceof Error ? error.message : "Failed to mark update as read.");
      }
    } finally {
      feedMutationPending.current = false;
      setFeedUpdatePending(false);
    }
  }

  async function handleMarkAllFeedEventsRead() {
    if (feedMutationPending.current || feedLoadPending) return;
    feedMutationPending.current = true;
    feedRequestVersion.current += 1;
    const userId = feedUserId.current;
    setFeedUpdatePending(true);
    setErrorMessage(null);
    let marked = false;
    try {
      await markAllFeedEventsRead();
      if (feedUserId.current !== userId) return;
      marked = true;
      feedReadRevision.current += 1;
      setFeedGroups((current) => feedVisibility.current === "unread" ? [] : current.map((item) => ({ ...item, isRead: true, unreadEventCount: 0 })));
      if (feedVisibility.current === "unread") {
        setFeedNextCursor(null);
        setFeedHasMore(false);
      }
      await refreshFeedReadCounts(userId);
    } catch (error) {
      if (feedUserId.current === userId) {
        setErrorMessage(marked ? "Updates marked read, but counts could not be refreshed. Reload the page."
          : error instanceof Error ? error.message : "Failed to mark updates as read.");
      }
    } finally {
      feedMutationPending.current = false;
      setFeedUpdatePending(false);
    }
  }

  async function loadFeedGroups(options: { state: "all" | "unread"; subscriptionId: string | null; cursor?: string }): Promise<boolean> {
    const version = ++feedRequestVersion.current;
    const readRevision = feedReadRevision.current;
    const userId = feedUserId.current;
    setFeedLoadPending(true);
    setErrorMessage(null);
    try {
      const payload = await fetchFeedGroups({ ...options, subscriptionId: options.subscriptionId ?? undefined });
      if (version !== feedRequestVersion.current || feedUserId.current !== userId) return false;
      // Navigation may start a list request while an explicit read is still committing.
      if (readRevision !== feedReadRevision.current) return loadFeedGroups(options);
      setFeedState(options.state);
      setFeedSubscriptionId(options.subscriptionId);
      setFeedGroups((current) => options.cursor
        ? [...current, ...payload.items.filter((item) => !current.some((existing) => existing.groupId === item.groupId))]
        : payload.items);
      setFeedNextCursor(payload.nextCursor);
      setFeedHasMore(payload.hasMore);
      setUnreadFeedCount(payload.unreadCount);
      return true;
    } catch (error) {
      if (version === feedRequestVersion.current && feedUserId.current === userId) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to load Feed updates.");
      }
      return false;
    } finally {
      if (version === feedRequestVersion.current) setFeedLoadPending(false);
    }
  }

  async function handleFeedStateChange(nextState: "all" | "unread") {
    if (nextState === feedState || feedMutationPending.current || feedLoadPending) return;
    await loadFeedGroups({ state: nextState, subscriptionId: feedSubscriptionId });
  }

  async function handleLoadOlderFeedGroups() {
    if (!feedNextCursor || feedLoadPending || feedMutationPending.current) return;
    await loadFeedGroups({ cursor: feedNextCursor, state: feedState, subscriptionId: feedSubscriptionId });
  }

  async function restoreGlobalFeed() {
    await loadFeedGroups({ state: feedState, subscriptionId: null });
  }

  function handleViewChange(nextView: AppView) {
    navigateTo(nextView);
    if (activeView === "feed" && nextView !== "feed" && feedSubscriptionId) {
      void restoreGlobalFeed();
    }
  }

  function handleToggleSearchDiagnostics() {
    cancelPendingFeedNavigation();
    const nextRequested = !searchDiagnosticsActive;
    const nextUrl = new URL(window.location.href);
    nextUrl.pathname = VIEW_PATHS.explore;
    if (nextRequested) {
      nextUrl.searchParams.set("diagnostics", "1");
    } else {
      nextUrl.searchParams.delete("diagnostics");
    }
    window.history.pushState({}, "", `${nextUrl.pathname}${nextUrl.search}`);
    setSearchDiagnosticsRequested(nextRequested);
    setActiveView("explore");
  }

  function navigateTo(nextView: AppView) {
    cancelPendingFeedNavigation();
    const nextPath = VIEW_PATHS[nextView];
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    if (nextView !== "explore") {
      setSearchDiagnosticsRequested(false);
    }
    setActiveView(nextView);
  }

  function cancelPendingFeedNavigation() {
    if (pendingFeedNavigation.current === null) return;
    pendingFeedNavigation.current = null;
    feedRequestVersion.current += 1;
    setFeedLoadPending(false);
  }

  async function handleViewSubscriptionFeed(subscriptionId: string) {
    if (feedMutationPending.current) return;
    const version = feedRequestVersion.current + 1;
    pendingFeedNavigation.current = version;
    try {
      if (await loadFeedGroups({ state: "all", subscriptionId })) navigateTo("feed");
    } finally {
      if (pendingFeedNavigation.current === version) pendingFeedNavigation.current = null;
    }
  }

  return (
    <AppShell
      activeView={activeView}
      isBootstrapping={bootstrapStatus === "loading"}
      onNavigate={handleViewChange}
      onOpenAccount={() => handleViewChange("account")}
      onToggleSearchDiagnostics={handleToggleSearchDiagnostics}
      onSignIn={() => void handleSignIn()}
      onSignOut={() => void handleSignOut()}
      searchDiagnosticsActive={searchDiagnosticsActive}
      signingIn={signingIn}
      signingOut={signingOut}
      unreadFeedCount={unreadFeedCount}
      viewer={viewer}
    >
      {bootstrapStatus === "loading" ? (
        <AppLoadingState />
      ) : bootstrapStatus === "error" ? (
        <AppUnavailableState />
      ) : (
        <>
          {errorMessage ? <section className="shell-alert shell-alert-error" role="alert">{errorMessage}</section> : null}

          {activeView === "explore" ? (
            <ExplorePage
              canSubscribe={Boolean(viewer)}
              exploreSearchFeedback={exploreSearchFeedback}
              lastAiSearchPlan={lastAiSearchPlan}
              onRunSearch={() => void handleRunSearch()}
              onExpandSearch={() => void handleExpandSearch()}
              onSignIn={() => void handleSignIn()}
              onSubscribe={(result) => void handleSubscribe(result)}
              onTopicInputChange={setTopicInput}
              onTurnstileTokenChange={setTurnstileToken}
              results={results}
              canExpandSearch={canExpandSearch}
              isExpandingSearch={isExpandingSearch}
              searchPending={searchPending}
              searchDiagnosticsActive={searchDiagnosticsActive}
              searchDiagnosticsReport={searchDiagnosticsReport}
              searchDiagnosticsStatus={
                searchDiagnosticsLoading
                  ? "loading"
                  : searchDiagnosticsUnavailable
                    ? "unavailable"
                    : searchDiagnosticsReport
                      ? "ready"
                      : "idle"
              }
              subscribePendingRepositoryId={createPendingRepositoryId}
              subscribedRepositoryIds={subscriptions.map((item) => item.repository.repositoryId)}
              topicInput={topicInput}
              searchStageLabel={
                isExpandingSearch
                  ? "Expanding search…"
                  : mapExploreJobStatusToStage(activeExploreJobStatus)
              }
              turnstileReady={Boolean(turnstileToken)}
              turnstileResetKey={turnstileResetKey}
              turnstileSiteKey={frontendConfig.turnstileSiteKey}
              viewer={viewer}
            />
          ) : null}
          {activeView === "feed" ? (
            <FeedPage
              feedUpdatePending={feedUpdatePending}
              feedLoadPending={feedLoadPending}
              feedGroups={feedGroups}
              feedHasMore={feedHasMore}
              feedState={feedState}
              feedSubscriptionId={feedSubscriptionId}
              unreadFeedCount={unreadFeedCount}
              onLoadOlder={() => void handleLoadOlderFeedGroups()}
              onMarkAllRead={() => void handleMarkAllFeedEventsRead()}
              onMarkRead={(groupId) => void handleMarkFeedGroupRead(groupId)}
              onStateChange={(state) => void handleFeedStateChange(state)}
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
              onViewAllUpdates={(subscriptionId) => void handleViewSubscriptionFeed(subscriptionId)}
              viewer={viewer}
            />
          ) : null}
          {activeView === "about" ? <AboutPage /> : null}
          {activeView === "account" && viewer ? (
            <AccountPage
              deleting={accountDeletePending}
              onDelete={() => void handleDeleteAccount()}
              onSignOut={() => void handleSignOut()}
              viewer={viewer}
            />
          ) : null}
          {activeView === "privacy" ? <PrivacyPage /> : null}
          {activeView === "terms" ? <TermsPage /> : null}
        </>
      )}
    </AppShell>
  );
}

function AppLoadingState() {
  return (
    <section aria-live="polite" className="app-loading-state">
      <span className="app-loading-indicator" />
      <span>Loading SciScope…</span>
    </section>
  );
}

function AppUnavailableState() {
  return (
    <section className="results-panel">
      <article className="empty-state-panel feed-empty-state">
        <h1 className="empty-state-title">SciScope is temporarily unavailable</h1>
        <p className="empty-state-copy">
          We could not load your session and repository data. Please try again in a moment.
        </p>
        <button className="outline-button" onClick={() => window.location.reload()} type="button">
          Try again
        </button>
      </article>
    </section>
  );
}

function viewFromPath(pathname: string): AppView {
  const normalizedPath = pathname.replace(/\/+$/, "") || "/";
  const view = (Object.keys(VIEW_PATHS) as AppView[]).find(
    (candidate) => VIEW_PATHS[candidate] === normalizedPath,
  );
  return view ?? "explore";
}

function isSearchDiagnosticsRequested(search: string): boolean {
  return new URLSearchParams(search).get("diagnostics") === "1";
}

function mapExploreJobStatusToStage(
  status: ExploreSearchRunStatus | null,
): string | null {
  if (status === null) {
    return null;
  }
  const presentation = searchRunPresentation[status];
  return presentation.state === "pending" ? presentation.stageLabel : null;
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
