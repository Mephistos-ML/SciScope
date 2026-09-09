import { EventKindBadge } from "../components/EventKindBadge";
import feedEmptyIllustration from "../assets/states/feed/feed-empty.svg";
import { getSourceLogo } from "../lib/sourceLogos";
import type { FeedEventItem, ViewerPayload } from "../types/api";

type FeedPageProps = {
  feedHasMore: boolean;
  feedLoadPending: boolean;
  feedState: "all" | "unread";
  feedSubscriptionId: string | null;
  unreadFeedCount: number;
  feedUpdatePending: boolean;
  feedEvents: FeedEventItem[];
  onLoadOlder: () => void;
  onMarkAllRead: () => void;
  onMarkRead: (eventId: string) => void;
  onStateChange: (state: "all" | "unread") => void;
  viewer: ViewerPayload["user"];
};

export function FeedPage({
  feedUpdatePending,
  feedHasMore,
  feedLoadPending,
  feedState,
  feedSubscriptionId,
  unreadFeedCount,
  feedEvents,
  onLoadOlder,
  onMarkAllRead,
  onMarkRead,
  onStateChange,
  viewer,
}: FeedPageProps) {
  const hasEvents = feedEvents.length > 0;
  const unreadCount = unreadFeedCount;
  const visibleEvents = feedEvents;

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
      ) : !hasEvents && feedState === "all" ? (
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
                  <h3 className="panel-title">{feedSubscriptionId ? "Repository Events" : "Recent Repository Events"}</h3>
                  <span className="results-count-badge">{visibleEvents.length} events</span>
                </div>
              </div>
              <div className="feed-actions">
                <div aria-label="Feed visibility" className="feed-filter" role="group">
                  <button
                    className={feedState === "all" ? "feed-filter-button feed-filter-button-active" : "feed-filter-button"}
                    disabled={feedLoadPending}
                    onClick={() => onStateChange("all")}
                    type="button"
                  >
                    All
                  </button>
                  <button
                    className={feedState === "unread" ? "feed-filter-button feed-filter-button-active" : "feed-filter-button"}
                    disabled={feedLoadPending}
                    onClick={() => onStateChange("unread")}
                    type="button"
                  >
                    Unread {unreadCount > 0 ? `(${unreadCount})` : ""}
                  </button>
                </div>
                <button
                  className="outline-button"
                  disabled={feedUpdatePending || unreadCount === 0}
                  onClick={onMarkAllRead}
                  type="button"
                >
                  Mark all read
                </button>
              </div>
            </div>

            <div className="repository-table feed-repository-table">
              <div className="repository-table-head">
                <span>Event</span>
                <span>Repository</span>
                <span>When</span>
                <span>State</span>
              </div>

              <div className="repository-table-body">
                {visibleEvents.map((event) => (
                  <div
                    className={event.readAt === null ? "repository-row repository-row-unread" : "repository-row"}
                    key={event.eventId}
                    >
                    <div className="repository-main-cell">
                      <div className="feed-event-heading">
                        <EventKindBadge kind={event.signalKind} />
                        <a
                          className="repository-title repository-inline-link"
                          href={event.url}
                          rel="noreferrer"
                          target="_blank"
                        >
                          {event.title}
                        </a>
                      </div>
                      <p className="repository-description">
                        {event.summary || "No event summary available."}
                      </p>
                    </div>

                    <div className="repository-cell" data-label="Repository">
                      <span className="repository-provider-link">
                        {getSourceLogo(event.repositorySource) ? (
                          <img alt="" aria-hidden="true" src={getSourceLogo(event.repositorySource) ?? undefined} />
                        ) : null}
                        <a
                          className="repository-inline-link"
                          href={event.repositoryUrl}
                          rel="noreferrer"
                          target="_blank"
                        >
                          {event.repositoryFullName}
                        </a>
                      </span>
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="When">
                      <span className="repository-muted-value">
                        {formatEventDate(event.publishedAt || event.createdAt)}
                      </span>
                    </div>

                    <div className="repository-cell repository-metadata-cell" data-label="State">
                      {event.readAt === null ? (
                        <button
                          className="feed-read-button"
                          disabled={feedUpdatePending}
                          onClick={() => onMarkRead(event.eventId)}
                          type="button"
                        >
                          Mark read
                        </button>
                      ) : (
                        <span className="repository-muted-value">Read</span>
                      )}
                    </div>
                  </div>
                ))}
                {visibleEvents.length === 0 ? (
                  <div className="feed-filter-empty">No unread Feed events.</div>
                ) : null}
                {feedHasMore ? (
                  <div className="feed-load-more">
                    <button
                      className="outline-button"
                      disabled={feedLoadPending}
                      onClick={onLoadOlder}
                      type="button"
                    >
                      {feedLoadPending ? "Loading…" : "Load older events"}
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </article>
        </section>
      )}
    </main>
  );
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
