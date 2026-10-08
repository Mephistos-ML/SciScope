import { useEffect, useMemo, useState } from "react";

import type {
  AiSearchPlanPayload,
  ExploreResultItem,
  SearchDiagnosticsRankingSnapshot,
  SearchDiagnosticsReport,
  ViewerPayload,
} from "../types/api";
import { SearchDiagnosticsRepositoryDetails } from "../components/SearchDiagnosticsRepositoryDetails";
import { SearchDiagnosticsSummary } from "../components/SearchDiagnosticsSummary";
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

type ExploreSortOption = "relevance" | "recent_activity" | "stars";
type SearchDiagnosticsStatus = "idle" | "loading" | "ready" | "unavailable";

type ExplorePageProps = {
  canExpandSearch: boolean;
  canSubscribe: boolean;
  exploreSearchFeedback: ExploreSearchFeedback | null;
  lastAiSearchPlan: AiSearchPlanPayload | null;
  onRunSearch: () => void;
  onExpandSearch: () => void;
  onSignIn: () => void;
  onSubscribe: (result: ExploreResultItem) => void;
  onTopicInputChange: (value: string) => void;
  onTurnstileTokenChange: (token: string | null) => void;
  results: ExploreResultItem[];
  isExpandingSearch: boolean;
  searchPending: boolean;
  subscribePendingRepositoryId: string | null;
  subscribedRepositoryIds: string[];
  topicInput: string;
  searchStageLabel: string | null;
  searchDiagnosticsActive: boolean;
  searchDiagnosticsReport: SearchDiagnosticsReport | null;
  searchDiagnosticsStatus: SearchDiagnosticsStatus;
  turnstileReady: boolean;
  turnstileResetKey: number;
  turnstileSiteKey: string | null;
  viewer: ViewerPayload["user"];
};

export function ExplorePage({
  canExpandSearch,
  canSubscribe,
  exploreSearchFeedback,
  lastAiSearchPlan,
  onRunSearch,
  onExpandSearch,
  onSignIn,
  onSubscribe,
  onTopicInputChange,
  onTurnstileTokenChange,
  results,
  isExpandingSearch,
  searchPending,
  searchStageLabel,
  searchDiagnosticsActive,
  searchDiagnosticsReport,
  searchDiagnosticsStatus,
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
  const [sortOption, setSortOption] = useState<ExploreSortOption>("relevance");
  const [expandedDiagnosticsRepositoryId, setExpandedDiagnosticsRepositoryId] = useState<string | null>(
    null,
  );

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
  }, [results, sortOption]);

  useEffect(() => {
    setExpandedDiagnosticsRepositoryId(null);
  }, [results]);

  const retryLockActive = retrySecondsRemaining !== null && retrySecondsRemaining > 0;
  const expansionDisabled =
    searchPending || retryLockActive || (requiresTurnstile && !turnstileReady);
  const searchDisabled = expansionDisabled || !topicInput.trim();
  const searchButtonLabel = searchPending
    ? "Searching"
    : retryLockActive
      ? `Try Again in ${formatRetryCountdown(retrySecondsRemaining)}`
      : requiresTurnstile && !turnstileReady
      ? "Complete Verification"
      : "Run Search";
  const showLoadingResults = searchPending && !hasResults;
  const sortedResults = useMemo(
    () => sortExploreResults(results, sortOption),
    [results, sortOption],
  );
  const diagnosticsByRepositoryId = useMemo(
    () => buildLatestDiagnosticsByRepositoryId(searchDiagnosticsReport),
    [searchDiagnosticsReport],
  );
  const totalPages = Math.max(1, Math.ceil(sortedResults.length / RESULTS_PER_PAGE));
  const visibleResults = sortedResults.slice(
    (currentPage - 1) * RESULTS_PER_PAGE,
    currentPage * RESULTS_PER_PAGE,
  );
  const visibleRangeStart = hasResults ? (currentPage - 1) * RESULTS_PER_PAGE + 1 : 0;
  const visibleRangeEnd = hasResults
    ? Math.min(currentPage * RESULTS_PER_PAGE, results.length)
    : 0;
  const pageNumbers = buildPageNumbers(totalPages, currentPage);
  const hasCompletedSearchPlan = lastAiSearchPlan?.status === "ready";

  return (
    <main className="app-shell explore-shell">
      <section className="page-intro explore-intro">
        <div className="page-intro-main">
          <h1 className="page-title">Explore Scientific Software</h1>
          <p className="section-copy">
            Discover repositories across GitHub and GitLab.
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
          {searchDiagnosticsActive ? (
            <p className="query-context-note">
              <strong>Search diagnostics is enabled.</strong>{" "}
              {searchDiagnosticsStatus === "loading"
                ? "Loading internal execution data."
                : searchDiagnosticsStatus === "ready"
                  ? "Internal execution data is ready for this run."
                  : searchDiagnosticsStatus === "unavailable"
                    ? "Internal execution data is unavailable for this run."
                    : "Internal execution data will load after the search completes."}
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

      {searchDiagnosticsActive && searchDiagnosticsReport ? (
        <SearchDiagnosticsSummary report={searchDiagnosticsReport} />
      ) : null}

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
                  {searchPending ? (
                    <span className="results-count-badge">
                      {searchStageLabel ?? "Searching repositories"}
                    </span>
                  ) : hasResults ? (
                    <span className="results-count-badge">{results.length} results</span>
                  ) : null}
                </div>
              </div>
            </div>

            {hasResults ? (
              <div className="results-toolbar">
                <label className="results-sort-control" htmlFor="explore-sort">
                  <span>Sort by</span>
                  <select
                    id="explore-sort"
                    onChange={(event) => setSortOption(event.target.value as ExploreSortOption)}
                    value={sortOption}
                  >
                    <option value="relevance">Relevance</option>
                    <option value="recent_activity">Recent activity</option>
                    <option value="stars">Stars</option>
                  </select>
                </label>
              </div>
            ) : null}

            {showLoadingResults ? (
              <>
                <div className="repository-table">
                  <div className="repository-table-head">
                    <span>Repository</span>
                    <span>Source</span>
                    <span>Stars</span>
                    <span>Activity</span>
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

                        <div className="repository-cell" data-label="Source">
                          <span className="repository-skeleton-badge skeleton-shimmer" />
                        </div>

                        <div
                          className="repository-cell repository-metadata-cell"
                          data-label="Stars"
                        >
                          <span className="repository-skeleton-meta repository-skeleton-meta-short skeleton-shimmer" />
                        </div>

                        <div
                          className="repository-cell repository-metadata-cell"
                          data-label="Activity"
                        >
                          <span className="repository-skeleton-meta skeleton-shimmer" />
                        </div>

                        <div
                          className="repository-cell repository-actions-cell"
                          data-label="Actions"
                        >
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
                    <span>Stars</span>
                    <span>Activity</span>
                    <span>Actions</span>
                  </div>

                  <div className="repository-table-body">
                    {visibleResults.map((result) => {
                      const isSubscribed = subscribedRepositoryIds.includes(result.itemId);
                      const isPending = subscribePendingRepositoryId === result.itemId;
                      const diagnostics = searchDiagnosticsActive
                        ? diagnosticsByRepositoryId.get(result.itemId)
                        : undefined;
                      const diagnosticsExpanded = expandedDiagnosticsRepositoryId === result.itemId;

                      return (
                        <div className="repository-row-group" key={result.itemId}>
                          <div className="repository-row">
                            <div className="repository-main-cell">
                              <p className="repository-title">{result.fullName}</p>
                              <p className="repository-description repository-about">
                                {result.description || result.reason}
                              </p>
                            </div>

                            <div className="repository-cell" data-label="Source">
                              <SourceBadge href={result.url} source={result.source} />
                            </div>

                            <div
                              className="repository-cell repository-metadata-cell"
                              data-label="Stars"
                            >
                              {result.stars !== null ? formatCompactNumber(result.stars) : "-"}
                            </div>

                            <div
                              className="repository-cell repository-metadata-cell"
                              data-label="Activity"
                            >
                              {formatProviderActivity(result.providerUpdatedAt)}
                            </div>

                            <div
                              className="repository-cell repository-actions-cell"
                              data-label="Actions"
                            >
                              {diagnostics ? (
                                <button
                                  aria-expanded={diagnosticsExpanded}
                                  className="outline-button results-action-button repository-diagnostics-button"
                                  onClick={() => setExpandedDiagnosticsRepositoryId(
                                    diagnosticsExpanded ? null : result.itemId,
                                  )}
                                  type="button"
                                >
                                  {diagnosticsExpanded ? "Hide ranking details" : "Ranking details"}
                                </button>
                              ) : null}
                              <button
                                className={
                                  isSubscribed
                                    ? "outline-button results-action-button results-action-button-subscribed"
                                    : "solid-button results-action-button"
                                }
                                disabled={
                                  !canSubscribe || isSubscribed || isPending
                                }
                                onClick={() => onSubscribe(result)}
                                type="button"
                              >
                                {isSubscribed ? "Subscribed" : isPending ? "Saving..." : "Subscribe"}
                              </button>
                            </div>
                          </div>
                          {diagnostics && diagnosticsExpanded ? (
                            <SearchDiagnosticsRepositoryDetails snapshot={diagnostics} />
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="results-footer">
                  <p className="results-footer-copy">
                    Showing {visibleRangeStart}-{visibleRangeEnd} of {results.length} results
                  </p>
                  {canExpandSearch ? (
                    <ExpandSearchControl
                      canExpand={canExpandSearch}
                      disabled={expansionDisabled}
                      onExpand={onExpandSearch}
                    />
                  ) : hasCompletedSearchPlan ? (
                    <ExpandSearchControl
                      canExpand={false}
                      disabled
                      onExpand={onExpandSearch}
                    />
                  ) : null}
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
                {hasCompletedSearchPlan ? (
                  <ExpandSearchControl
                    canExpand={canExpandSearch}
                    disabled={expansionDisabled || !canExpandSearch}
                    onExpand={onExpandSearch}
                  />
                ) : null}
              </div>
            )}
            {isExpandingSearch ? (
              <p className="expand-search-loading-copy">
                Searching another scientific angle and updating the ranking.
              </p>
            ) : null}
          </article>
        </section>
      )}
    </main>
  );
}

const LOADING_REPOSITORY_ROW_COUNT = [0, 1, 2, 3, 4] as const;
const RESULTS_PER_PAGE = 10;

function formatCompactNumber(value: number): string {
  if (value >= 1000) {
    const compactValue = value / 1000;
    return compactValue >= 10 ? `${Math.round(compactValue)}k` : `${compactValue.toFixed(1)}k`;
  }

  return `${value}`;
}

function formatProviderActivity(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function sortExploreResults(
  results: ExploreResultItem[],
  sortOption: ExploreSortOption,
): ExploreResultItem[] {
  return [...results].sort((left, right) => {
    const primaryDifference =
      sortOption === "recent_activity"
        ? compareProviderActivity(left.providerUpdatedAt, right.providerUpdatedAt)
        : sortOption === "stars"
          ? (right.stars ?? -1) - (left.stars ?? -1)
          : right.score - left.score;

    if (primaryDifference !== 0) return primaryDifference;

    const relevanceDifference = right.score - left.score;
    if (relevanceDifference !== 0) return relevanceDifference;

    return left.fullName.localeCompare(right.fullName);
  });
}

function compareProviderActivity(left: string | null, right: string | null): number {
  const leftTimestamp = readTimestamp(left);
  const rightTimestamp = readTimestamp(right);
  if (leftTimestamp === null && rightTimestamp === null) return 0;
  if (leftTimestamp === null) return 1;
  if (rightTimestamp === null) return -1;
  return rightTimestamp - leftTimestamp;
}

function buildLatestDiagnosticsByRepositoryId(
  report: SearchDiagnosticsReport | null,
): Map<string, SearchDiagnosticsRankingSnapshot> {
  if (!report?.rankingSnapshots.length) return new Map();
  const latestStageNumber = Math.max(
    ...report.rankingSnapshots.map((snapshot) => snapshot.stageNumber),
  );
  return new Map(
    report.rankingSnapshots
      .filter((snapshot) => snapshot.stageNumber === latestStageNumber)
      .map((snapshot) => [snapshot.repositoryId, snapshot]),
  );
}

function readTimestamp(value: string | null): number | null {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

function ExpandSearchControl({
  canExpand,
  disabled,
  onExpand,
}: {
  canExpand: boolean;
  disabled: boolean;
  onExpand: () => void;
}) {
  if (canExpand) {
    return (
      <button
        className="outline-button expand-search-button"
        disabled={disabled}
        onClick={onExpand}
        type="button"
      >
        Expand search
      </button>
    );
  }

  return (
    <div className="expand-search-exhausted">
      <button className="outline-button expand-search-button" disabled type="button">
        All search angles used
      </button>
      <p>All planned search angles have been explored.</p>
    </div>
  );
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
