import type { AiSearchPlanPayload, ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";
import exploreEmptyIllustration from "../assets/states/explore/explore-empty.svg";
import noResultsIllustration from "../assets/states/explore/search-no-results.svg";

type ExplorePageProps = {
  canSubscribe: boolean;
  lastAiSearchPlan: AiSearchPlanPayload | null;
  onRunSearch: () => void;
  onSubscribe: (result: ExploreResultItem) => void;
  onTopicInputChange: (value: string) => void;
  results: ExploreResultItem[];
  searchPending: boolean;
  subscribePendingRepositoryId: string | null;
  subscribedRepositoryIds: string[];
  topicInput: string;
  viewer: ViewerPayload["user"];
};

export function ExplorePage({
  canSubscribe,
  lastAiSearchPlan,
  onRunSearch,
  onSubscribe,
  onTopicInputChange,
  results,
  searchPending,
  subscribePendingRepositoryId,
  subscribedRepositoryIds,
  topicInput,
  viewer,
}: ExplorePageProps) {
  const hasResults = results.length > 0;
  const isPreSearch = !lastAiSearchPlan && !hasResults;
  const isNoResults = !isPreSearch && !hasResults;

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
              Explore mode is public. Sign in with Google to save subscriptions and build
              your feed.
            </p>
          ) : null}
          <div className="query-actions">
            <button
              className="solid-button"
              disabled={searchPending || !topicInput.trim()}
              onClick={onRunSearch}
              type="button"
            >
              {searchPending ? "Running..." : "Run search"}
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
