import type { AiSearchPlanPayload, ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";

type ExplorePageProps = {
  canSubscribe: boolean;
  createPending: boolean;
  lastAiSearchPlan: AiSearchPlanPayload | null;
  onRunSearch: () => void;
  onSearchScopeChange: (value: "repositories" | "all") => void;
  onSubscribe: () => void;
  onTopicInputChange: (value: string) => void;
  results: ExploreResultItem[];
  searchScope: "repositories" | "all";
  searchPending: boolean;
  topicInput: string;
  viewer: ViewerPayload["user"];
};

export function ExplorePage({
  canSubscribe,
  createPending,
  lastAiSearchPlan,
  onRunSearch,
  onSearchScopeChange,
  onSubscribe,
  onTopicInputChange,
  results,
  searchScope,
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
            Describe the topic, choose the search scope, and let SciScope generate
            the repository discovery queries for you.
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
              className={searchScope === "repositories" ? "solid-button" : "outline-button"}
              onClick={() => onSearchScopeChange("repositories")}
              type="button"
            >
              Repositories
            </button>
            <button
              className={searchScope === "all" ? "solid-button" : "outline-button"}
              onClick={() => onSearchScopeChange("all")}
              type="button"
            >
              All
            </button>
          </div>

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
              `All` is already available in the contract and will expand beyond repositories
              as new source families land.
            </p>
            <p className="field-hint">
              {viewer
                ? "Save this topic to your feed."
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
              {lastAiSearchPlan?.sourcePlans[0]?.queries?.length ? (
                <>
                  <p className="field-hint">
                    AI-generated search queries
                  </p>
                  {lastAiSearchPlan.sourcePlans[0].queries.map((query) => (
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
