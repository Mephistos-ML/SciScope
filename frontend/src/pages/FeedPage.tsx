import { SourceBadge } from "../components/SourceBadge";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
import type { FeedEventItem, ViewerPayload } from "../types/api";

type FeedPageProps = {
  feedEvents: FeedEventItem[];
  viewer: ViewerPayload["user"];
};

export function FeedPage({ feedEvents, viewer }: FeedPageProps) {
  const hasEvents = feedEvents.length > 0;

  return (
    <main className="app-shell feed-shell">
      <section className="page-intro">
        <div className="page-intro-main">
          <h1 className="page-title">Feed</h1>
          <p className="section-copy">
            Repository updates collected after you subscribed, across releases and default-branch commits.
          </p>
        </div>
      </section>

      {!viewer ? (
        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">Sign In to View Your Feed</h2>
            <p className="empty-state-copy">
              Use Google sign-in to save repositories from Explore and keep their updates here.
            </p>
          </article>
        </section>
      ) : !hasEvents ? (
        <section className="results-panel">
          <article className="empty-state-panel feed-empty-state">
            <img
              alt=""
              aria-hidden="true"
              className="empty-state-illustration"
              src={feedEmptyIllustration}
            />
            <h2 className="empty-state-title">No Feed Events Yet</h2>
            <p className="empty-state-copy">
              New releases and default-branch commits from your subscribed repositories will appear here.
            </p>
          </article>
        </section>
      ) : (
        <section className="results-panel">
          <article className="info-panel repository-results-panel">
            <div className="results-header">
              <div className="results-header-main">
                <p className="section-kicker">Feed</p>
                <div className="results-title-row">
                  <h3 className="panel-title">Recent Repository Events</h3>
                  <span className="results-count-badge">{feedEvents.length} events</span>
                </div>
              </div>
            </div>

            <div className="repository-table">
              <div className="repository-table-head">
                <span>Event</span>
                <span>Repository</span>
                <span>Source</span>
                <span>Type</span>
                <span>Query</span>
                <span>When</span>
              </div>

              <div className="repository-table-body">
                {feedEvents.map((event) => (
                  <div className="repository-row" key={event.eventId}>
                    <div className="repository-main-cell">
                      <p className="repository-title">{event.title}</p>
                      <p className="repository-description">
                        {event.summary || "No event summary available."}
                      </p>
                    </div>

                    <div className="repository-cell" data-label="Repository">
                      <a
                        className="repository-inline-link"
                        href={event.repositoryUrl}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {event.repositoryFullName}
                      </a>
                    </div>

                    <div className="repository-cell" data-label="Source">
                      <SourceBadge href={event.url} source={event.source} />
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="Type">
                      <span className="repository-muted-value">
                        {formatSignalKind(event.signalKind)}
                      </span>
                    </div>

                    <div className="repository-cell repository-query-cell" data-label="Query">
                      {event.selectedQuery || "No Query Snapshot"}
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="When">
                      <span className="repository-muted-value">
                        {formatEventDate(event.publishedAt || event.createdAt)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </article>
        </section>
      )}
    </main>
  );
}

function formatSignalKind(value: string): string {
  if (value === "release") {
    return "Release";
  }
  if (value === "commit") {
    return "Commit";
  }
  return value;
}

function formatEventDate(value: string | null): string {
  if (!value) {
    return "Unknown";
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parsedDate);
}
