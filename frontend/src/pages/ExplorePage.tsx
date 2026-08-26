import { useEffect, useState } from "react";

import type {
  AiSearchPlanPayload,
  ExploreAdmissionSummaryPayload,
  ExploreResultItem,
  ViewerPayload,
} from "../types/api";
import { SourceBadge } from "../components/SourceBadge";
import { TurnstileWidget } from "../components/TurnstileWidget";
import exploreEmptyIllustration from "../assets/states/explore/explore-empty.svg";
import noResultsIllustration from "../assets/states/explore/search-no-results.svg";

type ExploreSearchFeedback = {
  message: string;
  retryUntilEpochMs: number | null;
  signInSuggested: boolean;
  turnstileRequired: boolean;
};

type ExplorePageProps = {
  canSubscribe: boolean;
  exploreSearchFeedback: ExploreSearchFeedback | null;
  lastAdmissionSummary: ExploreAdmissionSummaryPayload | null;
  lastAiSearchPlan: AiSearchPlanPayload | null;
  onRunSearch: () => void;
  onSignIn: () => void;
  onSubscribe: (result: ExploreResultItem) => void;
  onTopicInputChange: (value: string) => void;
  onTurnstileTokenChange: (token: string | null) => void;
  results: ExploreResultItem[];
  searchPending: boolean;
  subscribePendingRepositoryId: string | null;
  subscribedRepositoryIds: string[];
  topicInput: string;
  turnstileReady: boolean;
  turnstileResetKey: number;
  turnstileSiteKey: string | null;
  viewer: ViewerPayload["user"];
};

export function ExplorePage({
  canSubscribe,
  exploreSearchFeedback,
  lastAdmissionSummary,
  lastAiSearchPlan,
  onRunSearch,
  onSignIn,
  onSubscribe,
  onTopicInputChange,
  onTurnstileTokenChange,
  results,
  searchPending,
  subscribePendingRepositoryId,
  subscribedRepositoryIds,
  topicInput,
  turnstileReady,
  turnstileResetKey,
  turnstileSiteKey,
  viewer,
}: ExplorePageProps) {
  const hasResults = results.length > 0;
  const isPreSearch = !searchPending && !lastAiSearchPlan && !hasResults;
  const isNoResults = !searchPending && !isPreSearch && !hasResults;
  const requiresTurnstile = exploreSearchFeedback?.turnstileRequired === true;
  const [retrySecondsRemaining, setRetrySecondsRemaining] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    const retryUntilEpochMs = exploreSearchFeedback?.retryUntilEpochMs;
    if (!retryUntilEpochMs) {
      setRetrySecondsRemaining(null);
      return;
    }

    const syncRemainingSeconds = () => {
      const nextRemaining = Math.max(
        Math.ceil((retryUntilEpochMs - Date.now()) / 1000),
        0,
      );
      setRetrySecondsRemaining(nextRemaining);
    };

    syncRemainingSeconds();
    const intervalId = window.setInterval(syncRemainingSeconds, 1000);
    return () => window.clearInterval(intervalId);
  }, [exploreSearchFeedback?.retryUntilEpochMs]);

  useEffect(() => {
    setCurrentPage(1);
  }, [results]);

  const retryLockActive = retrySecondsRemaining !== null && retrySecondsRemaining > 0;
  const searchDisabled =
    searchPending ||
    !topicInput.trim() ||
    retryLockActive ||
    (requiresTurnstile && !turnstileReady);
  const searchButtonLabel = searchPending
    ? "Searching"
    : retryLockActive
      ? `Try Again in ${formatRetryCountdown(retrySecondsRemaining)}`
      : requiresTurnstile && !turnstileReady
      ? "Complete Verification"
      : "Run Search";
  const showLoadingResults = searchPending;
  const totalPages = Math.max(1, Math.ceil(results.length / RESULTS_PER_PAGE));
  const visibleResults = results.slice(
    (currentPage - 1) * RESULTS_PER_PAGE,
    currentPage * RESULTS_PER_PAGE,
  );
  const visibleRangeStart = hasResults ? (currentPage - 1) * RESULTS_PER_PAGE + 1 : 0;
  const visibleRangeEnd = hasResults
    ? Math.min(currentPage * RESULTS_PER_PAGE, results.length)
    : 0;
  const pageNumbers = buildPageNumbers(totalPages, currentPage);

  return (
    <main className="app-shell explore-shell">
      <section className="page-intro explore-intro">
        <div className="page-intro-main">
          <h1 className="page-title">Explore Scientific Software</h1>
          <p className="section-copy">
            Discover repositories across GitHub, GitLab, Gitee, GitCode and GitVerse.
          </p>
        </div>
      </section>

      <section className="explore-query-layout">
        <article className="query-workspace">
          <label className="field-label" htmlFor="topic-query">
            Topic Description
          </label>
          <textarea
            id="topic-query"
            className="text-field text-area explore-query-input"
            value={topicInput}
            onChange={(event) => onTopicInputChange(event.target.value)}
            placeholder="Enter a research topic, method or software area..."
          />
          <p className="field-hint">
            {viewer
              ? "SciScope will generate discovery queries and let you subscribe to specific repositories from the results."
              : "SciScope will generate discovery queries and search across all sources."}
          </p>
          {!viewer ? (
            <p className="query-context-note">
              Explore mode is public.{" "}
              <button className="query-context-link" onClick={onSignIn} type="button">
                Sign In with Google
              </button>{" "}
              to save subscriptions and build your feed.
            </p>
          ) : null}
          {exploreSearchFeedback ? (
            <div className="query-feedback-panel">
              <p className="query-feedback-copy">{exploreSearchFeedback.message}</p>
              {requiresTurnstile ? (
                <>
                  <p className="query-feedback-meta">
                    {turnstileReady
                      ? "Verification complete. Run Search to continue."
                      : "Complete the verification challenge to continue."}
                  </p>
                  <TurnstileWidget
                    onTokenChange={onTurnstileTokenChange}
                    resetKey={turnstileResetKey}
                    siteKey={turnstileSiteKey}
                  />
                </>
              ) : retryLockActive ? (
                <p className="query-feedback-meta">
                  You can run the next search in {formatRetryCountdown(retrySecondsRemaining)}.
                </p>
              ) : null}
              {exploreSearchFeedback.signInSuggested && !viewer ? (
                <div className="query-feedback-actions">
                  <button className="outline-button" onClick={onSignIn} type="button">
                    Sign In with Google
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="query-actions">
            <button
              className={
                searchPending
                  ? "solid-button search-submit-button solid-button-loading"
                  : "solid-button search-submit-button"
              }
              disabled={searchDisabled}
              onClick={onRunSearch}
              type="button"
            >
              <span className="search-submit-button-label">{searchButtonLabel}</span>
            </button>
          </div>
        </article>
      </section>

      {isPreSearch ? (
        <section className="results-panel">
          <article className="empty-state-panel explore-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={exploreEmptyIllustration}
            />
            <h2 className="empty-state-title">Start Exploring</h2>
            <p className="empty-state-copy">
              Enter a topic above and run search to discover relevant repositories
              from multiple hosts.
            </p>
          </article>
        </section>
      ) : (
        <section className="results-panel">
          <article className="info-panel repository-results-panel">
            <div className="results-header">
              <div className="results-header-main">
                <p className="section-kicker">Results</p>
                <div className="results-title-row">
                  <h3 className="panel-title">Matched Repositories</h3>
                  {hasResults ? (
                    <span className="results-count-badge">{results.length} results</span>
                  ) : searchPending ? (
                    <span className="results-count-badge">Searching...</span>
                  ) : null}
                  {lastAdmissionSummary?.mode === "shadow" ? (
                    <span className="results-count-badge results-count-badge-debug">
                      {lastAdmissionSummary.keptCount} keep / {lastAdmissionSummary.rejectedCount} reject
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="results-plan-summary">
                {lastAiSearchPlan?.queries.length ? (
                  <>
                    <p className="field-hint">AI-Generated Search Queries</p>
                    <div className="query-chip-row">
                      {lastAiSearchPlan.queries.map((query) => (
                        <span className="query-chip" key={query}>
                          {query}
                        </span>
                      ))}
                    </div>
                  </>
                ) : showLoadingResults ? (
                  <>
                    <p className="field-hint">AI-Generated Search Queries</p>
                    <div className="query-chip-row query-chip-row-loading" aria-hidden="true">
                      {LOADING_QUERY_CHIP_WIDTHS.map((width, index) => (
                        <span
                          className="query-chip query-chip-skeleton skeleton-shimmer"
                          key={`loading-chip-${index}`}
                          style={{ width }}
                        />
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="empty-copy">
                    Run a search to see the queries produced for the current AI search plan.
                  </p>
                )}
              </div>
            </div>

            {showLoadingResults ? (
              <>
                <div className="repository-table">
                  <div className="repository-table-head">
                    <span>Repository</span>
                    <span>Source</span>
                    <span>Language</span>
                    <span>Stars</span>
                    <span>Query</span>
                    <span>Actions</span>
                  </div>

                  <div className="repository-table-body">
                    {LOADING_REPOSITORY_ROW_COUNT.map((rowIndex) => (
                      <div
                        className="repository-row repository-row-skeleton"
                        key={`loading-row-${rowIndex}`}
                      >
                        <div className="repository-main-cell">
                          <span className="repository-skeleton-title skeleton-shimmer" />
                          <span className="repository-skeleton-copy skeleton-shimmer" />
                          <div className="repository-term-row" aria-hidden="true">
                            <span className="repository-term-chip repository-term-chip-skeleton skeleton-shimmer" />
                            <span className="repository-term-chip repository-term-chip-skeleton skeleton-shimmer repository-term-chip-skeleton-wide" />
                            <span className="repository-term-chip repository-term-chip-skeleton skeleton-shimmer" />
                          </div>
                        </div>

                        <div className="repository-cell">
                          <span className="repository-skeleton-badge skeleton-shimmer" />
                        </div>

                        <div className="repository-cell repository-metadata-cell">
                          <span className="repository-skeleton-meta skeleton-shimmer" />
                        </div>

                        <div className="repository-cell repository-metadata-cell">
                          <span className="repository-skeleton-meta repository-skeleton-meta-short skeleton-shimmer" />
                        </div>

                        <div className="repository-cell repository-query-cell">
                          <span className="repository-skeleton-query skeleton-shimmer" />
                        </div>

                        <div className="repository-cell repository-actions-cell">
                          <span className="repository-skeleton-button skeleton-shimmer" />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : hasResults ? (
              <>
                <div className="repository-table">
                  <div className="repository-table-head">
                    <span>Repository</span>
                    <span>Source</span>
                    <span>Language</span>
                    <span>Stars</span>
                    <span>Query</span>
                    <span>Actions</span>
                  </div>

                  <div className="repository-table-body">
                    {visibleResults.map((result) => {
                      const isSubscribed = subscribedRepositoryIds.includes(result.itemId);
                      const isPending = subscribePendingRepositoryId === result.itemId;

                      return (
                        <div className="repository-row" key={result.itemId}>
                          <div className="repository-main-cell">
                            <p className="repository-title">{result.fullName}</p>
                            <p className="repository-description">
                              {result.description || result.reason}
                            </p>
                            {lastAdmissionSummary?.mode === "shadow" && result.admission ? (
                              <div className="repository-admission-row">
                                <span
                                  className={
                                    result.admission.decision === "keep"
                                      ? "repository-admission-badge repository-admission-badge-keep"
                                      : "repository-admission-badge repository-admission-badge-reject"
                                  }
                                >
                                  {result.admission.decision === "keep" ? "Keep" : "Reject"}
                                </span>
                                <span className="repository-admission-copy">
                                  {result.admission.reasons[0] ?? result.reason}
                                </span>
                              </div>
                            ) : null}
                            {result.matchedTerms.length > 0 ? (
                              <div className="repository-term-row">
                                {result.matchedTerms.map((term) => (
                                  <span className="repository-term-chip" key={`${result.itemId}-${term}`}>
                                    {term}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>

                          <div className="repository-cell">
                            <SourceBadge href={result.url} source={result.source} />
                          </div>

                          <div className="repository-cell repository-metadata-cell">
                            {result.language ? (
                              <span className="repository-dot-metadata">
                                <span className="repository-language-dot" aria-hidden="true" />
                                {result.language}
                              </span>
                            ) : (
                              <span className="repository-muted-value">-</span>
                            )}
                          </div>

                          <div className="repository-cell repository-metadata-cell">
                            {result.stars !== null ? formatCompactNumber(result.stars) : "-"}
                          </div>

                          <div className="repository-cell repository-query-cell">
                            {result.query || "No Query Snapshot"}
                          </div>

                          <div className="repository-cell repository-actions-cell">
                            <button
                              className={
                                isSubscribed
                                  ? "outline-button results-action-button results-action-button-subscribed"
                                  : "solid-button results-action-button"
                              }
                              disabled={!canSubscribe || isSubscribed || isPending}
                              onClick={() => onSubscribe(result)}
                              type="button"
                            >
                              {isSubscribed ? "Subscribed" : isPending ? "Saving..." : "Subscribe"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="results-footer">
                  <p className="results-footer-copy">
                    Showing {visibleRangeStart}-{visibleRangeEnd} of {results.length} results
                  </p>
                  {totalPages > 1 ? (
                    <nav aria-label="Results pages" className="pagination-nav">
                      <button
                        className="pagination-button"
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                        type="button"
                      >
                        Previous
                      </button>
                      <div className="pagination-pages">
                        {pageNumbers.map((pageToken, index) =>
                          pageToken === "ellipsis-left" || pageToken === "ellipsis-right" ? (
                            <span
                              aria-hidden="true"
                              className="pagination-ellipsis"
                              key={`${pageToken}-${index}`}
                            >
                              ...
                            </span>
                          ) : (
                            <button
                              aria-current={pageToken === currentPage ? "page" : undefined}
                              className={
                                pageToken === currentPage
                                  ? "pagination-button pagination-button-active"
                                  : "pagination-button"
                              }
                              key={pageToken}
                              onClick={() => setCurrentPage(pageToken)}
                              type="button"
                            >
                              {pageToken}
                            </button>
                          ),
                        )}
                      </div>
                      <button
                        className="pagination-button"
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                        type="button"
                      >
                        Next
                      </button>
                    </nav>
                  ) : null}
                </div>
              </>
            ) : (
              <div className="empty-state-panel search-no-results-state">
                <img
                  alt=""
                  aria-hidden="true"
                  className="empty-state-illustration search-no-results-illustration"
                  src={noResultsIllustration}
                />
                <h2 className="empty-state-title">No Repositories Found</h2>
                <p className="empty-state-copy">
                  Try refining the topic description or broadening the query terms to
                  discover more repositories.
                </p>
              </div>
            )}
          </article>
        </section>
      )}
    </main>
  );
}

const LOADING_QUERY_CHIP_WIDTHS = ["148px", "112px", "176px"] as const;
const LOADING_REPOSITORY_ROW_COUNT = [0, 1, 2, 3, 4] as const;
const RESULTS_PER_PAGE = 10;

function formatCompactNumber(value: number): string {
  if (value >= 1000) {
    const compactValue = value / 1000;
    return compactValue >= 10 ? `${Math.round(compactValue)}k` : `${compactValue.toFixed(1)}k`;
  }

  return `${value}`;
}

function formatRetryCountdown(value: number | null): string {
  if (!value || value <= 0) {
    return "0s";
  }

  if (value < 60) {
    return `${value}s`;
  }

  const totalMinutes = Math.floor(value / 60);
  const seconds = value % 60;
  if (totalMinutes < 60) {
    return seconds === 0 ? `${totalMinutes}m` : `${totalMinutes}m ${seconds}s`;
  }

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
}

function buildPageNumbers(
  totalPages: number,
  currentPage: number,
): Array<number | "ellipsis-left" | "ellipsis-right"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "ellipsis-right", totalPages];
  }

  if (currentPage >= totalPages - 3) {
    return [1, "ellipsis-left", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  }

  return [
    1,
    "ellipsis-left",
    currentPage - 2,
    currentPage - 1,
    currentPage,
    currentPage + 1,
    currentPage + 2,
    "ellipsis-right",
    totalPages,
  ];
}
