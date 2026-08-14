import type { AiSearchPlanPayload, ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";

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
  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="hero-copy-block">
          <p className="section-kicker">Explore</p>
          <h2 className="section-title">Find the most relevant repositories for a research topic.</h2>
          <p className="section-copy">
            Describe the topic and let SciScope generate repository discovery queries.
          </p>
        </div>

        <div className="query-panel">
          <label className="field-label" htmlFor="topic-query">
            Topic description
          </label>
          <textarea
            id="topic-query"
            className="text-field text-area"
            value={topicInput}
            onChange={(event) => onTopicInputChange(event.target.value)}
            placeholder="Track repositories around paramagnetic NMR analysis workflows."
          />
          <div className="query-actions">
            <button
              className="outline-button"
              disabled={searchPending}
              onClick={onRunSearch}
              type="button"
            >
              {searchPending ? "Running..." : "Run search"}
            </button>
            <p className="field-hint">
              {viewer
                ? "Subscribe to specific repositories directly from the results."
                : "Sign in with Google before saving this topic to your feed."}
            </p>
          </div>
        </div>
      </section>

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
    </main>
  );
}
