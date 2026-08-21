import type { AiSearchPlanPayload, ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";
import { TurnstileWidget } from "../components/TurnstileWidget";
import exploreEmptyIllustration from "../assets/states/explore/explore-empty.svg";
import noResultsIllustration from "../assets/states/explore/search-no-results.svg";

type ExploreSearchFeedback = {
  message: string;
  retryAfterSeconds: number | null;
  signInSuggested: boolean;
  turnstileRequired: boolean;
};

type ExplorePageProps = {
  canSubscribe: boolean;
  exploreSearchFeedback: ExploreSearchFeedback | null;
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
  const isPreSearch = !lastAiSearchPlan && !hasResults;
  const isNoResults = !isPreSearch && !hasResults;
  const requiresTurnstile = exploreSearchFeedback?.turnstileRequired === true;
  const searchDisabled =
    searchPending || !topicInput.trim() || (requiresTurnstile && !turnstileReady);
  const searchButtonLabel = searchPending
    ? "Running..."
    : requiresTurnstile && !turnstileReady
      ? "Complete verification"
      : "Run search";

  return (
    <main className="app-shell explore-shell">
      <section className="page-intro explore-intro">
        <div className="page-intro-main">
          <h1 className="page-title">Explore scientific software</h1>
          <p className="section-copy">
            Discover repositories across GitHub, GitLab, Gitee, GitCode and GitVerse.
          </p>
        </div>
      </section>

      <section className="explore-query-layout">
        <article className="query-workspace">
          <label className="field-label" htmlFor="topic-query">
            Topic description
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
                Sign in with Google
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
                      ? "Verification complete. Run search to continue."
                      : "Complete the verification challenge to continue."}
                  </p>
                  <TurnstileWidget
                    onTokenChange={onTurnstileTokenChange}
                    resetKey={turnstileResetKey}
                    siteKey={turnstileSiteKey}
                  />
                </>
              ) : null}
              {exploreSearchFeedback.signInSuggested && !viewer ? (
                <div className="query-feedback-actions">
                  <button className="outline-button" onClick={onSignIn} type="button">
                    Sign in with Google
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="query-actions">
            <button
              className="solid-button"
              disabled={searchDisabled}
              onClick={onRunSearch}
              type="button"
            >
              {searchButtonLabel}
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
            <h2 className="empty-state-title">Start exploring</h2>
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
                  <h3 className="panel-title">Matched repositories</h3>
                  {hasResults ? (
                    <span className="results-count-badge">{results.length} results</span>
                  ) : null}
                </div>
              </div>
              <div className="results-plan-summary">
                {lastAiSearchPlan?.queries.length ? (
                  <>
                    <p className="field-hint">AI-generated search queries</p>
                    <div className="query-chip-row">
                      {lastAiSearchPlan.queries.map((query) => (
                        <span className="query-chip" key={query}>
                          {query}
                        </span>
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

            {hasResults ? (
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
                    {results.map((result) => {
                      const isSubscribed = subscribedRepositoryIds.includes(result.itemId);
                      const isPending = subscribePendingRepositoryId === result.itemId;

                      return (
                        <div className="repository-row" key={result.itemId}>
                          <div className="repository-main-cell">
                            <p className="repository-title">{result.fullName}</p>
                            <p className="repository-description">
                              {result.description || result.reason}
                            </p>
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
                            {result.query || "No query snapshot"}
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

                <p className="results-footer-copy">
                  Showing 1-{results.length} of {results.length} results
                </p>
              </>
            ) : (
              <div className="empty-state-panel search-no-results-state">
                <img
                  alt=""
                  aria-hidden="true"
                  className="empty-state-illustration search-no-results-illustration"
                  src={noResultsIllustration}
                />
                <h2 className="empty-state-title">No repositories found</h2>
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

function formatCompactNumber(value: number): string {
  if (value >= 1000) {
    const compactValue = value / 1000;
    return compactValue >= 10 ? `${Math.round(compactValue)}k` : `${compactValue.toFixed(1)}k`;
  }

  return `${value}`;
}
