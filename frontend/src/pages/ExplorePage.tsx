import type { AiSearchPlanPayload, ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";
import exploreEmptyIllustration from "../assets/states/explore/explore-empty.svg";

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
  const isPreSearch = !lastAiSearchPlan && results.length === 0;

  return (
    <main className="app-shell">
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
            placeholder="Describe a research topic, method, software or workflow..."
          />
          <p className="field-hint">
            {viewer
              ? "SciScope will generate discovery queries and let you subscribe to specific repositories from the results."
              : "SciScope will generate discovery queries and search across all sources. Sign in with Google before saving repositories to your feed."}
          </p>
          <div className="query-actions">
            <button
              className="solid-button"
              disabled={searchPending}
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
          <article className="info-panel">
          <div className="results-header">
            <div>
              <p className="section-kicker">Results</p>
              <h3 className="panel-title">Matched repositories</h3>
            </div>
            <div className="query-chip-row">
              {lastAiSearchPlan?.queries.length ? (
                <>
                  <p className="field-hint">
                    AI-generated search queries
                  </p>
                  {lastAiSearchPlan.queries.map((query) => (
                    <span className="query-chip" key={query}>
                      {query}
                    </span>
                  ))}
                </>
              ) : (
                <p className="empty-copy">
                  Run a search to see the queries produced for the current AI search plan.
                </p>
              )}
            </div>
          </div>

          <div className="signal-list">
            {results.length > 0 ? (
              results.map((result) => {
                const isSubscribed = subscribedRepositoryIds.includes(result.itemId);
                const isPending = subscribePendingRepositoryId === result.itemId;

                return (
                  <div className="signal-row" key={result.itemId}>
                    <div>
                      <strong>{result.fullName}</strong>
                      <p>{result.description || result.reason}</p>
                    </div>
                    <div className="signal-meta">
                      <SourceBadge href={result.url} source={result.source} />
                      <span>{result.query}</span>
                      <button
                        className={isSubscribed ? "outline-button" : "solid-button"}
                        disabled={!canSubscribe || isSubscribed || isPending}
                        onClick={() => onSubscribe(result)}
                        type="button"
                      >
                        {isSubscribed ? "Subscribed" : isPending ? "Saving..." : "Subscribe"}
                      </button>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="empty-copy">
                No repositories yet. Without generated queries, the search plan stays pending.
              </p>
            )}
          </div>
          </article>
        </section>
      )}
    </main>
  );
}
