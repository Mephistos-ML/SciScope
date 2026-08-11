import type { AuthMode } from "../lib/config";
import type { ExploreResultItem, ViewerPayload } from "../types/api";
import { SourceBadge } from "../components/SourceBadge";

type ExplorePageProps = {
  authMode: AuthMode;
  canSubscribe: boolean;
  createPending: boolean;
  lastQueries: string[];
  lastQueryStrategy: "profile_terms" | "pending_ai" | null;
  onProfileQueryTermsInputChange: (value: string) => void;
  onRunSearch: () => void;
  onSubscribe: () => void;
  onTopicInputChange: (value: string) => void;
  profileQueryTermsInput: string;
  results: ExploreResultItem[];
  searchPending: boolean;
  topicInput: string;
  viewer: ViewerPayload["user"];
};

export function ExplorePage({
  authMode,
  canSubscribe,
  createPending,
  lastQueries,
  lastQueryStrategy,
  onProfileQueryTermsInputChange,
  onRunSearch,
  onSubscribe,
  onTopicInputChange,
  profileQueryTermsInput,
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
            Describe the topic now. Until the AI profile layer lands, provide structured
            research profile query terms manually to simulate the agent output.
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

          <label className="field-label" htmlFor="profile-query-terms">
            Research profile query terms (temporary)
          </label>
          <textarea
            id="profile-query-terms"
            className="text-field text-area"
            value={profileQueryTermsInput}
            onChange={(event) => onProfileQueryTermsInputChange(event.target.value)}
            placeholder={"paramagnetic nmr\npcs tensor fitting"}
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
              One term per line. These terms currently stand in for the structured query output that the AI layer will later generate from the topic description.
            </p>
            <p className="field-hint">
              {viewer
                ? "Save this topic to your feed."
                : authMode === "dev"
                  ? "Developer sign-in is required before you can save this topic."
                  : "Authentication is disabled in this environment, so subscriptions stay read-only for now."}
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
                <>
                  <p className="field-hint">
                    {lastQueryStrategy === "profile_terms"
                      ? "Using research profile query terms"
                      : "Waiting for AI profile generation"}
                  </p>
                  {lastQueries.map((query) => (
                    <span className="query-chip" key={query}>
                      {query}
                    </span>
                  ))}
                </>
              ) : (
                <p className="empty-copy">
                  Run a search to see the queries produced from the current research profile terms.
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
                No repositories yet. Without research profile terms, the topic stays in pending-AI mode.
              </p>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}
