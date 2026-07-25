import type { ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";

type ExplorePageProps = {
  canSubscribe: boolean;
  createPending: boolean;
  queryInput: string;
  lastQueries: string[];
  onQueryInputChange: (value: string) => void;
  onRunSearch: () => void;
  onSubscribe: () => void;
  onTopicInputChange: (value: string) => void;
  results: ExploreResultItem[];
  searchPending: boolean;
  topicInput: string;
  viewer: ViewerPayload["user"];
};

export function ExplorePage({
  canSubscribe,
  createPending,
  queryInput,
  lastQueries,
  onQueryInputChange,
  onRunSearch,
  onSubscribe,
  onTopicInputChange,
  results,
  searchPending,
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
            Describe the topic, refine the queries, and save it as a subscription when you want
            ongoing updates.
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

          <label className="field-label" htmlFor="manual-query-input">
            Manual queries
          </label>
          <input
            id="manual-query-input"
            className="text-field"
            value={queryInput}
            onChange={(event) => onQueryInputChange(event.target.value)}
            placeholder="pcs, paramagnetic nmr, tensor fitting"
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
            <button
              className="solid-button"
              disabled={!canSubscribe || createPending}
              onClick={onSubscribe}
              type="button"
            >
              {createPending ? "Saving..." : "Subscribe"}
            </button>
            <p className="field-hint">
              {viewer
                ? "Save this topic to your feed."
                : "Sign in to save this topic to your feed."}
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
              {lastQueries.length > 0 ? (
                lastQueries.map((query) => (
                  <span className="query-chip" key={query}>
                    {query}
                  </span>
                ))
              ) : (
                <p className="empty-copy">Run a search to see the exact queries sent to GitHub and GitLab.</p>
              )}
            </div>
          </div>

          <div className="signal-list">
            {results.length > 0 ? (
              results.map((result) => (
                <div className="signal-row" key={result.itemId}>
                  <div>
                    <strong>{result.fullName}</strong>
                    <p>{result.description || result.reason}</p>
                  </div>
                  <div className="signal-meta">
                    <SourceBadge source={result.source} />
                    <span>{result.query}</span>
                  </div>
                </div>
              ))
            ) : (
              <p className="empty-copy">No repositories yet. Run a search from the manual queries.</p>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}
